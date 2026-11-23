"""Testes de recomendador.py. Não chama a API do Gemini."""

import json

import pandas as pd

from analise import juntar_categorias, montar_pacote
from categorizador import ErroValidacao
from extrato import carregar_e_validar
import recomendador
from recomendador import (
    gerar_recomendacoes,
    montar_prompt,
    formatar_reais,
    lista_para_prompt,
    montar_marcadores,
    preencher_resposta,
    validar_resposta,
)

# --- a) Pacote e marcadores com as categorias da IA ---
df, erros = carregar_e_validar("dados/transacoes.csv")
assert not erros, erros
categorias = pd.read_csv("resultados/categorias_v2-regras.csv", dtype={"id": str})
df = juntar_categorias(df, categorias.to_dict("records"))
pacote = montar_pacote(df)
marcadores = montar_marcadores(pacote)

# --- b) Quantidade e primeiras linhas ---
print(f"Marcadores: {len(marcadores)}")
print("\n=== lista_para_prompt (10 primeiras linhas) ===")
print("\n".join(lista_para_prompt(marcadores).splitlines()[:10]))

# --- c) Formatação ---
assert formatar_reais(1350.0) == "R$ 1.350,00"
assert formatar_reais(0.0) == "R$ 0,00"
assert formatar_reais(-16.95) == "-R$ 16,95"
print("\nOK: formatar_reais (milhar, centavos, zero e negativo)")

# --- d) Textos dos marcadores ---
esperado = {
    "{diferenca.sobra}": "queda de R$ 1.800,68",
    "{Transporte.diferenca}": "alta de R$ 176,19",
    "{diferenca.renda_fixa}": "sem variação",
    "{2026-10.sobra}": "R$ 1.400,46",
    "{fixo_1}": "R$ 1.350,00",
    "{total.investimentos_aplicados}": "R$ 1.076,33",
    "{Moradia e contas.2026-09}": "R$ 0,00",
}
for marcador, texto in esperado.items():
    assert marcadores[marcador]["texto"] == texto, (marcador, marcadores[marcador])
assert len(marcadores) == 81, len(marcadores)
print("OK: textos dos marcadores e total de 81 marcadores")

# --- e) Resposta falsa válida ---
valida = {
    "recomendacoes": [
        {
            "titulo": "Recompor a renda extra",
            "diagnostico": "Entre agosto e outubro, a sobra teve {diferenca.sobra}.",
            "acao": "A renda extra foi de {2026-08.renda_extra} em agosto e de "
                    "{2026-10.renda_extra} em outubro; planeje sem contar com ela.",
        },
        {
            "titulo": "Olhar o transporte",
            "diagnostico": "O gasto variável com Transporte teve {Transporte.diferenca}.",
            "acao": "Compare {Transporte.2026-08} em agosto com {Transporte.2026-10} em outubro.",
        },
        {
            "titulo": "Manter os gastos fixos sob controle",
            "diagnostico": "O aluguel custa em média {fixo_1} por mês.",
            "acao": "Já foram aplicados {total.investimentos_aplicados} em investimentos.",
        },
    ]
}
validar_resposta(valida, marcadores)
preenchidas = preencher_resposta(valida, marcadores)
print("\n=== recomendações preenchidas ===")
for i, rec in enumerate(preenchidas, start=1):
    print(f"{i}. {rec['titulo']}\n   Diagnóstico: {rec['diagnostico']}\n   Ação: {rec['acao']}")
assert preenchidas[0]["diagnostico"] == "Entre agosto e outubro, a sobra teve queda de R$ 1.800,68."
print("OK: resposta válida passa e os marcadores viram valores")


# --- f) Respostas inválidas ---
def rec(**campos):
    base = {"titulo": "Título", "diagnostico": "Diagnóstico.", "acao": "Ação."}
    base.update(campos)
    return base


def resposta_com(primeira):
    return {"recomendacoes": [primeira, rec(), rec()]}


def deve_falhar(resposta, descricao):
    try:
        validar_resposta(resposta, marcadores)
    except ErroValidacao as e:
        print(f"  erro esperado ({descricao}): {e}")
        return
    raise AssertionError(f"era para dar ErroValidacao: {descricao}")


