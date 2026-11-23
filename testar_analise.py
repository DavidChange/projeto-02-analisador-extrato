import pandas as pd

from analise import (
    evolucao_mensal,
    fora_do_consumo,
    gasto_por_categoria,
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
