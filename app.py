import streamlit as st

from extrato import carregar_e_validar

CAMINHO_EXEMPLO = "dados/transacoes.csv"


def formatar_reais(valor):
    """Ex.: 1234.5 -> 'R$ 1.234,50'."""
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


st.title("Analisador de extrato financeiro")
st.warning("Use apenas dados fictícios.")

arquivo = st.file_uploader("Envie um extrato em CSV", type="csv")

# Guarda no session_state que o usuário pediu o exemplo (o Streamlit reroda o script a cada clique)
if st.button("Usar dados de exemplo"):
    st.session_state["usar_exemplo"] = True
if arquivo is not None:
    st.session_state["usar_exemplo"] = False  # um upload novo vale mais que o exemplo

if arquivo is not None:
    fonte = arquivo
elif st.session_state.get("usar_exemplo"):
    fonte = CAMINHO_EXEMPLO
else:
    st.info("Envie um CSV (colunas: id, data, descricao, valor) ou use os dados de exemplo.")
    st.stop()

df, erros = carregar_e_validar(fonte)

# Se houver erros, mostra e para
if erros:
    for erro in erros:
        st.error(erro)
    st.stop()

# Resumo
entradas = df.loc[df["valor"] > 0, "valor"].sum()
saidas = df.loc[df["valor"] < 0, "valor"].sum()

col1, col2 = st.columns(2)
col1.metric("Transações", len(df))
col2.metric("Período", f"{df['data'].min():%d/%m/%Y} a {df['data'].max():%d/%m/%Y}")

col3, col4 = st.columns(2)
col3.metric("Total de entradas", formatar_reais(entradas))
col4.metric("Total de saídas", formatar_reais(abs(saidas)))

st.dataframe(df, width="stretch")
