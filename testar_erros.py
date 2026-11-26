"""Testes do tratamento de erros do Gemini. Só erros falsos; não chama a API."""

import categorizador
import recomendador
from categorizador import (
    ErroChave,
    ErroGemini,
    ErroValidacao,
    _cota_diaria,
    _erro_temporario,
    explicar_erro,
)


class ErroFalso(Exception):
    """Imita os erros da API: tem .code e um texto em inglês."""

    def __init__(self, code, texto):
        super().__init__(f"{code} {texto}")
        self.code = code


TEXTO_DIA = "RESOURCE_EXHAUSTED quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier"
TEXTO_MINUTO = "RESOURCE_EXHAUSTED quotaId: GenerateRequestsPerMinutePerProjectPerModel"

cota = ErroFalso(429, TEXTO_DIA)
minuto = ErroFalso(429, TEXTO_MINUTO)
sobrecarga = ErroFalso(503, "UNAVAILABLE The model is overloaded.")

# --- Classificação ---
assert _cota_diaria(cota)
assert _cota_diaria(ErroFalso(429, "quota exceeded perday"))  # sem diferenciar maiúsculas
assert not _erro_temporario(cota)
print("OK: 429 com PerDay é cota diária e não é temporário")

assert not _cota_diaria(minuto)
assert _erro_temporario(minuto)
print("OK: 429 sem PerDay continua temporário")

assert not _cota_diaria(ErroFalso(503, "PerDay"))
assert _erro_temporario(sobrecarga)
print("OK: só o código 429 conta como cota diária")

# --- Chamadas falsas: nenhuma espera de verdade e nenhuma API ---
esperas = []
categorizador.time.sleep = esperas.append  # recomendador usa o mesmo módulo time


def categorizar_falso(erros_por_modelo, modelos):
    """Levanta o erro do modelo; sem erro cadastrado, devolve uma categoria."""

    def chamar(lote, modelo=categorizador.MODELO):
        modelos.append(modelo)
        if modelo in erros_por_modelo:
            raise erros_por_modelo[modelo]
        return [{"id": t["id"], "categoria": "Outros"} for t in lote]

    return chamar


def capturar(funcao):
    try:
        funcao()
    except ErroGemini as e:
        return e
    raise AssertionError("era para dar ErroGemini")


LOTE = [{"id": "X1", "descricao": "TESTE", "valor": -1.0}]
PRINCIPAL, RESERVA = categorizador.MODELO, categorizador.MODELO_RESERVA

modelos = []
categorizador.categorizar_lote = categorizar_falso({PRINCIPAL: cota}, modelos)
resultado, extras = categorizador._categorizar_lote_resiliente(LOTE, 1)
assert modelos == [PRINCIPAL, RESERVA], modelos
assert esperas == [], esperas
assert extras == 1 and resultado[0]["modelo"] == RESERVA
print("OK: categorização com cota diária vai direto ao reserva, sem sleep")

modelos = []
categorizador.categorizar_lote = categorizar_falso({PRINCIPAL: cota, RESERVA: sobrecarga}, modelos)
erro_duplo = capturar(lambda: categorizador._categorizar_lote_resiliente(LOTE, 1))
assert modelos == [PRINCIPAL, RESERVA] and esperas == []
assert erro_duplo.erros == (cota, sobrecarga)
print("OK: cota diária no principal e 503 no reserva guardam os dois erros")

modelos = []
categorizador.categorizar_lote = categorizar_falso({PRINCIPAL: minuto}, modelos)
categorizador._categorizar_lote_resiliente(LOTE, 1)
assert modelos == [PRINCIPAL] * 4 + [RESERVA], modelos
assert esperas == categorizador.ESPERAS_TENTATIVAS, esperas
print("OK: 429 sem PerDay ainda espera e tenta de novo antes do reserva")

# --- Recomendações (pacote trocado por um falso: aqui só importam as chamadas) ---
recomendador.montar_marcadores = lambda pacote: {}
recomendador.montar_prompt = lambda pacote, marcadores: "prompt falso"


