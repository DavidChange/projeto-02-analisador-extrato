import hashlib
import json
import os

import altair as alt
import pandas as pd
import streamlit as st

from analise import (
    evolucao_mensal,
    fixo_variavel_mensal,
    fora_do_consumo,
    gasto_por_categoria,
    gastos_fixos,
    juntar_categorias,
    maiores_despesas,
    montar_pacote,
    resumo,
)
from categorizador import MODELO, VERSAO_PROMPT, categorizar_todos
from extrato import carregar_e_validar
from recomendador import VERSAO_PROMPT_RECOMENDACOES, gerar_recomendacoes

CAMINHO_EXEMPLO = "dados/transacoes.csv"
CAMINHO_CATEGORIAS_EXEMPLO = "resultados/categorias_v2-regras.csv"

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
# Eixos no padrão brasileiro: o Altair formata "1,500" e trocamos a vírgula por ponto
ROTULO_EIXO_BR = "replace(datum.label, regexp(',', 'g'), '.')"


def rotulo_mes(mes):
    """Ex.: '2026-08' -> 'ago/2026'."""
    ano, numero = mes.split("-")
    return f"{MESES[int(numero) - 1]}/{ano}"


def formatar_reais(valor):
    """Ex.: 1234.5 -> 'R$ 1.234,50' e -1234.5 -> '-R$ 1.234,50'."""
    sinal = "-" if valor < 0 else ""
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sinal}R$ {texto}"


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
col5.metric(
    "Saídas brutas",
    formatar_reais(abs(saidas)),
    help="Inclui a fatura do cartão, PIX a pessoas e aplicações",
)

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
# Categorias pré-calculadas só valem para o exemplo: um upload sempre começa sem categorias
elif guardado is not None and "origem" in guardado and fonte != CAMINHO_EXEMPLO:
    del st.session_state["categorias"]

# Exemplo sem categorias na sessão: carrega as já salvas em arquivo (sem chamar o Gemini)
if fonte == CAMINHO_EXEMPLO and "categorias" not in st.session_state:
    if os.path.exists(CAMINHO_CATEGORIAS_EXEMPLO):
        salvas = pd.read_csv(CAMINHO_CATEGORIAS_EXEMPLO, dtype=str)
        ids_extrato = sorted(t["id"] for t in transacoes)
        if sorted(salvas["id"]) == ids_extrato:
            st.session_state["categorias"] = {
                "assinatura": assinatura,
                "resultado": salvas[["id", "categoria", "modelo"]].to_dict("records"),
                "origem": {
                    "modelo": ", ".join(sorted(set(salvas["modelo"]))),
                    "versao_prompt": ", ".join(sorted(set(salvas["versao_prompt"]))),
                },
            }
        else:
            st.warning(
                "As categorias salvas não correspondem ao extrato de exemplo; "
                "use o botão Categorizar com IA."
            )

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
    if guardado is not None and "origem" in guardado:
        st.info(
            f"Categorias pré-calculadas pelo Gemini ({guardado['origem']['modelo']}, "
            f"prompt {guardado['origem']['versao_prompt']}) e carregadas de "
            f"{CAMINHO_CATEGORIAS_EXEMPLO}, sem nova chamada à API. "
            "Use o botão Categorizar com IA para categorizar ao vivo."
        )
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

