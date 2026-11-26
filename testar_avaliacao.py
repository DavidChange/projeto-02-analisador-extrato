"""Testes de avaliar_categorizacao.py. Só dados inventados; não lê arquivos nem chama a API."""

import pandas as pd

from avaliar_categorizacao import (
    acuracia,
    acuracia_nos_ids,
    acuracia_por_ambiguidade,
    comparar,
    comparar_david_gabarito,
    comparar_gabarito,
    divergencias,
    erros,
    erros_gabarito,
    por_categoria,
)

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

# --- Avaliação secundária (gabarito inventado aqui, não lê dados/gabarito.csv) ---
gabarito = pd.DataFrame(
    {
        "id": ["B1", "B2", "B3", "B4", "B5", "B6"],
        "categoria": [
            "Mercado", "Alimentação fora", "Transporte", "Outros", "Saúde", "Renda"
        ],
        "ambigua": ["0", "1", "0", "1", "0", "1"],
        "nota": [None, "regra B2", None, "regra B4", None, "regra B6"],
    }
)
ia_gabarito = pd.DataFrame(
    {
        "id": ["B6", "B5", "B4", "B3", "B2", "B1", "B9"],  # B9 não está no gabarito
        "categoria": [
            "Transferências", "Saúde", "Outros", "Transporte", "Mercado", "Mercado", "Renda"
        ],
    }
)
transacoes = pd.DataFrame(
    {
        "id": ["B1", "B2", "B3", "B4", "B5", "B6", "B9"],
        "descricao": ["D1", "D2", "D3", "D4", "D5", "D6", "D9"],
    }
)
contra = comparar_gabarito(gabarito, ia_gabarito, transacoes)

assert list(contra.columns) == [
    "id", "descricao", "categoria_gabarito", "categoria_ia", "ambigua", "acertou", "nota"
]
assert contra["ambigua"].tolist() == [False, True, False, True, False, True]
assert contra["ambigua"].dtype == bool
assert acuracia(contra) == (4, 6)
print("OK: (a) IA x gabarito -> (4, 6)")

grupos = acuracia_por_ambiguidade(contra)
assert grupos == {"ambiguas": (1, 3), "nao_ambiguas": (3, 3)}, grupos
print("OK: (b) ambíguas (1, 3) e não ambíguas (3, 3)")

assert acuracia_nos_ids(contra, rotulos["id"]) == (3, 4)
print("OK: (c) IA x gabarito só nos 4 ids rotulados -> (3, 4)")

david = comparar_david_gabarito(rotulos, contra)
assert (int(david["concorda"].sum()), len(david)) == (2, 4)
lista = divergencias(david)
assert list(lista.columns) == ["id", "descricao", "david", "gabarito", "ia", "nota"]
assert lista.values.tolist() == [
    ["B2", "D2", "Mercado", "Alimentação fora", "Mercado", "regra B2"],
    ["B4", "D4", "Lazer e assinaturas", "Outros", "Outros", "regra B4"],
]
print("OK: (d) meus rótulos x gabarito -> (2, 4), com 2 divergências")

lista = erros_gabarito(contra)
assert list(lista.columns) == ["id", "descricao", "gabarito", "ia", "ambigua", "nota"]
assert lista["id"].tolist() == ["B2", "B6"]
assert lista["nota"].tolist() == ["regra B2", "regra B6"]
print("OK: (e) erros contra o gabarito, com a nota")


def deve_dar_erro(funcao, trecho):
    try:
        funcao()
    except ValueError as e:
        assert trecho in str(e), str(e)
        print(f"  erro esperado: {e}")
        return
    raise AssertionError(f"era para dar ValueError: {trecho}")


marca_invalida = gabarito.assign(ambigua=["0", "1", "0", "sim", "0", "1"])
deve_dar_erro(
    lambda: comparar_gabarito(marca_invalida, ia_gabarito, transacoes), "só aceita 0 ou 1"
)
print("OK: ambigua diferente de 0 ou 1 -> ValueError")

deve_dar_erro(
    lambda: comparar_gabarito(gabarito, ia_gabarito[ia_gabarito["id"] != "B5"], transacoes),
    "não existem no arquivo da IA",
)
print("OK: id do gabarito ausente no arquivo da IA -> ValueError")

deve_dar_erro(
    lambda: acuracia_nos_ids(contra, ["B1", "B8"]), "não existem no arquivo do gabarito"
)
print("OK: id rotulado ausente no gabarito -> ValueError")
