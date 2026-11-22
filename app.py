import hashlib
import json

import streamlit as st

from categorizador import MODELO, VERSAO_PROMPT, categorizar_todos
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

col1, col2, col3 = st.columns(3)
col1.metric("Transações", len(df))
col2.metric("Primeira data", f"{df['data'].min():%d/%m/%Y}")
col3.metric("Última data", f"{df['data'].max():%d/%m/%Y}")

col4, col5 = st.columns(2)
col4.metric("Total de entradas", formatar_reais(entradas))
col5.metric("Total de saídas", formatar_reais(abs(saidas)))

# Espaço reservado para a tabela (preenchido depois, para já mostrar a coluna "categoria")
area_tabela = st.container()

# --- Categorização com IA ---
transacoes = [
    {"id": str(l.id), "descricao": str(l.descricao), "valor": float(l.valor)}
    for l in df.itertuples()
]
# "Assinatura" do extrato atual: se o arquivo mudar, a categorização antiga é descartada
assinatura = hashlib.sha256(
    json.dumps(transacoes, ensure_ascii=False, sort_keys=True).encode("utf-8")
).hexdigest()

guardado = st.session_state.get("categorias")
if guardado is not None and guardado["assinatura"] != assinatura:
    del st.session_state["categorias"]

if st.button("Categorizar com IA"):
    # Cache simples na sessão: (extrato, modelo, prompt) -> resultado. Não usa @st.cache_data
    # porque a barra de progresso é um elemento de tela e não pode ser reencenada pelo cache.
    cache = st.session_state.setdefault("cache_categorias", {})
    chave = (assinatura, MODELO, VERSAO_PROMPT)

    if chave in cache:
        # Mesmo extrato, modelo e prompt: reaproveita, sem Gemini e sem barra
        st.session_state["categorias"] = {"assinatura": assinatura, "resultado": cache[chave]}
    else:
        barra = st.progress(0, text="Enviando ao Gemini...")

        def atualizar_barra(atual, total):
            barra.progress(atual / total, text=f"Lote {atual} de {total}")

        try:
            resultado = categorizar_todos(transacoes, progresso=atualizar_barra)
            cache[chave] = resultado
            st.session_state["categorias"] = {"assinatura": assinatura, "resultado": resultado}
        except RuntimeError as e:
            # Mensagens já em português vindas do categorizador (chave ausente, lote que falhou)
            st.error(str(e))
        except Exception as e:
            st.error(f"Não foi possível categorizar o extrato ({type(e).__name__}): {e}")
        finally:
            barra.empty()

# Tabela (com a coluna "categoria" quando já houver resultado)
tabela = df.copy()
guardado = st.session_state.get("categorias")
if guardado is not None:
    mapa = {r["id"]: r["categoria"] for r in guardado["resultado"]}
    tabela["categoria"] = tabela["id"].astype(str).map(mapa)

with area_tabela:
    st.dataframe(tabela, width="stretch")

# Contagem de transações por categoria
if guardado is not None:
    st.subheader("Transações por categoria")
    contagem = (
        tabela["categoria"]
        .value_counts()
        .rename_axis("categoria")
        .reset_index(name="transações")
    )
    st.dataframe(contagem, hide_index=True, width="stretch")
