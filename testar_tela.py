"""Testes da tela do app (cartões de recomendações e subtítulos). Não chama a API."""

import json

import pandas as pd
from streamlit.testing.v1 import AppTest

import categorizador


def proibido(*args, **kwargs):
    raise AssertionError("o teste da tela não pode criar o cliente do Gemini")


categorizador.genai.Client = proibido


def blocos_html(app):
    return [elemento.proto.body for elemento in app.get("html")]


at = AppTest.from_file("app.py", default_timeout=60).run()
next(b for b in at.button if b.label == "Usar dados de exemplo").click()
at.run()
assert not at.exception, at.exception

# --- a) Subtítulos da seção 05, pela mesma função e na ordem certa ---
subtitulos = [
    corpo.split('subtitulo-texto">')[1].split("<")[0]
    for corpo in blocos_html(at)
    if 'class="subtitulo"' in corpo
]
assert subtitulos == ["Gasto fixo x variável", "Maiores despesas", "Fora do consumo", "Extrato"]
assert any("Extrato</span><span class=\"rotulo-secao\">FILTRAR TRANSAÇÕES<" in c
           for c in blocos_html(at))
assert not at.subheader, [s.value for s in at.subheader]
print("OK: 4 subtítulos da seção 05, com FILTRAR TRANSAÇÕES ao lado de Extrato")

# --- b) Recomendações falsas: nada vira HTML e os "$" ficam como foram escritos ---
falsas = [
    {
        "titulo": "<script>alert(1)</script> <b>negrito</b>",
        "diagnostico": "Entre R$ 10 e R$ 20 por **mês** & \"aspas\".",
        "acao": "</div><img src=x onerror=alert(1)> guarde R$ 10 e R$ 20",
    },
    {"titulo": "Segunda", "diagnostico": "Texto <b>b</b>", "acao": "Ação $x$"},
    {"titulo": "Terceira", "diagnostico": "Texto", "acao": "Ação"},
]
guardadas = dict(at.session_state["recomendacoes"])
guardadas["resultado"] = {**guardadas["resultado"], "recomendacoes": falsas}
at.session_state["recomendacoes"] = guardadas
at.run()
assert not at.exception, at.exception

cartoes = [c for c in blocos_html(at) if 'class="recomendacoes"' in c]
assert len(cartoes) == 1
corpo = cartoes[0]
for proibida in ["<script", "</script", "<b>", "<img"]:
    assert proibida not in corpo, proibida
for esperado in [
    "&lt;script&gt;alert(1)&lt;/script&gt; &lt;b&gt;negrito&lt;/b&gt;",
    "Entre R$&nbsp;10 e R$&nbsp;20 por **mês** &amp; &quot;aspas&quot;.",
    "→ &lt;/div&gt;&lt;img src=x onerror=alert(1)&gt; guarde R$&nbsp;10 e R$&nbsp;20",
    "→ Ação $x$",
]:
    assert esperado in corpo, esperado
assert "R$ " not in corpo, "sobrou R$ com espaço que quebra"
assert corpo.count('class="cartao rec"') == 3
assert [corpo.count(f'rec-numero">{n}<') for n in ["01", "02", "03"]] == [1, 1, 1]
assert not any("negrito" in m.value for m in at.markdown)
print("OK: recomendação falsa escapada; os $ aparecem normais; 3 cartões numerados")
print("OK: R$ preso ao número por um espaço que não quebra")

# --- c) Notas no lugar das caixas azuis e etiquetas do topo ---
assert not at.info, [i.value for i in at.info]
notas = [c for c in blocos_html(at) if 'class="cartao nota"' in c]
assert len(notas) == 2, notas
assert (
    "<span>Estas categorias já foram calculadas pelo Gemini e salvas, sem gastar pedidos. "
    "Para ver a IA trabalhando ao vivo, clique em Categorizar com IA.</span>" in notas[0]
), notas[0]
assert (
    "<span>Estas recomendações já foram geradas pelo Gemini e salvas. Os valores vêm do pandas. "
    "Para gerar novas ao vivo, clique em Gerar recomendações com IA.</span>" in notas[1]
), notas[1]
assert all('nota-icone" aria-hidden="true">ⓘ</span>' in c and ">NOTA<" not in c for c in notas)
# A linha pequena de cada nota vem dos arquivos salvos (modelo e prompt)
salvas = pd.read_csv("resultados/categorias_v2-regras.csv", dtype=str)
detalhe_categorias = (
    f"{', '.join(sorted(set(salvas['modelo'])))} · prompt "
    f"{', '.join(sorted(set(salvas['versao_prompt'])))}"
)
with open("resultados/recomendacoes_r2.json", encoding="utf-8") as arquivo:
    salvo = json.load(arquivo)
detalhe_recomendacoes = f"{salvo['modelo']} · prompt {salvo['versao_prompt']}"
for corpo, detalhe in zip(notas, [detalhe_categorias, detalhe_recomendacoes]):
    assert corpo.endswith(f'<div class="nota-detalhe">{detalhe}</div></div></div>'), corpo
titulos = [c for c in blocos_html(at) if 'secao-numero">' in c]
assert ['secao-primeira' in c for c in titulos] == [True, False, False, False, False]
topo = next(c for c in blocos_html(at) if 'class="topo"' in c)
for etiqueta in [">Dados fictícios<", ">Pedidos de IA hoje: 15 de 15<", ">GitHub<"]:
    assert etiqueta in topo, etiqueta
inicio = AppTest.from_file("app.py", default_timeout=60).run()
assert not inicio.info
assert any('ⓘ</span><div><span>Envie um CSV' in c for c in blocos_html(inicio))
assert not any('class="nota-detalhe"' in c for c in blocos_html(inicio))
print("OK: notas no lugar de st.info e etiquetas com inicial maiúscula")
print(f"OK: detalhes das notas: {detalhe_categorias} | {detalhe_recomendacoes}")
print("OK: só o título 01 fica sem a linha divisória")

cartoes_resumo = next(c for c in blocos_html(at) if 'class="cartoes"><div class="cartao"' in c
                      and ">Sobra<" in c)
assert '<div class="cartao-explicacao">Renda menos consumo, antes de investir</div></div></div>' in cartoes_resumo
assert "title=" not in cartoes_resumo, "a explicação não pode depender do mouse"
print("OK: explicação da Sobra sempre visível")

assert categorizador.pedidos_restantes() == categorizador.LIMITE_DIARIO_APP
print("OK: nenhum pedido ao Gemini")
