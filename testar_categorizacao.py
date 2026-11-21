import pandas as pd

from categorizador import categorizar_lote

# Lê só as 5 primeiras linhas (id como texto)
df = pd.read_csv("dados/transacoes.csv", dtype={"id": str}).head(5)

transacoes = df[["id", "descricao", "valor"]].to_dict("records")
resultado = categorizar_lote(transacoes)

# Junta a categoria de volta pela coluna id
categorias = {r["id"]: r["categoria"] for r in resultado}
df["categoria"] = df["id"].map(categorias)

print(df[["id", "descricao", "valor", "categoria"]].to_string(index=False))