def gemini_falso(erros_por_modelo, modelos):
    def chamar(prompt, modelo):
        modelos.append(modelo)
        raise erros_por_modelo[modelo]

    return chamar


esperas.clear()
modelos = []
erro_rec = capturar(
    lambda: recomendador.gerar_recomendacoes(
        {}, chamar=gemini_falso({PRINCIPAL: cota, RESERVA: sobrecarga}, modelos)
    )
)
assert modelos == [PRINCIPAL, RESERVA], modelos
assert esperas == [], esperas
assert erro_rec.erros == (cota, sobrecarga)
print("OK: recomendações com cota diária vão direto ao reserva, sem sleep")

# --- Frases para o usuário ---
INGLES = ["RESOURCE_EXHAUSTED", "UNAVAILABLE", "overloaded", "quota", "API key", "Server", "disconnected"]


class RemoteProtocolError(Exception):
    pass


RemoteProtocolError.__module__ = "httpx"

casos = {
    "cota diária": (cota, "5h"),
    "sobrecarga 503": (sobrecarga, "sobrecarregado"),
    "conexão caída (httpx)": (RemoteProtocolError("Server disconnected"), "conexão"),
    "conexão caída": (ConnectionError("Server disconnected"), "conexão"),
    "429 por minuto": (minuto, "Espere um minuto"),
    "chave inválida 400": (ErroFalso(400, "API key not valid"), "chave"),
    "chave 400 (API_KEY_INVALID)": (ErroFalso(400, "reason: API_KEY_INVALID"), "chave"),
    "chave 400 (maiúsculas trocadas)": (ErroFalso(400, "api KEY expired"), "chave"),
    "outro 400": (ErroFalso(400, "INVALID_ARGUMENT bad schema"), "resposta válida"),
    "chave 401": (ErroFalso(401, "UNAUTHENTICATED"), "chave"),
    "chave 403": (ErroFalso(403, "PERMISSION_DENIED"), "chave"),
    "chave ausente": (ErroChave("Missing key"), "chave"),
    "outro erro": (ValueError("something broke"), "resposta válida"),
    "resposta inválida": (ErroValidacao("JSON"), "resposta válida"),
}
for nome, (erro, trecho) in casos.items():
    # Testa o erro solto e embrulhado em ErroGemini, como o app recebe
    for entrada in (erro, ErroGemini(f"texto técnico: {erro}", erro)):
        frase = explicar_erro(entrada)
        assert trecho in frase, (nome, frase)
        assert str(erro) not in frase, (nome, frase)
        assert not any(p.lower() in frase.lower() for p in INGLES), (nome, frase)
    print(f"  {nome}: {frase}")
print("OK: frases de explicar_erro em português, sem texto bruto da API")

assert "chave" not in explicar_erro(ErroFalso(400, "INVALID_ARGUMENT bad schema"))
print("OK: 400 só vira a frase da chave quando o texto fala da chave")

assert "pouco tempo" in explicar_erro(minuto) and "cota diária" not in explicar_erro(minuto)
print("OK: 429 por minuto tem frase própria")

assert "Usar dados de exemplo" in explicar_erro(cota)
print("OK: a frase da cota diária sugere os dados de exemplo")

for erro in (erro_duplo, erro_rec):
    frase = explicar_erro(erro)
    assert "Modelo principal: A cota diária" in frase, frase
    assert "Modelo reserva: O Gemini está sobrecarregado" in frase, frase
    assert not any(p.lower() in frase.lower() for p in INGLES), frase
print(f"  dois erros: {frase}")
print("OK: com dois erros diferentes, a frase explica os dois")

iguais = explicar_erro(ErroGemini("texto", cota, ErroFalso(429, TEXTO_DIA)))
assert iguais == explicar_erro(cota) and "Modelo" not in iguais
print("OK: com dois erros iguais, a frase aparece uma vez só")
