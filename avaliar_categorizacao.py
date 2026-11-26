"""Compara os 50 rótulos manuais com as categorias da IA. Não chama a API do Gemini.

Com --gabarito, faz a avaliação secundária contra dados/gabarito.csv (só leitura).
"""

import sys
from pathlib import Path

import pandas as pd

from categorizador import CATEGORIAS

PASTA = Path(__file__).parent
ARQUIVO_ROTULOS = PASTA / "dados" / "avaliacao_50.csv"
ARQUIVO_IA = PASTA / "resultados" / "categorias_v2-regras.csv"
ARQUIVO_SAIDA = PASTA / "resultados" / "avaliacao_v2-regras.csv"
ARQUIVO_GABARITO = PASTA / "dados" / "gabarito.csv"
ARQUIVO_TRANSACOES = PASTA / "dados" / "transacoes.csv"
ARQUIVO_SAIDA_GABARITO = PASTA / "resultados" / "avaliacao_gabarito_v2-regras.csv"

# Recorte secundário: respostas vistas antes de rotular (T001 a T005) e T009 (confiança 0,5)
IDS_FORA_DO_RECORTE = ("T001", "T002", "T003", "T004", "T005", "T009")


def _validar_ids_unicos(tabela, nome):
    repetidos = sorted(set(tabela.loc[tabela["id"].duplicated(), "id"]))
    if repetidos:
        raise ValueError(f"Há id repetido no arquivo {nome}: {', '.join(repetidos)}.")


def _validar_ids_presentes(base, outra, nome_base, nome_outra):
    faltando = sorted(set(base["id"]) - set(outra["id"]))
    if faltando:
        raise ValueError(
            f"Ids {nome_base} que não existem no arquivo {nome_outra}: {', '.join(faltando)}."
        )


def _validar_categorias(tabela, coluna, dono):
    invalidas = tabela[~tabela[coluna].isin(CATEGORIAS)]
    if not invalidas.empty:
        lista = ", ".join(f"{i} ({c!r})" for i, c in zip(invalidas["id"], invalidas[coluna]))
        raise ValueError(f"Categoria {dono} fora da lista de categorias nos ids: {lista}.")


def comparar(rotulos, ia):
    """Junta rótulos e categorias da IA pelo id.

    Devolve as colunas id, descricao, categoria_david, categoria_ia e acertou.
    Ids que só existem no arquivo da IA são ignorados.
    """
    rotulos = rotulos.assign(id=rotulos["id"].astype(str))
    ia = ia.assign(id=ia["id"].astype(str))

    _validar_ids_unicos(rotulos, "dos rótulos")
    _validar_ids_unicos(ia, "da IA")
    _validar_ids_presentes(rotulos, ia, "dos rótulos", "da IA")

    comparacao = rotulos[["id", "descricao", "categoria_david"]].merge(
        ia[["id", "categoria"]].rename(columns={"categoria": "categoria_ia"}),
        on="id",
        how="left",
    )

    _validar_categorias(comparacao, "categoria_david", "do David")
    _validar_categorias(comparacao, "categoria_ia", "da IA")

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


def converter_ambigua(coluna):
    """Converte a marca de ambiguidade (0 ou 1) em False ou True."""
    texto = coluna.astype(str).str.strip()
    invalidos = sorted(set(texto[~texto.isin(["0", "1"])]))
    if invalidos:
        lista = ", ".join(repr(v) for v in invalidos)
        raise ValueError(f"A coluna ambigua do gabarito só aceita 0 ou 1. Valores encontrados: {lista}.")
    return texto == "1"


def comparar_gabarito(gabarito, ia, transacoes):
    """Junta o gabarito, as categorias da IA e as descrições das transações pelo id.

    Devolve as colunas id, descricao, categoria_gabarito, categoria_ia, ambigua,
    acertou e nota. Ids que não estão no gabarito são ignorados.
    """
    gabarito = gabarito.assign(id=gabarito["id"].astype(str))
    ia = ia.assign(id=ia["id"].astype(str))
    transacoes = transacoes.assign(id=transacoes["id"].astype(str))

    _validar_ids_unicos(gabarito, "do gabarito")
    _validar_ids_unicos(ia, "da IA")
    _validar_ids_unicos(transacoes, "das transações")
    _validar_ids_presentes(gabarito, ia, "do gabarito", "da IA")
    _validar_ids_presentes(gabarito, transacoes, "do gabarito", "das transações")

    comparacao = (
        gabarito[["id", "categoria", "ambigua", "nota"]]
        .rename(columns={"categoria": "categoria_gabarito"})
        .merge(transacoes[["id", "descricao"]], on="id", how="left")
        .merge(
            ia[["id", "categoria"]].rename(columns={"categoria": "categoria_ia"}),
            on="id",
            how="left",
        )
    )
    _validar_categorias(comparacao, "categoria_gabarito", "do gabarito")
    _validar_categorias(comparacao, "categoria_ia", "da IA")

    comparacao["ambigua"] = converter_ambigua(comparacao["ambigua"])
    comparacao["nota"] = comparacao["nota"].fillna("")
    comparacao["acertou"] = comparacao["categoria_gabarito"] == comparacao["categoria_ia"]
    colunas = [
        "id", "descricao", "categoria_gabarito", "categoria_ia", "ambigua", "acertou", "nota"
    ]
    return comparacao[colunas]


