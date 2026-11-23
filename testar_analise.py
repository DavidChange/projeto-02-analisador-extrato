import pandas as pd

from analise import (
    evolucao_mensal,
    fixo_variavel_mensal,
    fora_do_consumo,
    gasto_por_categoria,
    gastos_fixos,
    juntar_categorias,
    maiores_despesas,
    resumo,
)
from extrato import carregar_e_validar

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)
pd.set_option("display.max_colwidth", 60)

# --- a) Dados de exemplo + categorias já geradas ---
df, erros = carregar_e_validar("dados/transacoes.csv")
assert not erros, erros
categorias = pd.read_csv("resultados/categorias_v2-regras.csv", dtype={"id": str})
df = juntar_categorias(df, categorias.to_dict("records"))

print("=== resumo ===")
r = resumo(df)
for chave, valor in r.items():
    print(f"{chave}: R$ {valor:,.2f}")

print("\n=== gasto_por_categoria ===")
gastos = gasto_por_categoria(df)
print(gastos.to_string(index=False))

print("\n=== evolucao_mensal ===")
print(evolucao_mensal(df).to_string(index=False))

print("\n=== maiores_despesas (10) ===")
print(maiores_despesas(df).to_string(index=False))

print("\n=== fora_do_consumo ===")
print(fora_do_consumo(df).to_string(index=False))

# Conferências de coerência
assert abs(gastos["gasto"].sum() - r["consumo"]) < 0.01, "gasto por categoria != consumo"
assert abs(evolucao_mensal(df)["consumo"].sum() - r["consumo"]) < 0.01, "mensal != consumo"
assert abs(evolucao_mensal(df)["renda"].sum() - r["renda"]) < 0.01, "mensal != renda"
print("\nConferências de coerência: OK")

# --- b) Teste mínimo com 3 linhas inventadas ---
mini = pd.DataFrame(
    {
        "id": ["A1", "A2", "A3", "A4", "A5"],
        "data": pd.to_datetime(
            ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"]
        ),
        "descricao": ["COMPRA X", "ESTORNO X", "SALARIO Y", "PIX RECEBIDO TESTE", "PIX ENVIADO TESTE"],
        "valor": [-100.0, 30.0, 500.0, 200.0, -50.0],
    }
)
mini = juntar_categorias(
    mini,
    [
        {"id": "A1", "categoria": "Mercado"},
        {"id": "A2", "categoria": "Mercado"},
        {"id": "A3", "categoria": "Renda"},
        {"id": "A4", "categoria": "Transferências"},
        {"id": "A5", "categoria": "Transferências"},
    ],
)
gasto_mercado = gasto_por_categoria(mini).set_index("categoria").loc["Mercado", "gasto"]
assert gasto_mercado == 70, gasto_mercado
# Só o PIX enviado (-50) conta como saída fora do consumo; transferências não mexem na sobra
assert resumo(mini) == {"renda": 500.0, "consumo": 70.0,
                        "saidas_fora_consumo": 50.0, "saldo": 430.0}

# fora_do_consumo() tem sinal: PIX recebido positivo, PIX enviado negativo
fora_mini = fora_do_consumo(mini).set_index("descricao_grupo")["total"]
assert fora_mini["PIX recebidos"] == 200.0, fora_mini["PIX recebidos"]
assert fora_mini["PIX enviados"] == -50.0, fora_mini["PIX enviados"]

# id sem categoria deve dar erro em português
try:
    juntar_categorias(mini, [{"id": "A1", "categoria": "Mercado"}])
    raise AssertionError("era para dar ValueError")
except ValueError as e:
    print("Erro esperado:", e)

print("Teste mínimo (compra -100 + estorno +30 = gasto 70): OK")

# --- c) Gasto fixo x variável, com as categorias da IA ---
print("\n=== gastos_fixos ===")
print(gastos_fixos(df).to_string(index=False))

print("\n=== fixo_variavel_mensal ===")
fv = fixo_variavel_mensal(df)
print(fv.to_string(index=False))

evol = evolucao_mensal(df)
for i in range(len(evol)):
    soma_mes = fv["fixo"].iloc[i] + fv["variavel"].iloc[i]
    assert abs(soma_mes - evol["consumo"].iloc[i]) < 0.01, "fixo + variável != consumo do mês"
assert abs((fv["fixo"] + fv["variavel"]).sum() - r["consumo"]) < 0.01, "fixo + variável != consumo total"
print("Fixo + variável = consumo (por mês e no total): OK")

# --- d) Mini-df de 3 meses para o critério de fixo ---
def linha(i, data, descricao, valor, cat):
    return {"id": f"F{i}", "data": data, "descricao": descricao, "valor": valor, "categoria": cat}

meses3 = ["2026-01-10", "2026-02-10", "2026-03-10"]
linhas = []
n = 0
def add(data, descricao, valor, cat):
    global n
    n += 1
    linhas.append(linha(n, pd.Timestamp(data), descricao, valor, cat))

for m in meses3:
    add(m, "ALUGUEL", -1000.0, "Moradia e contas")
    add(m, "SALARIO", 3000.0, "Renda")
    add(m, "UBER", -15.0, "Transporte")
    add(m, "UBER", -15.0, "Transporte")
for m, luz, cafe in zip(meses3, [-100.0, -120.0, -140.0], [-10.0, -20.0, -30.0]):
    add(m, "LUZ", luz, "Moradia e contas")
    add(m, "CAFE", cafe, "Alimentação fora")
add("2026-03-15", "ESTORNO UBER", 15.0, "Transporte")
add("2026-01-20", "PIX ENVIADO JOAO", -200.0, "Transferências")
mini3 = pd.DataFrame(linhas)

fixos3 = gastos_fixos(mini3)
assert fixos3["descricao"].tolist() == ["ALUGUEL", "LUZ"], fixos3
assert fixos3["gasto_medio"].tolist() == [1000.0, 120.0], fixos3
assert fixos3["variacao"].tolist() == [0.0, 0.333], fixos3
fv3 = fixo_variavel_mensal(mini3)
assert fv3["fixo"].tolist() == [1100.0, 1120.0, 1140.0], fv3
assert fv3["variavel"].tolist() == [40.0, 50.0, 45.0], fv3
print("Mini-df de 3 meses (fixo = ALUGUEL e LUZ; variável = 40, 50, 45): OK")

# --- e) Mini-df com só 2 meses: não separa ---
mini2 = mini3[mini3["data"] < "2026-03-01"]
assert gastos_fixos(mini2).empty
assert list(gastos_fixos(mini2).columns) == ["descricao", "categoria", "gasto_medio", "variacao"]
assert fixo_variavel_mensal(mini2).empty
assert list(fixo_variavel_mensal(mini2).columns) == ["mes", "fixo", "variavel"]
print("Mini-df de 2 meses (vazio): OK")
