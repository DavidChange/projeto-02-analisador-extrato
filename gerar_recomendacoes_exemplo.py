"""Gera as recomendações do extrato de exemplo com o Gemini (UMA chamada real; gasta cota)."""

import json

import pandas as pd

from analise import juntar_categorias, montar_pacote
from extrato import carregar_e_validar
from recomendador import gerar_recomendacoes

df, erros = carregar_e_validar("dados/transacoes.csv")
assert not erros, erros
categorias = pd.read_csv("resultados/categorias_v2-regras.csv", dtype={"id": str})
df = juntar_categorias(df, categorias.to_dict("records"))

resultado = gerar_recomendacoes(montar_pacote(df))

for i, rec in enumerate(resultado["recomendacoes"], start=1):
    print(f"{i}. {rec['titulo']}")
    print(f"   Diagnóstico: {rec['diagnostico']}")
    print(f"   Ação: {rec['acao']}\n")
print(f"Modelo: {resultado['modelo']}")
print(f"Versão do prompt: {resultado['versao_prompt']}")
print(f"Tentativas extras: {resultado['tentativas_extras']}")

saida = {
    "versao_prompt": resultado["versao_prompt"],
    "modelo": resultado["modelo"],
    "tentativas_extras": resultado["tentativas_extras"],
    "resposta_bruta": resultado["resposta_bruta"],
    "recomendacoes": resultado["recomendacoes"],
}
with open("resultados/recomendacoes_r1.json", "w", encoding="utf-8") as f:
    json.dump(saida, f, ensure_ascii=False, indent=2)
print("Salvo em resultados/recomendacoes_r1.json")
