"""Cálculos do extrato com pandas. O LLM só categoriza; todo número sai daqui."""

import pandas as pd

# Fatura do cartão duplicaria as compras "COMPRA CARTAO" já listadas; PIX a pessoas e
# aplicações também não são consumo.
CATEGORIA_INVESTIMENTOS = "Investimentos"
CATEGORIAS_FORA_CONSUMO = ["Transferências", CATEGORIA_INVESTIMENTOS]
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
    """Número simples (float) arredondado a 2 casas (sem o -0.0)."""
    return round(float(valor), 2) + 0.0


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
        (
            CATEGORIA_INVESTIMENTOS,
            df.loc[df["categoria"] == CATEGORIA_INVESTIMENTOS, "valor"].sum(),
        ),
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


def _categoria_mais_frequente(grupo):
    """Categoria mais frequente do grupo; no empate, a do mês mais recente entre as empatadas."""
    contagem = grupo["categoria"].value_counts()
    empatadas = set(contagem[contagem == contagem.max()].index)
    do_ultimo_para_o_primeiro = grupo.sort_values("mes", ascending=False)["categoria"]
    return next(c for c in do_ultimo_para_o_primeiro if c in empatadas)


def _recorrentes(linhas, meses):
    """Descrições recorrentes: DataFrame (chave, categoria, media, variacao), valores em módulo.

    'linhas' precisa das colunas mes, chave, categoria e valor. Recorrente = aparece exatamente
    uma vez em cada mês de 'meses' e (maior - menor) / média <= LIMITE_VARIACAO_FIXO.
    media e variacao saem sem arredondar.
    """
    resultado = []
    for chave, grupo in linhas.groupby("chave"):
        if len(grupo) != len(meses) or grupo["mes"].nunique() != len(meses):
            continue
        valores = grupo["valor"].abs()
        media = valores.mean()
        variacao = (valores.max() - valores.min()) / media
        if variacao <= LIMITE_VARIACAO_FIXO:
            resultado.append(
                {
                    "chave": chave,
                    "categoria": _categoria_mais_frequente(grupo),
                    "media": media,
                    "variacao": variacao,
                }
            )
    return pd.DataFrame(resultado, columns=["chave", "categoria", "media", "variacao"])


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

    rec = _recorrentes(_saidas_consumo(df), meses)
    resultado = pd.DataFrame(
        {
            "descricao": rec["chave"],
            "categoria": rec["categoria"],
            "gasto_medio": [_reais(m) for m in rec["media"]],
            "variacao": [round(float(v), 3) for v in rec["variacao"]],
        },
        columns=colunas,
    )
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


def renda_fixa_extra_mensal(df):
    """DataFrame (mes, renda_fixa, renda_extra), um por mês, em reais positivos.

    renda_fixa = entradas da categoria Renda cuja descrição é recorrente (uma vez por mês em
    todos os meses, variação de até LIMITE_VARIACAO_FIXO), como o salário.
    renda_extra = renda do mês (como em evolucao_mensal) - renda_fixa.
    Com menos de MESES_MINIMOS_FIXO meses, devolve vazio.
    """
    colunas = ["mes", "renda_fixa", "renda_extra"]
    meses = _meses_do_extrato(df)
    if len(meses) < MESES_MINIMOS_FIXO:
        return pd.DataFrame(columns=colunas)

    entradas = df[(df["categoria"] == CATEGORIA_RENDA) & (df["valor"] > 0)].copy()
    entradas["mes"] = entradas["data"].dt.strftime("%Y-%m")
    entradas["chave"] = entradas["descricao"].str.upper().str.strip()
    rec = _recorrentes(entradas, meses)
    fixas = entradas[entradas["chave"].isin(rec["chave"])]
    fixa = fixas["valor"].groupby(fixas["mes"]).sum().reindex(meses, fill_value=0).round(2).values

    renda = evolucao_mensal(df)["renda"].values
    return pd.DataFrame(
        {"mes": meses, "renda_fixa": fixa, "renda_extra": (renda - fixa).round(2)}
    )