print("\n=== respostas inválidas ===")
deve_falhar(resposta_com(rec(diagnostico="Transporte subiu 37%.")), "dígito")
deve_falhar(resposta_com(rec(diagnostico="Você gastou R$ 1.706,48 com transporte.")), "valor escrito à mão")
deve_falhar(resposta_com(rec(diagnostico="Veja {Transporte.total}.")), "marcador inexistente")
deve_falhar(resposta_com(rec(diagnostico="Veja {Transporte.diferenca")), "marcador sem fechar")
deve_falhar({"recomendacoes": [rec(), rec()]}, "só 2 recomendações")
deve_falhar(resposta_com(rec(acao="")), "acao vazia")
print("OK: respostas inválidas levantam ErroValidacao")
deve_falhar(resposta_com(rec(diagnostico="Transporte subiu trinta e sete por cento.")), "por cento")
deve_falhar(resposta_com(rec(diagnostico="A sobra caiu mais de mil reais.")), "reais")
deve_falhar(resposta_com(rec(diagnostico="O variável é quase o dobro do fixo.")), "dobro")
print("OK: expressões proibidas (por cento, reais, dobro) levantam ErroValidacao")

# --- g) gerar_recomendacoes com Gemini falso (sem API) ---
prompt = montar_prompt(pacote, marcadores)
assert "{diferenca.sobra}" in prompt.split("MARCADORES DISPONÍVEIS")[0], "exemplo literal ausente"
assert "de três meses" in prompt and "{n_meses}" not in prompt and "{lista}" not in prompt
assert "{2026-10.sobra} -> R$ 1.400,46" in prompt
print("OK: prompt r1 (exemplo com chaves literal, 'três' no lugar de {n_meses}, lista no fim)")


def gemini_falso(respostas, prompts, modelos=None):
    def chamar(prompt, modelo):
        prompts.append(prompt)
        if modelos is not None:
            modelos.append(modelo)
        item = respostas[min(len(prompts) - 1, len(respostas) - 1)]
        if isinstance(item, Exception):
            raise item
        return json.dumps(item, ensure_ascii=False)
    return chamar


com_digito = resposta_com(rec(diagnostico="Transporte subiu 37%."))
prompts = []
resultado = gerar_recomendacoes(pacote, chamar=gemini_falso([com_digito, valida], prompts))
assert len(resultado["recomendacoes"]) == 3
assert resultado["tentativas_extras"] == 1
assert resultado["versao_prompt"] == "r1"
assert resultado["recomendacoes"][0]["diagnostico"] == (
    "Entre agosto e outubro, a sobra teve queda de R$ 1.800,68."
)
assert "{diferenca.sobra}" in resultado["resposta_bruta"]["recomendacoes"][0]["diagnostico"]
assert len(prompts) == 2
assert "Sua resposta anterior foi recusada pelo motivo" not in prompts[0]
assert "Sua resposta anterior foi recusada pelo motivo" in prompts[1]
print("OK: resposta recusada + resposta válida -> 3 recomendações, 1 tentativa extra")

try:
    gerar_recomendacoes(pacote, chamar=gemini_falso([com_digito, com_digito], []))
    raise AssertionError("era para dar RuntimeError")
except RuntimeError as e:
    print(f"  erro esperado (duas respostas inválidas): {e}")
print("OK: duas respostas inválidas -> RuntimeError")


class ErroFalso503(Exception):
    code = 503


recomendador.ESPERAS_TENTATIVAS = [0, 0, 0]  # sem esperar de verdade no teste
modelos = []
resultado = gerar_recomendacoes(
    pacote, chamar=gemini_falso([ErroFalso503()] * 4 + [valida], [], modelos)
)
assert resultado["modelo"] == recomendador.MODELO_RESERVA, resultado["modelo"]
assert modelos == [recomendador.MODELO] * 4 + [recomendador.MODELO_RESERVA], modelos
print("OK: erro temporário esgotado -> 1 tentativa com o modelo reserva")
