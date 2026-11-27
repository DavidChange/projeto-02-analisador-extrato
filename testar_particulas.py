"""Testes das partículas, com os dados de exemplo. Não chama a API."""

import json

import pandas as pd

from analise import gasto_por_categoria, juntar_categorias, resumo
from extrato import carregar_e_validar
from particulas import html_particulas, pontos_por_categoria, valor_por_ponto

df, erros = carregar_e_validar("dados/transacoes.csv")
assert not erros, erros
categorias = pd.read_csv("resultados/categorias_v2-regras.csv", dtype={"id": str})
df = juntar_categorias(df, categorias.to_dict("records"))
gastos = gasto_por_categoria(df)

# Exemplo: R$ 17.748,65 de consumo -> R$ 50 por ponto e 356 pontos
consumo = resumo(df)["consumo"]
assert consumo == 17748.65, consumo
valor = valor_por_ponto(consumo)
assert valor == 50, valor
pontos = pontos_por_categoria(gastos, valor)
assert sum(pontos.values()) == 356, pontos
print("OK: exemplo -> R$ 50 por ponto, 356 pontos")

assert valor_por_ponto(100_000) == 500
print("OK: R$ 100.000 -> R$ 500 por ponto")

# Limites: exatamente 400 pontos ainda vale; acima do maior valor, fica o maior
assert valor_por_ponto(4000) == 10
assert valor_por_ponto(4000.01) == 20
assert valor_por_ponto(10_000_000) == 5000
print("OK: limite de 400 pontos e total muito alto")

pequenos = pd.DataFrame({"categoria": ["A", "B", "C"], "gasto": [0.5, 0.0, -30.0]})
assert pontos_por_categoria(pequenos, 50) == {"A": 1, "B": 0, "C": 0}
print("OK: mínimo de 1 ponto só para gasto maior que zero")

pagina = html_particulas(gastos, "01/08/2026 a 31/10/2026", consumo)
for categoria in gastos["categoria"]:
    assert categoria in pagina, categoria
print(f"OK: o HTML contém os nomes das {len(gastos)} categorias")

for trecho in [
    "R$ 17.748,65 de consumo — 01/08/2026 a 31/10/2026",
    "Cada ponto são R$&nbsp;50.",
    "cada ponto vale R$&nbsp;50: são 356 pontos, com",
    "R$ 6.072,37",
    "#ff7a4d",
]:
    assert trecho in pagina, trecho
for marcador in ["__TOTAL__", "__PERIODO__", "__VALOR__", "__PONTOS__", "__DADOS__"]:
    assert marcador not in pagina, marcador
print("OK: textos, valores em reais e marcadores todos trocados")

# O rótulo e o valor por ponto vêm do total recebido, não da soma dos gastos
pagina = html_particulas(gastos, "x", 100_000)
assert "R$ 100.000,00 de consumo" in pagina
assert "Cada ponto são R$&nbsp;500." in pagina
print("OK: o HTML usa o total recebido")

assert "Cada ponto são R$&nbsp;1.000." in html_particulas(gastos, "x", 300_000)
print("OK: valor por ponto sem centavos, com separador de milhar")

# Categoria fora da lista fica cinza, e nenhum texto vira HTML ou código
nomes = ["</script><b>", "</SCRIPT ><img src=x onerror=alert(1)>", "<!--", 'aspas " \\ \'', "__PERIODO__"]
estranhas = pd.DataFrame({"categoria": nomes, "gasto": [500.0, 400.0, 300.0, 200.0, 100.0]})
periodo = '<img src=x onerror="alert(1)"> & __DADOS__'
pagina = html_particulas(estranhas, periodo, 1500.0)
assert "#8a8890" in pagina
assert pagina.lower().count("<script") == 1 and pagina.lower().count("</script") == 1
assert "<img" not in pagina and "<b>" not in pagina and "<!--" not in pagina
assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; __DADOS__" in pagina
# Os nomes chegam ao JavaScript exatamente como foram escritos
dados = pagina.split("const GRUPOS = ", 1)[1].split(";\nconst RAIO", 1)[0]
assert [grupo["nome"] for grupo in json.loads(dados)] == nomes
print("OK: categoria fora da lista em cinza; nomes e período protegidos")