# --- Análise dos gastos (só depois da categorização) ---
if guardado is not None:
    st.header("Análise dos gastos")
    try:
        df_cat = juntar_categorias(df, guardado["resultado"])
    except ValueError as e:
        st.error(str(e))
    else:
        r = resumo(df_cat)

        m1, m2, m3 = st.columns(3)
        m1.metric("Renda", formatar_reais(r["renda"]))
        m2.metric("Consumo", formatar_reais(r["consumo"]))
        m3.metric(
            "Sobra",
            formatar_reais(r["saldo"]),
            help="Renda menos consumo, antes de investimentos e transferências",
        )

        # Gráfico de barras horizontais: maior gasto no topo
        st.subheader("Gasto por categoria")
        gastos = gasto_por_categoria(df_cat)
        gastos["gasto_formatado"] = gastos["gasto"].map(formatar_reais)  # para o tooltip
        grafico = (
            alt.Chart(gastos)
            .mark_bar()
            .encode(
                x=alt.X(
                    "gasto:Q",
                    title="Gasto (R$)",
                    axis=alt.Axis(format=",.0f", labelExpr=ROTULO_EIXO_BR),
                ),
                y=alt.Y("categoria:N", sort="-x", title=None),
                tooltip=[
                    alt.Tooltip("categoria:N", title="Categoria"),
                    alt.Tooltip("gasto_formatado:N", title="Gasto"),
                ],
            )
        )
        st.altair_chart(grafico, width="stretch")

        # Evolução mensal: barras agrupadas (renda e consumo lado a lado em cada mês)
        st.subheader("Evolução mensal")
        mensal = evolucao_mensal(df_cat)
        mensal["mes_rotulo"] = mensal["mes"].map(rotulo_mes)
        longo = mensal.melt(
            id_vars=["mes", "mes_rotulo"],
            value_vars=["renda", "consumo"],
            var_name="tipo",
            value_name="valor",
        )
        longo["tipo"] = longo["tipo"].map({"renda": "Renda", "consumo": "Consumo"})
        longo["valor_formatado"] = longo["valor"].map(formatar_reais)  # para o tooltip
        grafico_mensal = (
            alt.Chart(longo)
            .mark_bar()
            .encode(
                x=alt.X(
                    "mes_rotulo:N",
                    title=None,
                    sort=mensal["mes_rotulo"].tolist(),  # ordem cronológica
                    axis=alt.Axis(labelAngle=0),
                ),
                xOffset=alt.XOffset("tipo:N", sort=["Renda", "Consumo"]),
                y=alt.Y(
                    "valor:Q",
                    title="Valor (R$)",
                    axis=alt.Axis(format=",.0f", labelExpr=ROTULO_EIXO_BR),
                ),
                color=alt.Color(
                    "tipo:N",
                    title=None,
                    scale=alt.Scale(domain=["Renda", "Consumo"], range=["#4C78A8", "#F58518"]),
                ),
                tooltip=[
                    alt.Tooltip("mes_rotulo:N", title="Mês"),
                    alt.Tooltip("tipo:N", title="Tipo"),
                    alt.Tooltip("valor_formatado:N", title="Valor"),
                ],
            )
        )
        st.altair_chart(grafico_mensal, width="stretch")

        # As 10 maiores despesas de consumo
        st.subheader("Maiores despesas")
        top = maiores_despesas(df_cat, n=10)
        top_tela = {
            "ID": top["id"],
            "Data": top["data"].dt.strftime("%d/%m/%Y"),
            "Descrição": top["descricao"],
            "Valor": top["valor"].map(formatar_reais),
            "Categoria": top["categoria"],
        }
        st.dataframe(top_tela, hide_index=True, width="stretch")
        st.caption("Só despesas de consumo; fatura, PIX a pessoas e aplicações ficam de fora.")

        # Tabela do que ficou fora do consumo (valores com sinal)
        st.subheader("Fora do consumo")
        fora = fora_do_consumo(df_cat)
        fora_tela = {
            "Grupo": fora["descricao_grupo"],
            "Total": fora["total"].map(formatar_reais),
        }
        st.dataframe(fora_tela, hide_index=True, width="stretch")
        st.caption(
            "Não entram no consumo: a fatura repetiria as compras do cartão já listadas; "
            "PIX a pessoas e aplicações não dizem com o que o dinheiro foi gasto."
        )

        # --- Gasto fixo x variável ---
        st.subheader("Gasto fixo x variável")
        fixo_variavel = fixo_variavel_mensal(df_cat)
        if fixo_variavel.empty:
            st.info("A separação entre gasto fixo e variável precisa de pelo menos 3 meses de extrato.")
        else:
            fv_tela = {
                "Mês": fixo_variavel["mes"].map(rotulo_mes),
                "Fixo": fixo_variavel["fixo"].map(formatar_reais),
                "Variável": fixo_variavel["variavel"].map(formatar_reais),
            }
            st.dataframe(fv_tela, hide_index=True, width="stretch")
            with st.expander("Gastos considerados fixos"):
                fixos = gastos_fixos(df_cat)
                fixos_tela = {
                    "Descrição": fixos["descricao"],
                    "Gasto médio": fixos["gasto_medio"].map(formatar_reais),
                }
                st.dataframe(fixos_tela, hide_index=True, width="stretch")
            st.caption("Fixo = aparece uma vez por mês, em todos os meses, com variação de valor de até 50%.")

        # --- Recomendações (IA) ---
        st.subheader("Recomendações (IA)")
        pacote = None
        try:
            pacote = montar_pacote(df_cat)
        except ValueError as e:
            st.info(str(e))

        # Se o extrato mudou, as recomendações antigas são descartadas (como as categorias)
        guardadas = st.session_state.get("recomendacoes")
        if guardadas is not None and guardadas["assinatura"] != assinatura:
            del st.session_state["recomendacoes"]

        if pacote is not None and st.button("Gerar recomendações com IA"):
            # Cache simples na sessão: (extrato, modelo, prompt) -> resultado
            cache_rec = st.session_state.setdefault("cache_recomendacoes", {})
            chave_rec = (assinatura, MODELO, VERSAO_PROMPT_RECOMENDACOES)

            if chave_rec in cache_rec:
                st.session_state["recomendacoes"] = {
                    "assinatura": assinatura,
                    "resultado": cache_rec[chave_rec],
                }
            else:
                try:
                    with st.spinner("Gerando recomendações com o Gemini..."):
                        resultado_rec = gerar_recomendacoes(pacote)
                    cache_rec[chave_rec] = resultado_rec
                    st.session_state["recomendacoes"] = {
                        "assinatura": assinatura,
                        "resultado": resultado_rec,
                    }
                except RuntimeError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Não foi possível gerar as recomendações ({type(e).__name__}): {e}")

        # Mostra as recomendações guardadas (continuam na tela depois de um Rerun)
        guardadas = st.session_state.get("recomendacoes")
        if pacote is not None and guardadas is not None:
            rec_guardado = guardadas["resultado"]
            # Dois "$" na mesma linha viram fórmula no Markdown: escapa todos
            for numero, rec in enumerate(rec_guardado["recomendacoes"], start=1):
                st.markdown(f"**{numero}. {rec['titulo']}**".replace("$", "\\$"))
                st.markdown(f"Diagnóstico: {rec['diagnostico']}".replace("$", "\\$"))
                st.markdown(f"Ação: {rec['acao']}".replace("$", "\\$"))
            st.caption(
                "Os números foram calculados pelo pandas. O texto foi escrito pelo Gemini "
                f"(modelo {rec_guardado['modelo']}, prompt {rec_guardado['versao_prompt']}) "
                "usando marcadores, e conferido automaticamente: o LLM não escreve nem calcula "
                "números. Conteúdo educativo, não é recomendação de investimento."
            )
