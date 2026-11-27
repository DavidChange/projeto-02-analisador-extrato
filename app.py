import hashlib
import html
import json
import os
import re
import unicodedata

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
from categorizador import (
    LIMITE_DIARIO_APP,
    MODELO,
    TAMANHO_LOTE,
    VERSAO_PROMPT,
    ErroValidacao,
    categorizar_todos,
    explicar_erro,
    pedidos_restantes,
)
from extrato import carregar_e_validar
from particulas import ALTURA_QUADRO, COR_FORA_DA_LISTA, CORES, html_particulas
from recomendador import (
    VERSAO_PROMPT_RECOMENDACOES,
    gerar_recomendacoes,
    montar_marcadores,
    preencher_resposta,
    validar_resposta,
)

CAMINHO_EXEMPLO = "dados/transacoes.csv"
CAMINHO_CATEGORIAS_EXEMPLO = "resultados/categorias_v2-regras.csv"
CAMINHO_RECOMENDACOES_EXEMPLO = f"resultados/recomendacoes_{VERSAO_PROMPT_RECOMENDACOES}.json"

LIMITE_TRANSACOES_UPLOAD = 400  # limite da demonstração, para proteger a cota

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

URL_REPOSITORIO = "https://github.com/DavidChange/projeto-02-analisador-extrato"

# Aparência da barra do topo e dos cartões (as cores gerais estão em .streamlit/config.toml)
ESTILO = """
<style>
.topo { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
    gap: 12px; padding-bottom: 14px; border-bottom: 1px solid #1d1d21; }
.topo-nome { font-size: 1.5rem; font-weight: 700; }
.topo-etiquetas { display: flex; flex-wrap: wrap; gap: 8px; }
.etiqueta { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; padding: 4px 12px;
    background: #0b0b0d; border: 1px solid #1d1d21; border-radius: 999px; }
.topo a.etiqueta { color: #e9e7e4; text-decoration: none; }
.topo a.etiqueta:hover { color: #ff7a4d; border-color: #ff7a4d; }
.cartoes { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 12px; }
.cartao { background: #0b0b0d; border: 1px solid #1d1d21; border-radius: 14px;
    padding: 18px 20px; }
.cartao-rotulo { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;
    text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.65; }
.cartao-valor { font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; font-weight: 600;
    margin-top: 6px; overflow-wrap: anywhere; }
.cartao-destaque .cartao-valor { color: #ff7a4d; }
.paineis { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr); gap: 12px; }
.painel { display: flex; flex-direction: column; gap: 14px; }
.painel-topo { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; }
.legenda { display: flex; gap: 12px; font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; }
.bolinha { display: inline-block; flex: none; width: 8px; height: 8px; border-radius: 50%; }
.legenda .bolinha { margin-right: 5px; }
.cor-renda { background: #f6f4f1; }
.cor-consumo { background: #ff7a4d; }
.meses { flex: 1; display: flex; gap: 6px; overflow-x: auto; }
.mes { flex: 1 0 74px; display: flex; flex-direction: column; text-align: center; }
.barras { position: relative; flex: 1; min-height: 210px; padding-top: 28px; display: flex;
    justify-content: center; gap: 6px; border-bottom: 1px solid #1d1d21; }
.coluna { height: 100%; width: 26px; display: flex; align-items: flex-end; outline: none; }
.barra { width: 100%; border-radius: 5px 5px 0 0; }
.coluna:hover .barra, .coluna:focus .barra { opacity: 0.8; }
.dica { position: absolute; top: 0; left: 50%; transform: translateX(-50%); white-space: nowrap;
    font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; padding: 2px 6px;
    background: #1d1d21; border-radius: 6px; display: none; pointer-events: none; }
.coluna:hover .dica, .coluna:focus .dica { display: block; }
.mes-nome, .mes-sobra { font-family: 'JetBrains Mono', monospace; }
.mes-nome { font-size: 0.75rem; margin-top: 8px; }
.mes-sobra { font-size: 0.65rem; opacity: 0.65; margin-top: 2px; }
.linha { display: grid; grid-template-columns: 8px minmax(0, 1fr) 3.2em 6.6em; align-items: center;
    gap: 6px; padding: 7px 0; border-bottom: 1px solid #1d1d21; font-size: 0.78rem; }
.linha:last-child { border-bottom: none; }
.linha-percentual, .linha-valor { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem;
    text-align: right; white-space: nowrap; }
.linha-percentual { opacity: 0.65; }
.divisao { display: flex; height: 10px; margin: 14px 0 12px; border-radius: 999px;
    overflow: hidden; background: #1d1d21; }
.cor-fixo { background: #8f6c60; }
.cor-variavel { background: #ff7a4d; }
.parcela { display: flex; align-items: center; gap: 7px; margin-top: 4px;
    font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; }
.rotulo-secao { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;
    letter-spacing: 0.08em; opacity: 0.65; padding-bottom: 6px; }
.contagem { font-size: 0.875rem; color: #a5a3a0; }
.filtro-ativo { color: #ff7a4d; }
.st-key-limpar_filtros button { min-height: 0; padding: 2px 12px; }
.st-key-limpar_filtros button p { font-size: 0.75rem; }
.secao { display: flex; align-items: baseline; gap: 12px; margin-top: 28px;
    padding-top: 20px; border-top: 1px solid #1d1d21; }
.secao-numero { font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; color: #ff7a4d; }
.secao-titulo { font-size: 1.75rem; font-weight: 700; line-height: 1.2; }
@media (max-width: 640px) { .paineis { grid-template-columns: minmax(0, 1fr); } }
[data-testid="stMetricLabel"] p, [data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace; }
</style>
"""


