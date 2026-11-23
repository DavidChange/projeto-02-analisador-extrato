"""Testes de recomendador.py. Não chama a API do Gemini."""

import pandas as pd

from analise import juntar_categorias, montar_pacote
from categorizador import ErroValidacao
from extrato import carregar_e_validar
from recomendador import (
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
