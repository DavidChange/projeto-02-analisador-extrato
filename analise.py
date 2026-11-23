"""Cálculos do extrato com pandas. O LLM só categoriza; todo número sai daqui."""

import pandas as pd

# Fatura do cartão duplicaria as compras "COMPRA CARTAO" já listadas; PIX a pessoas e
# aplicações também não são consumo.
CATEGORIAS_FORA_CONSUMO = ["Transferências", "Investimentos"]
CATEGORIA_RENDA = "Renda"
# Consumo = todas as outras categorias.

# Gasto fixo: aparece uma vez por mês em todos os meses e varia até 50%.
LIMITE_VARIACAO_FIXO = 0.5
MESES_MINIMOS_FIXO = 3


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
    """Dict com renda, consumo, saidas_fora_consumo e saldo (renda - consumo), em reais positivos.

    consumo: soma com sinal (estornos abatem as compras), em módulo.
    saidas_fora_consumo: soma só das SAÍDAS de Transferências e Investimentos, em valor
        positivo. NÃO é o mesmo que somar fora_do_consumo(): aquela tem sinal e inclui as
        entradas (como os PIX recebidos).
    """
    renda = df.loc[df["categoria"] == CATEGORIA_RENDA, "valor"].sum()
    consumo = -_consumo(df)["valor"].sum()
    fora = df[df["categoria"].isin(CATEGORIAS_FORA_CONSUMO) & (df["valor"] < 0)]
    saidas_fora_consumo = -fora["valor"].sum()
    return {
        "renda": _reais(renda),
        "consumo": _reais(consumo),
        "saidas_fora_consumo": _reais(saidas_fora_consumo),
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


def _meses_do_extrato(df):
    """Lista ordenada dos meses distintos (AAAA-MM) do df inteiro."""
    return sorted(df["data"].dt.strftime("%Y-%m").unique())


def _saidas_consumo(df):
    """Saídas de consumo (valor < 0), com 'mes' e 'chave' (descrição em maiúsculas, sem espaços nas pontas)."""
    saidas = _consumo(df)
    saidas = saidas[saidas["valor"] < 0].copy()
    saidas["mes"] = saidas["data"].dt.strftime("%Y-%m")
    saidas["chave"] = saidas["descricao"].str.upper().str.strip()
    return saidas


def gastos_fixos(df):
    """DataFrame (descricao, categoria, gasto_medio, variacao) dos gastos fixos, do maior para o menor.

    Fixo = saída de consumo cuja descrição aparece exatamente uma vez em cada mês do extrato
    (meses do df inteiro) e com variacao = (maior - menor) / média <= LIMITE_VARIACAO_FIXO.
    gasto_medio em reais positivos. Com menos de MESES_MINIMOS_FIXO meses, devolve vazio.
    """
    colunas = ["descricao", "categoria", "gasto_medio", "variacao"]
    meses = _meses_do_extrato(df)
    if len(meses) < MESES_MINIMOS_FIXO:
        return pd.DataFrame(columns=colunas)

    saidas = _saidas_consumo(df)
    linhas = []
    for chave, grupo in saidas.groupby("chave"):
        if len(grupo) != len(meses) or grupo["mes"].nunique() != len(meses):
            continue
        gastos = -grupo["valor"]
        media = gastos.mean()
        variacao = (gastos.max() - gastos.min()) / media
        if variacao <= LIMITE_VARIACAO_FIXO:
            linhas.append(
                {
                    "descricao": chave,
                    "categoria": grupo["categoria"].iloc[0],
                    "gasto_medio": _reais(media),
                    "variacao": round(float(variacao), 3),
                }
            )
    resultado = pd.DataFrame(linhas, columns=colunas)
    return resultado.sort_values("gasto_medio", ascending=False).reset_index(drop=True)


def fixo_variavel_mensal(df):
    """DataFrame (mes, fixo, variavel), um por mês, em reais positivos.

    fixo = saídas do mês cujas descrições estão em gastos_fixos(df).
    variavel = consumo do mês (como em evolucao_mensal, estornos abatem) - fixo; assim
    fixo + variavel = consumo. Com menos de MESES_MINIMOS_FIXO meses, devolve vazio.
    """
    colunas = ["mes", "fixo", "variavel"]
    if len(_meses_do_extrato(df)) < MESES_MINIMOS_FIXO:
        return pd.DataFrame(columns=colunas)

    mensal = evolucao_mensal(df)
    saidas = _saidas_consumo(df)
    saidas_fixas = saidas[saidas["chave"].isin(gastos_fixos(df)["descricao"])]
    fixo = (-saidas_fixas["valor"]).groupby(saidas_fixas["mes"]).sum()
    fixo = fixo.reindex(mensal["mes"], fill_value=0).round(2).values
    return pd.DataFrame(
        {
            "mes": mensal["mes"],
            "fixo": fixo,
            "variavel": (mensal["consumo"].values - fixo).round(2),
        }
    )