def rotulo_mes(mes):
    """Ex.: '2026-08' -> 'ago/2026'."""
    ano, numero = mes.split("-")
    return f"{MESES[int(numero) - 1]}/{ano}"


def formatar_reais(valor):
    """Ex.: 1234.5 -> 'R$ 1.234,50' e -1234.5 -> '-R$ 1.234,50'."""
    sinal = "-" if valor < 0 else ""
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sinal}R$ {texto}"


def escapar_markdown(texto):
    """Faz o texto aparecer como foi escrito, sem virar formatação ou fórmula no Markdown.

    Junta as quebras de linha em espaços e põe uma barra antes dos caracteres especiais.
    """
    texto = " ".join(str(texto).split())
    return re.sub(r"([\\`*_{}\[\]<>()#+\-.!|~$=&])", r"\\\1", texto)


def mostrar_erro_gemini(erro, complemento=""):
    """Frase em português na tela; o texto técnico fica recolhido."""
    st.error(f"{explicar_erro(erro)} {complemento}".strip())
    with st.expander("Detalhes técnicos"):
        st.text(f"{type(erro).__name__}: {erro}")


def mostrar_restantes(area):
    """Texto pequeno com o saldo de pedidos do dia (compartilhado entre visitantes)."""
    area.caption(
        f"Pedidos ao Gemini restantes hoje nesta demonstração: "
        f"{pedidos_restantes()} de {LIMITE_DIARIO_APP}."
    )


def mostrar_topo(area):
    """Barra do topo: nome do app e etiquetas (dados fictícios, saldo do dia e GitHub)."""
    area.html(
        '<div class="topo">'
        '<div class="topo-nome">Extrato com IA</div>'
        '<div class="topo-etiquetas">'
        '<span class="etiqueta">dados fictícios</span>'
        f'<span class="etiqueta">pedidos de IA hoje: {pedidos_restantes()} de '
        f"{LIMITE_DIARIO_APP}</span>"
        f'<a class="etiqueta" href="{URL_REPOSITORIO}" target="_blank" '
        'rel="noopener noreferrer">GitHub</a>'
        "</div></div>"
    )