def variavel_por_categoria_mensal(df):
    """DataFrame (categoria, uma coluna por mês 'AAAA-MM', diferenca) do consumo variável.

    Consumo variável = linhas de consumo (estornos abatem) cujas descrições NÃO estão em
    gastos_fixos(df). Reais positivos; mês sem gasto = 0.00. diferenca = último mês - primeiro
    mês, da maior para a menor. Com menos de MESES_MINIMOS_FIXO meses, devolve só
    categoria e diferenca, vazio.
    """
    meses = _meses_do_extrato(df)
    if len(meses) < MESES_MINIMOS_FIXO:
        return pd.DataFrame(columns=["categoria", "diferenca"])

    consumo = _consumo(df).copy()
    consumo["mes"] = consumo["data"].dt.strftime("%Y-%m")
    consumo["chave"] = consumo["descricao"].str.upper().str.strip()
    variavel = consumo[~consumo["chave"].isin(gastos_fixos(df)["descricao"])]

    tabela = -variavel.pivot_table(
        index="categoria", columns="mes", values="valor", aggfunc="sum", fill_value=0
    )
    tabela = tabela.reindex(columns=meses, fill_value=0).round(2)
    tabela["diferenca"] = (tabela[meses[-1]] - tabela[meses[0]]).round(2)
    tabela = tabela.sort_values("diferenca", ascending=False, kind="stable")
    tabela.columns.name = None
    return tabela.reset_index()


def montar_pacote(df):
    """Dict só com números calculados pelo pandas: o ÚNICO conteúdo que vai para o LLM.

    Não leva nenhuma transação individual: só totais, valores por mês, variação entre o
    primeiro e o último mês, gasto variável por categoria e a lista de gastos fixos
    (descrição e média). Todos os números são float do Python, com 2 casas.
    Com menos de MESES_MINIMOS_FIXO meses, levanta ValueError.
    """
    meses = _meses_do_extrato(df)
    if len(meses) < MESES_MINIMOS_FIXO:
        raise ValueError(
            f"São necessários pelo menos {MESES_MINIMOS_FIXO} meses de extrato "
            "para gerar recomendações."
        )

    mensal = (
        evolucao_mensal(df)
        .merge(renda_fixa_extra_mensal(df), on="mes")
        .merge(fixo_variavel_mensal(df), on="mes")
    )
    mensal["sobra"] = (mensal["renda"] - mensal["consumo"]).round(2)
    campos = ["renda", "renda_fixa", "renda_extra", "consumo", "fixo", "variavel", "sobra"]

    lista_mensal = [
        {"mes": linha["mes"], **{c: _reais(linha[c]) for c in campos}}
        for _, linha in mensal.iterrows()
    ]
    diferenca = {
        c: _reais(mensal[c].iloc[-1] - mensal[c].iloc[0]) for c in campos
    }

    r = resumo(df)
    aplicacoes = (df["categoria"] == CATEGORIA_INVESTIMENTOS) & (df["valor"] < 0)
    investimentos = df.loc[aplicacoes, "valor"].sum()
    por_categoria = [
        {
            "categoria": linha["categoria"],
            **{m: _reais(linha[m]) for m in meses},
            "diferenca": _reais(linha["diferenca"]),
        }
        for _, linha in variavel_por_categoria_mensal(df).iterrows()
    ]
    fixos = [
        {"descricao": linha["descricao"], "gasto_medio": _reais(linha["gasto_medio"])}
        for _, linha in gastos_fixos(df).iterrows()
    ]
    return {
        "meses": meses,
        "mensal": lista_mensal,
        "diferenca_primeiro_ultimo_mes": diferenca,
        "totais": {
            "renda": r["renda"],
            "consumo": r["consumo"],
            "sobra": r["saldo"],
            "investimentos_aplicados": _reais(-investimentos),
        },
        "variavel_por_categoria": por_categoria,
        "gastos_fixos": fixos,
    }
