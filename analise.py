"""Cálculos do extrato com pandas. O LLM só categoriza; todo número sai daqui."""

import pandas as pd

# Fatura do cartão duplicaria as compras "COMPRA CARTAO" já listadas; PIX a pessoas e
# aplicações também não são consumo.
CATEGORIAS_FORA_CONSUMO = ["Transferências", "Investimentos"]
CATEGORIA_RENDA = "Renda"
# Consumo = todas as outras categorias.


def _consumo(df):
    """Linhas de consumo: tudo que não é renda nem fora do consumo."""
    fora = CATEGORIAS_FORA_CONSUMO + [CATEGORIA_RENDA]
    return df[~df["categoria"].isin(fora)]


def _reais(valor):
    """Número simples (float) arredondado a 2 casas."""
    return round(float(valor), 2)


def juntar_categorias(df, categorias):
    """Devolve o df com a coluna 'categoria', vinda de uma lista de {"id", "categoria"}."""
    mapa = {str(c["id"]): c["categoria"] for c in categorias}
    resultado = df.copy()
    resultado["categoria"] = resultado["id"].astype(str).map(mapa)

    sem_categoria = resultado.loc[resultado["categoria"].isna(), "id"].astype(str).tolist()
    if sem_categoria:
        mostrados = ", ".join(sem_categoria[:5])
        if len(sem_categoria) > 5:
            mostrados += ", ..."
        raise ValueError(
            f"{len(sem_categoria)} transação(ões) ficaram sem categoria (ids: {mostrados})."
        )
    return resultado


def resumo(df):
    """Dict com renda, consumo, fora_consumo e saldo (renda - consumo), em reais positivos.

    consumo: soma com sinal (estornos abatem as compras), em módulo.
    fora_consumo: só o dinheiro que SAIU em categorias fora do consumo, em módulo.
    """
    renda = df.loc[df["categoria"] == CATEGORIA_RENDA, "valor"].sum()
    consumo = -_consumo(df)["valor"].sum()
    fora = df[df["categoria"].isin(CATEGORIAS_FORA_CONSUMO) & (df["valor"] < 0)]
    fora_consumo = -fora["valor"].sum()
    return {
        "renda": _reais(renda),
        "consumo": _reais(consumo),
        "fora_consumo": _reais(fora_consumo),
        "saldo": _reais(renda - consumo),
    }


def gasto_por_categoria(df):
    """DataFrame (categoria, gasto) só do consumo, do maior para o menor.

    Soma com sinal: estornos positivos abatem as compras da mesma categoria.
    """
    soma = _consumo(df).groupby("categoria")["valor"].sum()
    gasto = (-soma).round(2).rename("gasto").reset_index()
    return gasto.sort_values("gasto", ascending=False).reset_index(drop=True)


def evolucao_mensal(df):
    """DataFrame (mes 'AAAA-MM', renda, consumo), um por mês."""
    mes = df["data"].dt.strftime("%Y-%m")
    renda = df.loc[df["categoria"] == CATEGORIA_RENDA, "valor"].groupby(mes).sum()
    consumo = -_consumo(df)["valor"].groupby(mes).sum()
    meses = sorted(mes.unique())
    resultado = pd.DataFrame(
        {
            "mes": meses,
            "renda": renda.reindex(meses, fill_value=0).round(2).values,
            "consumo": consumo.reindex(meses, fill_value=0).round(2).values,
        }
    )
    return resultado


def maiores_despesas(df, n=10):
    """As n transações de consumo com valor mais negativo."""
    consumo = _consumo(df)
    consumo = consumo[consumo["valor"] < 0]
    colunas = ["id", "data", "descricao", "valor", "categoria"]
    return consumo.nsmallest(n, "valor")[colunas].reset_index(drop=True)


def fora_do_consumo(df):
    """DataFrame (descricao_grupo, total) do que ficou fora do consumo.

    Sempre 4 linhas (Fatura do cartão, PIX enviados, PIX recebidos, Investimentos) e,
    se houver, "Outras transferências". Total = soma COM SINAL do grupo
    (saída negativa, entrada positiva).
    """
    transf = df[df["categoria"] == "Transferências"]
    desc = transf["descricao"].str.upper().str.strip()

    fatura = desc.str.startswith("PAGAMENTO FATURA")
    pix_env = desc.str.startswith("PIX ENVIADO")
    pix_rec = desc.str.startswith("PIX RECEBIDO")
    outras = ~(fatura | pix_env | pix_rec)

    grupos = [
        ("Fatura do cartão", transf.loc[fatura, "valor"].sum()),
        ("PIX enviados", transf.loc[pix_env, "valor"].sum()),
        ("PIX recebidos", transf.loc[pix_rec, "valor"].sum()),
        ("Investimentos", df.loc[df["categoria"] == "Investimentos", "valor"].sum()),
    ]
    total_outras = transf.loc[outras, "valor"].sum()
    if total_outras != 0:
        grupos.append(("Outras transferências", total_outras))

    return pd.DataFrame(
        [{"descricao_grupo": nome, "total": _reais(total)} for nome, total in grupos]
    )