def mostrar_cartoes(r):
    """Cartões de Renda, Consumo e Sobra (r é o resultado de resumo())."""
    st.html(
        '<div class="cartoes">'
        '<div class="cartao"><div class="cartao-rotulo">Renda</div>'
        f'<div class="cartao-valor">{formatar_reais(r["renda"])}</div></div>'
        '<div class="cartao"><div class="cartao-rotulo">Consumo</div>'
        f'<div class="cartao-valor">{formatar_reais(r["consumo"])}</div></div>'
        '<div class="cartao cartao-destaque" '
        'title="Renda menos consumo, antes de investimentos e transferências">'
        '<div class="cartao-rotulo">Sobra</div>'
        f'<div class="cartao-valor">{formatar_reais(r["saldo"])}</div></div>'
        "</div>"
    )


def html_mes_a_mes(mensal):
    """Cartão com duas barras por mês (mensal é o resultado de evolucao_mensal())."""
    # A maior renda ocupa a altura toda; se um consumo passar dela, ele vira a referência
    maior = max(mensal["renda"].max(), mensal["consumo"].max())
    colunas = []
    for linha in mensal.itertuples():
        barras = ""
        for nome, classe, valor in (
            ("Renda", "cor-renda", linha.renda),
            ("Consumo", "cor-consumo", linha.consumo),
        ):
            altura = max(0.0, valor) / maior * 100 if maior > 0 else 0.0
            texto = formatar_reais(valor)
            barras += (
                f'<div class="coluna" tabindex="0" aria-label="{nome}: {texto}">'
                f'<span class="dica">{texto}</span>'
                f'<div class="barra {classe}" style="height: {altura:.2f}%"></div></div>'
            )
        sobra = formatar_reais(linha.sobra).replace(" ", "&nbsp;")
        colunas.append(
            f'<div class="mes"><div class="barras">{barras}</div>'
            f'<div class="mes-nome">{rotulo_mes(linha.mes)}</div>'
            f'<div class="mes-sobra">sobra {sobra}</div></div>'
        )
    return (
        '<div class="cartao painel"><div class="painel-topo">'
        '<div class="cartao-rotulo">Mês a mês</div>'
        '<div class="legenda"><span><span class="bolinha cor-renda"></span>renda</span>'
        '<span><span class="bolinha cor-consumo"></span>consumo</span></div></div>'
        f'<div class="meses">{"".join(colunas)}</div></div>'
    )


def html_para_onde_foi(gastos):
    """Cartão com uma linha por categoria (gastos é o resultado de gasto_por_categoria())."""
    linhas = []
    for linha in gastos.itertuples():  # já vem do maior gasto para o menor
        cor = CORES.get(linha.categoria, COR_FORA_DA_LISTA)
        percentual = f"{linha.percentual:.1f}".replace(".", ",")
        linhas.append(
            f'<div class="linha"><span class="bolinha" style="background: {cor}"></span>'
            f"<span>{html.escape(str(linha.categoria))}</span>"
            f'<span class="linha-percentual">{percentual}%</span>'
            f'<span class="linha-valor">{formatar_reais(linha.gasto)}</span></div>'
        )
    return (
        '<div class="cartao painel"><div class="cartao-rotulo">Para onde foi</div>'
        f'<div>{"".join(linhas)}</div></div>'
    )


def mostrar_paineis(mensal, gastos):
    """Os cartões "Mês a mês" e "Para onde foi", lado a lado (empilhados em tela estreita)."""
    st.html(
        f'<div class="paineis">{html_mes_a_mes(mensal)}{html_para_onde_foi(gastos)}</div>'
    )


def sem_acentos(texto):
    """Ex.: 'Farmácia' -> 'farmacia', para buscar sem diferenciar maiúsculas e acentos."""
    separado = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in separado if not unicodedata.combining(c)).casefold()


def limpar_filtros(chave):
    """on_click de "Limpar filtros": volta os três filtros ao padrão."""
    st.session_state[f"busca_{chave}"] = ""
    st.session_state[f"mes_{chave}"] = "Todos"
    if f"categoria_{chave}" in st.session_state:
        st.session_state[f"categoria_{chave}"] = "Todas"


