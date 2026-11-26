"""Testes do tratamento de erros do Gemini e do limite diário. Só falsos; não chama a API."""

import threading
from datetime import datetime, timezone
from types import SimpleNamespace

import categorizador
import recomendador
from categorizador import (
    ErroChave,
    ErroGemini,
    ErroLimiteApp,
    ErroValidacao,
    _cota_diaria,
    _erro_temporario,
    explicar_erro,
    pedidos_restantes,
)


# Guarda as funções verdadeiras antes de os testes abaixo trocarem por falsas
CATEGORIZAR_LOTE_REAL = categorizador.categorizar_lote


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

# --- Limite diário do app: relógio e cliente falsos ---
categorizador.categorizar_lote = CATEGORIZAR_LOTE_REAL
LIMITE = categorizador.LIMITE_DIARIO_APP
RESPOSTA_OK = '[{"id": "X1", "categoria": "Outros"}]'


def relogio(*quando):
    """Fixa a hora (em UTC) que o contador enxerga."""
    categorizador._agora = lambda: datetime(*quando, tzinfo=timezone.utc)


class ClienteFalso:
    """Imita o cliente do Gemini e conta quantas vezes a 'API' foi chamada."""

    def __init__(self, erros_por_modelo=None):
        self.erros_por_modelo = erros_por_modelo or {}
        self.modelos_chamados = []
        self.models = self

    def generate_content(self, model, contents, config):
        self.modelos_chamados.append(model)
        if model in self.erros_por_modelo:
            raise self.erros_por_modelo[model]
        return SimpleNamespace(text=RESPOSTA_OK)


def preparar(usados=0, erros_por_modelo=None):
    """Contador com `usados` pedidos no dia do relógio e um cliente falso novo."""
    categorizador._dia_contado = None
    categorizador._pedidos_feitos = 0
    for _ in range(usados):
        categorizador.registrar_pedido()
    cliente = ClienteFalso(erros_por_modelo)
    categorizador._obter_client = lambda: cliente
    recomendador._obter_client = lambda: cliente
    return cliente


def deve_estourar(funcao):
    try:
        funcao()
    except ErroLimiteApp as e:
        return e
    raise AssertionError("era para dar ErroLimiteApp")


relogio(2026, 11, 26, 20, 0)
cliente = preparar()
assert LIMITE == 15 and pedidos_restantes() == 15
categorizador.categorizar_lote(LOTE)
assert len(cliente.modelos_chamados) == 1 and pedidos_restantes() == 14
print("OK: cada chamada real conta 1 pedido (limite de 15)")

cliente = preparar(usados=LIMITE)
erro_limite = deve_estourar(lambda: categorizador.categorizar_lote(LOTE))
deve_estourar(lambda: recomendador._chamar_gemini("prompt", PRINCIPAL))
assert cliente.modelos_chamados == [] and pedidos_restantes() == 0
print("OK: limite atingido não chama a API (categorização e recomendações)")

esperas.clear()
for funcao in (
    lambda: categorizador._categorizar_lote_resiliente(LOTE, 1),
    lambda: recomendador.gerar_recomendacoes({}),
):
    frase = explicar_erro(capturar(funcao))
    assert frase == categorizador.FRASE_LIMITE_APP, frase
assert cliente.modelos_chamados == [] and esperas == []
assert "5h" in frase and "Usar dados de exemplo" in frase
print(f"  limite atingido: {frase}")
print("OK: no limite não há espera nem reserva, e a frase é a do limite diário")

# 27/11 07:59 UTC ainda é 26/11 no Pacífico; 08:00 UTC já é 27/11 (5h em Brasília)
relogio(2026, 11, 26, 20, 0)
preparar(usados=LIMITE)
relogio(2026, 11, 27, 0, 30)
assert pedidos_restantes() == 0
relogio(2026, 11, 27, 7, 59)
assert pedidos_restantes() == 0
print("OK: a virada do dia em UTC não zera o contador")

relogio(2026, 11, 27, 8, 0)
assert pedidos_restantes() == LIMITE
cliente = ClienteFalso()
categorizador._obter_client = lambda: cliente
categorizador.categorizar_lote(LOTE)
assert len(cliente.modelos_chamados) == 1 and pedidos_restantes() == LIMITE - 1
print("OK: a virada do dia no Pacífico zera o contador")

TRES = [{"id": f"X{i}", "descricao": "TESTE", "valor": -1.0} for i in (1, 2, 3)]
cliente = preparar(usados=LIMITE - 2)
erro = deve_estourar(lambda: categorizador.categorizar_todos(TRES, tamanho_lote=1))
assert cliente.modelos_chamados == [] and pedidos_restantes() == 2
frase = explicar_erro(erro)
assert "3 pedidos" in frase and "2 restantes" in frase and "Usar dados de exemplo" in frase
print(f"  recusa antecipada: {frase}")
print("OK: com menos saldo que lotes, recusa sem gastar nenhum pedido")

cliente = preparar(usados=LIMITE - 1)
assert len(categorizador.categorizar_todos(LOTE)) == 1
assert len(cliente.modelos_chamados) == 1 and pedidos_restantes() == 0
print("OK: com saldo igual ao número de lotes, categoriza")

cliente = preparar(erros_por_modelo={PRINCIPAL: sobrecarga})
categorizador._categorizar_lote_resiliente(LOTE, 1)
assert cliente.modelos_chamados == [PRINCIPAL] * 4 + [RESERVA]
assert pedidos_restantes() == LIMITE - 5
print("OK: na categorização, tentativas e reserva contam")

cliente = preparar(erros_por_modelo={PRINCIPAL: sobrecarga, RESERVA: sobrecarga})
capturar(lambda: recomendador.gerar_recomendacoes({}))
assert cliente.modelos_chamados == [PRINCIPAL] * 4 + [RESERVA]
assert pedidos_restantes() == LIMITE - 5
print("OK: nas recomendações, tentativas e reserva contam")

cliente = preparar(usados=LIMITE - 2, erros_por_modelo={PRINCIPAL: sobrecarga})
erro = capturar(lambda: categorizador._categorizar_lote_resiliente(LOTE, 1))
assert cliente.modelos_chamados == [PRINCIPAL] * 2 and pedidos_restantes() == 0
assert explicar_erro(erro) == categorizador.FRASE_LIMITE_APP
print("OK: limite atingido no meio das tentativas para de chamar a API")


def sem_chave():
    raise ErroChave("sem chave")


preparar()
categorizador._obter_client = sem_chave
try:
    categorizador.categorizar_lote(LOTE)
    raise AssertionError("era para dar ErroChave")
except ErroChave:
    pass
assert pedidos_restantes() == LIMITE
print("OK: sem chave não há chamada e nada é contado")

preparar()
aceitos = []


def pedir():
    try:
        categorizador.registrar_pedido()
        aceitos.append(1)
    except ErroLimiteApp:
        pass


threads = [threading.Thread(target=pedir) for _ in range(100)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
assert len(aceitos) == LIMITE and pedidos_restantes() == 0
print("OK: com 100 pedidos simultâneos, só 15 passam")