def acuracia_por_ambiguidade(comparacao):
    """Devolve (acertos, total) das transações ambíguas e das não ambíguas."""
    return {
        "ambiguas": acuracia(comparacao[comparacao["ambigua"]]),
        "nao_ambiguas": acuracia(comparacao[~comparacao["ambigua"]]),
    }


def acuracia_nos_ids(comparacao, ids):
    """Devolve (acertos, total) da IA contra o gabarito só nos ids pedidos."""
    pedidos = pd.DataFrame({"id": [str(i) for i in ids]})
    _validar_ids_unicos(pedidos, "dos rótulos")
    _validar_ids_presentes(pedidos, comparacao, "dos rótulos", "do gabarito")
    return acuracia(comparacao[comparacao["id"].isin(pedidos["id"])])


def comparar_david_gabarito(rotulos, comparacao):
    """Junta os rótulos do David com a comparação do gabarito.

    Devolve as colunas id, descricao, david, gabarito, ia, nota e concorda.
    """
    rotulos = rotulos.assign(id=rotulos["id"].astype(str))
    _validar_ids_unicos(rotulos, "dos rótulos")
    _validar_ids_presentes(rotulos, comparacao, "dos rótulos", "do gabarito")
    _validar_categorias(rotulos, "categoria_david", "do David")

    juntos = rotulos[["id", "categoria_david"]].merge(comparacao, on="id", how="left")
    juntos = juntos.rename(
        columns={"categoria_david": "david", "categoria_gabarito": "gabarito", "categoria_ia": "ia"}
    )
    juntos["concorda"] = juntos["david"] == juntos["gabarito"]
    return juntos[["id", "descricao", "david", "gabarito", "ia", "nota", "concorda"]]


def divergencias(david_gabarito):
    """Só as linhas em que o rótulo do David é diferente do gabarito."""
    colunas = ["id", "descricao", "david", "gabarito", "ia", "nota"]
    return david_gabarito.loc[~david_gabarito["concorda"], colunas].reset_index(drop=True)


def erros_gabarito(comparacao):
    """Só as linhas em que a IA deu uma categoria diferente da do gabarito."""
    linhas = comparacao.loc[~comparacao["acertou"]].rename(
        columns={"categoria_gabarito": "gabarito", "categoria_ia": "ia"}
    )
    return linhas[["id", "descricao", "gabarito", "ia", "ambigua", "nota"]].reset_index(drop=True)


def _formatar_placar(acertos, total):
    porcentagem = f"{100 * acertos / total:.1f}".replace(".", ",")
    return f"{acertos} de {total} ({porcentagem}%)"


def _ja_existe(arquivo=ARQUIVO_SAIDA):
    return (
        f"O arquivo {arquivo.relative_to(PASTA)} já existe e não será sobrescrito. "
        "Se quiser gerar de novo, renomeie ou apague o arquivo antes."
    )


def _imprimir_lista(tabela, vazia):
    print(vazia if tabela.empty else tabela.to_string(index=False))


def avaliar_gabarito():
    """Avaliação secundária: lê os arquivos, imprime os resultados e salva a comparação."""
    if ARQUIVO_SAIDA_GABARITO.exists():
        sys.exit(_ja_existe(ARQUIVO_SAIDA_GABARITO))

    gabarito = pd.read_csv(ARQUIVO_GABARITO, dtype=str)
    ia = pd.read_csv(ARQUIVO_IA, dtype={"id": str})
    transacoes = pd.read_csv(ARQUIVO_TRANSACOES, dtype={"id": str})
    rotulos = pd.read_csv(ARQUIVO_ROTULOS, dtype={"id": str})

    comparacao = comparar_gabarito(gabarito, ia, transacoes)
    grupos = acuracia_por_ambiguidade(comparacao)
    nos_50 = acuracia_nos_ids(comparacao, rotulos["id"])
    david = comparar_david_gabarito(rotulos, comparacao)
    concordancia = (int(david["concorda"].sum()), len(david))

    print(f"(a) IA x gabarito: {_formatar_placar(*acuracia(comparacao))}")
    print(f"(b) Ambíguas: {_formatar_placar(*grupos['ambiguas'])}")
    print(f"    Não ambíguas: {_formatar_placar(*grupos['nao_ambiguas'])}")
    print(f"(c) IA x gabarito nos 50 rotulados: {_formatar_placar(*nos_50)}")
    print(f"(d) Meus rótulos x gabarito nos 50: {_formatar_placar(*concordancia)}")

    print("\n=== (d) divergências entre os meus rótulos e o gabarito ===")
    _imprimir_lista(divergencias(david), "Nenhuma divergência.")

    print("\n=== (e) erros da IA contra o gabarito ===")
    _imprimir_lista(erros_gabarito(comparacao), "Nenhum erro.")

    try:
        comparacao.to_csv(ARQUIVO_SAIDA_GABARITO, index=False, mode="x")
    except FileExistsError:
        sys.exit(_ja_existe(ARQUIVO_SAIDA_GABARITO))
    print(
        f"\nComparação salva em {ARQUIVO_SAIDA_GABARITO.relative_to(PASTA)} "
        f"({len(comparacao)} linhas)."
    )


if __name__ == "__main__":
    if "--gabarito" in sys.argv[1:]:
        avaliar_gabarito()
        sys.exit()

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