def mostrar_extrato(tabela, assinatura, desativado):
    """Filtros e tabela do extrato. Só muda o que aparece: os cálculos usam o extrato inteiro."""
    tem_categorias = "categoria" in tabela.columns
    with st.container(horizontal=True, vertical_alignment="bottom"):
        st.subheader("Extrato", width="content")
        st.html('<div class="rotulo-secao">FILTRAR TRANSAÇÕES</div>', width="content")
    areas = st.columns(3 if tem_categorias else 2)
    # A assinatura nas chaves faz os filtros voltarem ao início quando o extrato muda
    chave = assinatura[:12]

    busca = areas[0].text_input(
        "Buscar",
        key=f"busca_{chave}",
        placeholder="Ex.: uber, mercado, aluguel",
        disabled=desativado,
    )
    meses = tabela["data"].dt.strftime("%Y-%m")
    mes = areas[1].selectbox(
        "Mês",
        ["Todos"] + sorted(meses.unique()),
        format_func=lambda m: m if m == "Todos" else rotulo_mes(m),
        key=f"mes_{chave}",
        disabled=desativado,
    )
    categoria = "Todas"
    if tem_categorias:
        presentes = sorted(tabela["categoria"].dropna().unique(), key=sem_acentos)
        categoria = areas[2].selectbox(
            "Categoria", ["Todas"] + presentes, key=f"categoria_{chave}", disabled=desativado
        )

    visiveis = pd.Series(True, index=tabela.index)
    if busca.strip():
        descricoes = tabela["descricao"].map(sem_acentos)
        visiveis &= descricoes.str.contains(sem_acentos(busca.strip()), regex=False)
    if mes != "Todos":
        visiveis &= meses == mes
    if categoria != "Todas":
        visiveis &= tabela["categoria"] == categoria
    filtrada = tabela[visiveis]

    colunas = {"id": "ID", "data": "Data", "descricao": "Descrição", "valor": "Valor"}
    if tem_categorias:
        colunas["categoria"] = "Categoria"
    tela = filtrada[list(colunas)].rename(columns=colunas)
    st.space("small")  # a barra de ícones da tabela aparece aqui, sem cobrir os filtros
    # Data e valor continuam sendo data e número (a ordenação funciona); só muda a exibição
    st.dataframe(
        tela.style.format({"Valor": formatar_reais}),
        column_config={
            # larguras (px) para as 5 colunas caberem na tela do computador
            "ID": st.column_config.Column(width=60),
            "Data": st.column_config.DateColumn(format="DD/MM/YYYY", width=100),
            "Descrição": st.column_config.Column(width=275),
            "Valor": st.column_config.Column(width=100),
            "Categoria": st.column_config.Column(width=160),
        },
        hide_index=True,
        width="stretch",
    )
    contagem = f"Mostrando {len(filtrada)} de {len(tabela)} transações"
    ativo = bool(busca.strip()) or mes != "Todos" or categoria != "Todas"
    with st.container(horizontal=True, vertical_alignment="center"):
        if ativo:
            st.html(
                f'<div class="contagem">{contagem} · '
                '<span class="filtro-ativo">filtro ativo</span></div>',
                width="content",
            )
            st.button(
                "Limpar filtros",
                key="limpar_filtros",
                on_click=limpar_filtros,
                args=(chave,),
                disabled=desativado,
            )
        else:
            st.html(f'<div class="contagem">{contagem}.</div>', width="content")


