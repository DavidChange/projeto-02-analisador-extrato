import pandas as pd

COLUNAS_OBRIGATORIAS = ["id", "data", "descricao", "valor"]
MAX_LINHAS_NA_MENSAGEM = 5  # evita mensagens enormes se o arquivo tiver muitos erros


def _linhas_texto(indices):
    """Transforma índices do DataFrame em números de linha do arquivo (linha 1 = cabeçalho)."""
    linhas = [str(i + 2) for i in indices]
    texto = ", ".join(linhas[:MAX_LINHAS_NA_MENSAGEM])
    if len(linhas) > MAX_LINHAS_NA_MENSAGEM:
        texto += f" e mais {len(linhas) - MAX_LINHAS_NA_MENSAGEM}"
    return texto


def carregar_e_validar(arquivo):
    """Lê um CSV e valida. Retorna (dataframe, lista_de_erros)."""
    erros = []

    # Lê tudo como texto para validar nós mesmos
    try:
        df = pd.read_csv(arquivo, dtype=str)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(), ["O arquivo está vazio."]
    except Exception as e:
        return pd.DataFrame(), [f"Não foi possível ler o arquivo como CSV: {e}"]

    # Colunas obrigatórias (se faltar alguma, não dá para validar o resto)
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltando:
        nomes = ", ".join(f'"{c}"' for c in faltando)
        return df, [f"Faltam colunas obrigatórias: {nomes}."]

    if df.empty:
        return df, ["O arquivo não tem nenhuma transação."]

    # Descrição não pode ser vazia
    vazias = df.index[df["descricao"].isna() | (df["descricao"].str.strip() == "")]
    if len(vazias) > 0:
        erros.append(f'Coluna "descricao" vazia na(s) linha(s): {_linhas_texto(vazias)}.')

    # Data no formato AAAA-MM-DD
    datas = pd.to_datetime(df["data"], format="%Y-%m-%d", errors="coerce")
    invalidas = df.index[datas.isna()]
    if len(invalidas) > 0:
        erros.append(
            f'Coluna "data" fora do formato AAAA-MM-DD (ou vazia) na(s) linha(s): '
            f"{_linhas_texto(invalidas)}."
        )

    # Valor numérico
    valores = pd.to_numeric(df["valor"], errors="coerce")
    invalidos = df.index[valores.isna()]
    if len(invalidos) > 0:
        erros.append(
            f'Coluna "valor" não numérica (ou vazia) na(s) linha(s): '
            f"{_linhas_texto(invalidos)}."
        )

    if erros:
        return df, erros

    # Tudo certo: devolve com os tipos corretos
    df["data"] = datas
    df["valor"] = valores
    return df, []
