import os
import time
from collections import Counter

import pandas as pd

from categorizador import VERSAO_PROMPT, categorizar_todos

inicio = time.time()

# Lê o extrato inteiro (id como texto)
df = pd.read_csv("dados/transacoes.csv", dtype={"id": str})
transacoes = df[["id", "descricao", "valor"]].to_dict("records")

estatisticas = {}
resultados = categorizar_todos(
    transacoes,
    estatisticas=estatisticas,
    progresso=lambda atual, total: print(f"Lote {atual}/{total} concluído"),
)

# Salva em resultados/categorias_<versao>.csv
os.makedirs("resultados", exist_ok=True)
saida = pd.DataFrame(resultados)[["id", "categoria", "modelo"]]
saida["versao_prompt"] = VERSAO_PROMPT
caminho = f"resultados/categorias_{VERSAO_PROMPT}.csv"
saida.to_csv(caminho, index=False)

# Só um resumo: nada de listar linha a linha (os rótulos manuais não podem ser influenciados)
print("\n=== RESUMO ===")
print(f"Arquivo salvo em: {caminho}")
print(f"Total de transações: {len(saida)}")
print(f"Número de lotes: {estatisticas['lotes']}")
print(f"Tentativas extras: {estatisticas['tentativas_extras']}")
print("Modelos que responderam (transações):")
for modelo, n in Counter(saida["modelo"]).most_common():
    print(f"  {modelo}: {n}")
print("Quantidade por categoria:")
for categoria, n in Counter(saida["categoria"]).most_common():
    print(f"  {categoria}: {n}")
print(f"Tempo total: {time.time() - inicio:.1f} s")