def mostrar_fixo_variavel(fixo_variavel):
    """Um cartão por mês (fixo_variavel é o resultado de fixo_variavel_mensal())."""
    cartoes = []
    for linha in fixo_variavel.itertuples():
        fixo, variavel = formatar_reais(linha.fixo), formatar_reais(linha.variavel)
        # Larguras da barra: proporção entre os dois (um valor negativo não ocupa espaço)
        parte_fixa, parte_variavel = max(0.0, linha.fixo), max(0.0, linha.variavel)
        soma = parte_fixa + parte_variavel
        largura_fixa = parte_fixa / soma * 100 if soma > 0 else 0.0
        largura_variavel = parte_variavel / soma * 100 if soma > 0 else 0.0
        cartoes.append(
            f'<div class="cartao"><div class="cartao-rotulo">{rotulo_mes(linha.mes)}</div>'
            f'<div class="divisao" role="img" aria-label="Fixo {fixo}, variável {variavel}">'
            f'<div class="cor-fixo" style="width: {largura_fixa:.2f}%"></div>'
            f'<div class="cor-variavel" style="width: {largura_variavel:.2f}%"></div></div>'
            f'<div class="parcela"><span class="bolinha cor-fixo"></span>Fixo {fixo}</div>'
            f'<div class="parcela"><span class="bolinha cor-variavel"></span>'
            f"Variável {variavel}</div></div>"
        )
    st.html(f'<div class="cartoes">{"".join(cartoes)}</div>')


def titulo_secao(numero, texto):
    """Título numerado das seções da página (ex.: 01 Envie o extrato)."""
    st.html(
        '<div class="secao" role="heading" aria-level="2">'
        f'<span class="secao-numero">{numero}</span>'
        f'<span class="secao-titulo">{texto}</span></div>'
    )


def marcar_execucao(acao):
    """on_click dos botões de IA: marca na sessão o que vai rodar."""
    if not st.session_state.get("rodando"):
        st.session_state["rodando"] = acao


def parar():
    """st.stop() sem deixar nenhuma chamada marcada (senão os botões ficariam presos)."""
    st.session_state["rodando"] = None
    st.stop()


def mostrar_erro_guardado(acao):
    """Mostra, uma vez, o erro da última chamada dessa ação."""
    guardado = st.session_state.get("erro_ia")
    if guardado is not None and guardado[0] == acao:
        del st.session_state["erro_ia"]
        mostrar_erro_gemini(guardado[1], guardado[2])


def aviso_lotes_guardados(total_transacoes):
    """Frase sobre os lotes já prontos depois de uma falha (vazia se não houver nenhum)."""
    guardados = st.session_state.get("lotes_prontos")
    if not guardados or not guardados["lotes"]:
        return ""
    total = len(range(0, total_transacoes, TAMANHO_LOTE))
    return (
        f"Lotes guardados: {len(guardados['lotes'])} de {total}. Um novo clique em "
        '"Categorizar com IA" continua de onde parou.'
    )


def categorizar_agora(transacoes, assinatura, area, areas_saldo):
    # Cache simples na sessão: (extrato, modelo, prompt) -> resultado. Não usa @st.cache_data
    # porque a barra de progresso é um elemento de tela e não pode ser reencenada pelo cache.
    cache = st.session_state.setdefault("cache_categorias", {})
    chave = (assinatura, MODELO, VERSAO_PROMPT)

    # Mesmo extrato, modelo e prompt: reaproveita, sem Gemini e sem barra
    if chave not in cache:
        barra = area.progress(0, text="Enviando ao Gemini...")

        def atualizar_barra(atual, total):
            barra.progress(atual / total, text=f"Lote {atual} de {total}")
            for area_saldo in areas_saldo:
                mostrar_restantes(area_saldo)
            mostrar_topo(area_topo)

        # Lotes já prontos deste extrato: sobrevivem a uma falha no meio
        guardados = st.session_state.get("lotes_prontos")
        if guardados is None or guardados["assinatura"] != assinatura:
            guardados = {"assinatura": assinatura, "lotes": {}}
            st.session_state["lotes_prontos"] = guardados
        cache[chave] = categorizar_todos(
            transacoes, progresso=atualizar_barra, lotes_prontos=guardados["lotes"]
        )
        del st.session_state["lotes_prontos"]  # o resultado completo já está no cache
    st.session_state["categorias"] = {"assinatura": assinatura, "resultado": cache[chave]}


