"""Compara os 50 rótulos manuais com as categorias da IA. Não chama a API do Gemini."""

import sys
from pathlib import Path

import pandas as pd

from categorizador import CATEGORIAS

PASTA = Path(__file__).parent
ARQUIVO_ROTULOS = PASTA / "dados" / "avaliacao_50.csv"
ARQUIVO_IA = PASTA / "resultados" / "categorias_v2-regras.csv"
ARQUIVO_SAIDA = PASTA / "resultados" / "avaliacao_v2-regras.csv"

# Recorte secundário: respostas vistas antes de rotular (T001 a T005) e T009 (confiança 0,5)
IDS_FORA_DO_RECORTE = ("T001", "T002", "T003", "T004", "T005", "T009")


def comparar(rotulos, ia):
    """Junta rótulos e categorias da IA pelo id.

    Devolve as colunas id, descricao, categoria_david, categoria_ia e acertou.
    Ids que só existem no arquivo da IA são ignorados.
    """
    rotulos = rotulos.assign(id=rotulos["id"].astype(str))
    ia = ia.assign(id=ia["id"].astype(str))

    for tabela, nome in ((rotulos, "dos rótulos"), (ia, "da IA")):
        repetidos = sorted(set(tabela.loc[tabela["id"].duplicated(), "id"]))
        if repetidos:
            raise ValueError(f"Há id repetido no arquivo {nome}: {', '.join(repetidos)}.")

    faltando = sorted(set(rotulos["id"]) - set(ia["id"]))
    if faltando:
        raise ValueError(f"Ids dos rótulos que não existem no arquivo da IA: {', '.join(faltando)}.")

    comparacao = rotulos[["id", "descricao", "categoria_david"]].merge(
        ia[["id", "categoria"]].rename(columns={"categoria": "categoria_ia"}),
        on="id",
        how="left",
    )

    for coluna, dono in (("categoria_david", "do David"), ("categoria_ia", "da IA")):
        invalidas = comparacao[~comparacao[coluna].isin(CATEGORIAS)]
        if not invalidas.empty:
            lista = ", ".join(f"{i} ({c!r})" for i, c in zip(invalidas["id"], invalidas[coluna]))
            raise ValueError(f"Categoria {dono} fora da lista de categorias nos ids: {lista}.")

    comparacao["acertou"] = comparacao["categoria_david"] == comparacao["categoria_ia"]
    return comparacao


def acuracia(comparacao, excluir=()):
    """Devolve (acertos, total), ignorando os ids em excluir."""
    considerados = comparacao[~comparacao["id"].isin(excluir)]
    return int(considerados["acertou"].sum()), len(considerados)


def por_categoria(comparacao):
    """Quantos rótulos e quantos acertos por categoria do David (números absolutos)."""
    tabela = (
        comparacao.groupby("categoria_david")["acertou"]
        .agg(rotulos="size", acertos="sum")
        .reset_index()
        .rename(columns={"categoria_david": "categoria"})
    )
    tabela["acertos"] = tabela["acertos"].astype(int)
    return tabela.sort_values(
        ["rotulos", "categoria"], ascending=[False, True]
    ).reset_index(drop=True)


def erros(comparacao):
    """Só as linhas em que a IA deu uma categoria diferente da do David."""
    colunas = ["id", "descricao", "categoria_david", "categoria_ia"]
    return comparacao.loc[~comparacao["acertou"], colunas].reset_index(drop=True)


def _formatar_placar(acertos, total):
    porcentagem = f"{100 * acertos / total:.1f}".replace(".", ",")
    return f"{acertos} de {total} ({porcentagem}%)"


def _ja_existe():
    return (
        f"O arquivo {ARQUIVO_SAIDA.relative_to(PASTA)} já existe e não será sobrescrito. "
        "Se quiser gerar de novo, renomeie ou apague o arquivo antes."
    )


if __name__ == "__main__":
    if ARQUIVO_SAIDA.exists():
        sys.exit(_ja_existe())

    rotulos = pd.read_csv(ARQUIVO_ROTULOS, dtype={"id": str})
    ia = pd.read_csv(ARQUIVO_IA, dtype={"id": str})
    comparacao = comparar(rotulos, ia)

    print(f"Acertos: {_formatar_placar(*acuracia(comparacao))}")
    recorte = acuracia(comparacao, excluir=IDS_FORA_DO_RECORTE)
    print(f"Recorte sem T001-T005 e sem T009: {_formatar_placar(*recorte)}")

    print("\n=== por categoria (rótulos do David) ===")
    print(por_categoria(comparacao).to_string(index=False))

    print("\n=== erros ===")
    lista_de_erros = erros(comparacao)
    if lista_de_erros.empty:
        print("Nenhum erro.")
    else:
        print(lista_de_erros.to_string(index=False))

    try:
        # mode="x" só cria arquivo novo: nunca sobrescreve
        comparacao.to_csv(ARQUIVO_SAIDA, index=False, mode="x")
    except FileExistsError:
        sys.exit(_ja_existe())
    print(f"\nComparação salva em {ARQUIVO_SAIDA.relative_to(PASTA)} ({len(comparacao)} linhas).")
