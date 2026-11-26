"""Testes de avaliar_categorizacao.py. Só dados inventados; não lê arquivos nem chama a API."""

import pandas as pd

from avaliar_categorizacao import acuracia, comparar, erros, por_categoria

# --- Exemplo inventado: 4 rótulos, 3 acertos (o erro é o B4) ---
rotulos = pd.DataFrame(
    {
        "id": ["B1", "B2", "B3", "B4"],
        "descricao": ["MERCADO UM", "MERCADO DOIS", "ONIBUS", "CINEMA"],
        "categoria_david": ["Mercado", "Mercado", "Transporte", "Lazer e assinaturas"],
    }
)
ia = pd.DataFrame(
    {
        "id": ["B4", "B3", "B2", "B1"],  # ordem trocada de propósito
        "categoria": ["Outros", "Transporte", "Mercado", "Mercado"],
    }
)
comparacao = comparar(rotulos, ia)

assert list(comparacao.columns) == [
    "id", "descricao", "categoria_david", "categoria_ia", "acertou"
]
assert list(comparacao["id"]) == ["B1", "B2", "B3", "B4"]
assert list(comparacao["acertou"]) == [True, True, True, False]
assert acuracia(comparacao) == (3, 4)
print("OK: 4 rótulos com 3 acertos -> (3, 4)")

assert acuracia(comparacao, excluir=["B1"]) == (2, 3)
print("OK: excluir um id que acertou -> (2, 3)")


# --- Entradas inválidas ---
def deve_falhar(r, i, trecho):
    try:
        comparar(r, i)
    except ValueError as e:
        assert trecho in str(e), str(e)
        print(f"  erro esperado: {e}")
        return
    raise AssertionError(f"era para dar ValueError: {trecho}")


deve_falhar(rotulos, ia[ia["id"] != "B2"], "não existem no arquivo da IA")
print("OK: id do rótulo ausente no arquivo da IA -> ValueError")

deve_falhar(pd.concat([rotulos, rotulos.iloc[[0]]]), ia, "id repetido no arquivo dos rótulos")
print("OK: id repetido nos rótulos -> ValueError")

deve_falhar(rotulos, pd.concat([ia, ia.iloc[[0]]]), "id repetido no arquivo da IA")
print("OK: id repetido no arquivo da IA -> ValueError")

david_invalido = rotulos.assign(
    categoria_david=["Feira", "Mercado", "Transporte", "Lazer e assinaturas"]
)
deve_falhar(david_invalido, ia, "Categoria do David")
print("OK: categoria inválida do David -> ValueError")

ia_invalida = ia.assign(categoria=["Outros", "Transporte", "Mercado", "Feira"])
deve_falhar(rotulos, ia_invalida, "Categoria da IA")
print("OK: categoria inválida da IA -> ValueError")

# --- Linhas extras no arquivo da IA ---
ia_com_extras = pd.concat(
    [ia, pd.DataFrame({"id": ["B8", "B9"], "categoria": ["Saúde", "Renda"]})]
)
com_extras = comparar(rotulos, ia_com_extras)
assert len(com_extras) == 4
assert acuracia(com_extras) == (3, 4)
print("OK: linhas extras no arquivo da IA são ignoradas")

# --- por_categoria e erros ---
tabela = por_categoria(comparacao)
assert list(tabela.columns) == ["categoria", "rotulos", "acertos"]
assert tabela.values.tolist() == [
    ["Mercado", 2, 2],
    ["Lazer e assinaturas", 1, 0],
    ["Transporte", 1, 1],
]
print("OK: por_categoria com os números certos, maior primeiro")

lista = erros(comparacao)
assert list(lista.columns) == ["id", "descricao", "categoria_david", "categoria_ia"]
assert lista.values.tolist() == [["B4", "CINEMA", "Lazer e assinaturas", "Outros"]]
print("OK: erros devolve só a linha errada")