def recomendar_agora(pacote, chave_pacote, assinatura, area):
    # Cache simples na sessão: (pacote, modelo, prompt) -> resultado. Com o mesmo pacote,
    # mostra as recomendações que já existem, sem chamar o Gemini.
    cache = st.session_state.setdefault("cache_recomendacoes", {})
    chave = (chave_pacote, MODELO, VERSAO_PROMPT_RECOMENDACOES)
    if chave not in cache:
        with area, st.spinner("Gerando recomendações com o Gemini..."):
            cache[chave] = gerar_recomendacoes(pacote)
    st.session_state["recomendacoes"] = {
        "assinatura": assinatura,
        "pacote": chave_pacote,
        "resultado": cache[chave],
    }


st.html(ESTILO)
area_topo = st.empty()  # redesenhada durante a categorização, para o saldo acompanhar
mostrar_topo(area_topo)

# True enquanto há uma chamada ao Gemini marcada: desativa os controles da tela
ocupado = st.session_state.get("rodando") is not None

titulo_secao("01", "Envie o extrato")
arquivo = st.file_uploader("Envie um extrato em CSV", type="csv", disabled=ocupado)

# Guarda no session_state que o usuário pediu o exemplo (o Streamlit reroda o script a cada clique)
if st.button("Usar dados de exemplo", disabled=ocupado):
    st.session_state["usar_exemplo"] = True
if arquivo is not None:
    st.session_state["usar_exemplo"] = False  # um upload novo vale mais que o exemplo

if arquivo is not None:
    fonte = arquivo
elif st.session_state.get("usar_exemplo"):
    fonte = CAMINHO_EXEMPLO
else:
    st.info("Envie um CSV (colunas: id, data, descricao, valor) ou use os dados de exemplo.")
    parar()

df, erros = carregar_e_validar(fonte)

# Se houver erros, mostra e para
if erros:
    for erro in erros:
        st.error(erro)
    parar()

if arquivo is not None and len(df) > LIMITE_TRANSACOES_UPLOAD:
    st.error(
        f"Este extrato tem {len(df)} transações, e o limite desta demonstração é de "
        f"{LIMITE_TRANSACOES_UPLOAD}. Envie um arquivo menor, ou remova o arquivo e use "
        '"Usar dados de exemplo".'
    )
    parar()

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

# --- Categorização com IA ---
titulo_secao("02", "Categorize com IA")
transacoes = [
    {"id": str(l.id), "descricao": str(l.descricao), "valor": float(l.valor)}
    for l in df.itertuples()
]
# "Assinatura" do extrato atual: se o arquivo mudar, a categorização antiga é descartada
assinatura = hashlib.sha256(
    json.dumps(transacoes, ensure_ascii=False, sort_keys=True).encode("utf-8")
).hexdigest()

# Trocar de arquivo descarta os lotes guardados do extrato anterior
lotes_guardados = st.session_state.get("lotes_prontos")
if lotes_guardados is not None and lotes_guardados["assinatura"] != assinatura:
    del st.session_state["lotes_prontos"]

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

st.button(
    "Categorizar com IA", on_click=marcar_execucao, args=("categorizar",), disabled=ocupado
)
# Espaços para o saldo de pedidos (atualizados durante a categorização)
areas_restantes = [st.empty()]
mostrar_restantes(areas_restantes[0])
area_categorizar = st.empty()  # barra de progresso
mostrar_erro_guardado("categorizar")

# Preenchidos mais abaixo, quando houver pacote para as recomendações
pacote = chave_pacote = area_recomendar = None

# Tabela (com a coluna "categoria" quando já houver resultado)
tabela = df.copy()
guardado = st.session_state.get("categorias")
if guardado is not None:
    mapa = {r["id"]: r["categoria"] for r in guardado["resultado"]}
    tabela["categoria"] = tabela["id"].astype(str).map(mapa)

# Aviso das categorias pré-calculadas
if guardado is not None and "origem" in guardado:
    st.info(
        f"Categorias pré-calculadas pelo Gemini ({guardado['origem']['modelo']}, "
        f"prompt {guardado['origem']['versao_prompt']}) e carregadas de "
        f"{CAMINHO_CATEGORIAS_EXEMPLO}, sem nova chamada à API. "
        "Use o botão Categorizar com IA para categorizar ao vivo."
    )

# --- 03: o resultado (só depois da categorização) ---
df_cat = None
if guardado is not None:
    titulo_secao("03", "O resultado")
    try:
        df_cat = juntar_categorias(df, guardado["resultado"])
    except ValueError as e:
        st.error(str(e))
    else:
        r = resumo(df_cat)

        mostrar_cartoes(r)

        # Animação: cada ponto é um pedaço do consumo (as datas são as do resumo, no alto)
        periodo = f"{df['data'].min():%d/%m/%Y} a {df['data'].max():%d/%m/%Y}"
        st.iframe(
            html_particulas(gasto_por_categoria(df_cat), periodo, r["consumo"]),
            height=ALTURA_QUADRO,
        )

        mostrar_paineis(evolucao_mensal(df_cat), gasto_por_categoria(df_cat))

# --- 04: recomendações da IA ---
if df_cat is not None:
    titulo_secao("04", "Recomendações da IA")
    area_aviso_rec = st.container()  # aviso das pré-geradas (preenchido depois do botão)
    try:
        pacote = montar_pacote(df_cat)
        chave_pacote = hashlib.sha256(
            json.dumps(pacote, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
    except ValueError as e:
        st.info(str(e))

    # Se o extrato ou o pacote mudou, as recomendações antigas são descartadas
    guardadas = st.session_state.get("recomendacoes")
    if guardadas is not None and (
        guardadas["assinatura"] != assinatura or guardadas.get("pacote") != chave_pacote
    ):
        del st.session_state["recomendacoes"]
    # Pré-geradas só valem enquanto as categorias também forem as pré-calculadas
    guardadas = st.session_state.get("recomendacoes")
    if guardadas is not None and "origem" in guardadas and "origem" not in guardado:
        del st.session_state["recomendacoes"]

    # Exemplo com categorias pré-calculadas e sem recomendações: carrega as já geradas
    # (sem chamar o Gemini). Se o arquivo salvo tiver problema, avisa e segue sem ele.
    if (
        pacote is not None
        and fonte == CAMINHO_EXEMPLO
        and "origem" in guardado
        and "recomendacoes" not in st.session_state
        and os.path.exists(CAMINHO_RECOMENDACOES_EXEMPLO)
    ):
        try:
            with open(CAMINHO_RECOMENDACOES_EXEMPLO, encoding="utf-8") as f:
                salvo = json.load(f)
            if salvo["versao_prompt"] == VERSAO_PROMPT_RECOMENDACOES:
                marcadores_rec = montar_marcadores(pacote)
                validar_resposta(salvo["resposta_bruta"], marcadores_rec)
                st.session_state["recomendacoes"] = {
                    "assinatura": assinatura,
                    "pacote": chave_pacote,
                    "resultado": {
                        # Texto preenchido de novo com os números do pacote atual
                        "recomendacoes": preencher_resposta(
                            salvo["resposta_bruta"], marcadores_rec
                        ),
                        "modelo": salvo["modelo"],
                        "versao_prompt": salvo["versao_prompt"],
                    },
                    "origem": {"arquivo": CAMINHO_RECOMENDACOES_EXEMPLO},
                }
        except (
            OSError,  # arquivo que não abre
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,  # campo ausente
            TypeError,  # formato diferente do esperado
            ErroValidacao,  # recomendações que não passam na conferência
        ):
            st.warning(
                "As recomendações salvas não puderam ser carregadas. Use o botão "
                "Gerar recomendações com IA para gerar ao vivo."
            )

    if pacote is not None:
        st.button(
            "Gerar recomendações com IA",
            on_click=marcar_execucao,
            args=("recomendar",),
            disabled=ocupado,
        )
        areas_restantes.append(st.empty())
        mostrar_restantes(areas_restantes[-1])
        area_recomendar = st.empty()  # aviso de "gerando"
        mostrar_erro_guardado("recomendar")

    # Mostra as recomendações guardadas (continuam na tela depois de um Rerun)
    guardadas = st.session_state.get("recomendacoes")
    if pacote is not None and guardadas is not None:
        rec_guardado = guardadas["resultado"]
        if "origem" in guardadas:
            with area_aviso_rec:
                st.info(
                    f"Recomendações pré-geradas pelo Gemini ({rec_guardado['modelo']}, "
                    f"prompt {rec_guardado['versao_prompt']}) e salvas em "
                    f"{guardadas['origem']['arquivo']}, sem nova chamada à API. "
                    "Os valores foram preenchidos agora a partir dos números calculados "
                    "pelo pandas. O botão gera novas recomendações ao vivo."
                )
        # O texto da IA é escapado para não virar formatação (ex.: dois "$" viram fórmula)
        for numero, rec in enumerate(rec_guardado["recomendacoes"], start=1):
            st.markdown(f"**{numero}. {escapar_markdown(rec['titulo'])}**")
            st.markdown(f"Diagnóstico: {escapar_markdown(rec['diagnostico'])}")
            st.markdown(f"Ação: {escapar_markdown(rec['acao'])}")
        st.caption(
            "Os números foram calculados pelo pandas. O texto foi escrito pelo Gemini "
            f"(modelo {rec_guardado['modelo']}, prompt {rec_guardado['versao_prompt']}) "
            "usando marcadores, e conferido automaticamente: o LLM não escreve nem calcula "
            "números. Conteúdo educativo, não é recomendação de investimento."
        )

# Sem categorias ainda: os títulos 03 e 04 aparecem, para a numeração não pular
if guardado is None:
    for numero, texto in (("03", "O resultado"), ("04", "Recomendações da IA")):
        titulo_secao(numero, texto)
        st.caption("Aparece depois da categorização.")

# --- 05: detalhes ---
titulo_secao("05", "Detalhes")
if df_cat is not None:
    # --- Gasto fixo x variável ---
    st.subheader("Gasto fixo x variável")
    fixo_variavel = fixo_variavel_mensal(df_cat)
    if fixo_variavel.empty:
        st.info("A separação entre gasto fixo e variável precisa de pelo menos 3 meses de extrato.")
    else:
        mostrar_fixo_variavel(fixo_variavel)
        with st.expander("Gastos considerados fixos"):
            fixos = gastos_fixos(df_cat)
            fixos_tela = {
                "Descrição": fixos["descricao"],
                "Gasto médio": fixos["gasto_medio"].map(formatar_reais),
            }
            st.dataframe(fixos_tela, hide_index=True, width="stretch")
        st.caption("Fixo = aparece uma vez por mês, em todos os meses, com variação de valor de até 50%.")

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

# Contagem de transações por categoria
if guardado is not None:
    with st.expander("Transações por categoria"):
        contagem = (
            tabela["categoria"]
            .value_counts()
            .rename_axis("categoria")
            .reset_index(name="transações")
        )
        st.dataframe(contagem, hide_index=True, width="stretch")

# O extrato aparece também antes da categorização (sem a coluna "Categoria")
mostrar_extrato(tabela, assinatura, ocupado)

# --- Chamada ao Gemini marcada por um botão ---
# Roda só aqui, no fim, quando todos os controles já foram desenhados desativados.
acao = st.session_state.get("rodando")
if acao is not None:
    try:
        if acao == "categorizar":
            categorizar_agora(transacoes, assinatura, area_categorizar, areas_restantes)
        elif acao == "recomendar" and pacote is not None:
            recomendar_agora(pacote, chave_pacote, assinatura, area_recomendar)
    except Exception as e:
        complemento = aviso_lotes_guardados(len(transacoes)) if acao == "categorizar" else ""
        st.session_state["erro_ia"] = (acao, e, complemento)
    finally:
        st.session_state["rodando"] = None  # com sucesso, erro ou interrupção
    st.rerun()  # redesenha com os botões ativos e com o resultado
