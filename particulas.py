"""Animação de partículas: cada ponto representa um pedaço do consumo.

Gera um HTML completo (canvas + JavaScript, sem bibliotecas externas). Os pontos aparecem
misturados e, a pedido, voam para um grupo por categoria.
"""

import html
import json
import re

from recomendador import formatar_reais

VALORES_POR_PONTO = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
MAXIMO_PONTOS = 400

CORES = {
    "Moradia e contas": "#ff7a4d",
    "Alimentação fora": "#f2b84b",
    "Mercado": "#5cc8b0",
    "Compras e serviços": "#7aa2ff",
    "Transporte": "#b18cff",
    "Lazer e assinaturas": "#ff7eb6",
    "Educação": "#b7d86a",
    "Saúde": "#6fd0f2",
    "Outros": "#c9b9a8",
    "Taxas e impostos": "#e86a6a",
}
COR_FORA_DA_LISTA = "#8a8890"
# Altura (px) do quadro onde o HTML é mostrado; cabe tudo em telas de 375 a 1280 px de largura
ALTURA_QUADRO = 560


def valor_por_ponto(total):
    """Menor valor da lista que dá no máximo 400 pontos.

    Se nem o maior valor bastar (total acima de R$ 2 milhões), devolve o maior.
    """
    for valor in VALORES_POR_PONTO:
        if total / valor <= MAXIMO_PONTOS:
            return valor
    return VALORES_POR_PONTO[-1]


def pontos_por_categoria(gastos, valor):
    """Dict categoria -> número de pontos, a partir do DataFrame de gasto_por_categoria().

    Toda categoria com gasto maior que zero tem pelo menos 1 ponto; sem gasto, 0.
    """
    return {
        categoria: max(1, round(gasto / valor)) if gasto > 0 else 0
        for categoria, gasto in zip(gastos["categoria"], gastos["gasto"])
    }


def html_particulas(gastos, periodo, total):
    """HTML completo da animação, para um quadro de altura ALTURA_QUADRO.

    O st.iframe executa o HTML como está, por isso todo texto é protegido antes de entrar:
    o período com html.escape; os nomes das categorias vão como texto JSON, com o sinal de
    menor trocado, e só são desenhados no canvas.

    gastos: DataFrame de gasto_por_categoria() (colunas categoria e gasto).
    periodo: texto do período, ex.: '01/08/2026 a 31/10/2026'.
    total: consumo do período, calculado em analise.py (resumo()["consumo"]).
    """
    valor = valor_por_ponto(total)
    pontos = pontos_por_categoria(gastos, valor)
    grupos = [
        {
            "nome": str(linha.categoria),
            "valor": formatar_reais(linha.gasto),
            "pontos": pontos[linha.categoria],
            "cor": CORES.get(linha.categoria, COR_FORA_DA_LISTA),
        }
        for linha in gastos.sort_values("gasto", ascending=False).itertuples()
        if pontos[linha.categoria] > 0
    ]
    # json.dumps protege aspas e barras; sem "<", nenhum nome fecha a tag <script>
    dados = json.dumps(grupos, ensure_ascii=False).replace("<", "\\u003c")

    # O valor por ponto é sempre inteiro: aparece sem centavos
    valor_curto = formatar_reais(valor).removesuffix(",00")
    trocas = {
        "__TOTAL__": html.escape(formatar_reais(total)),
        "__PERIODO__": html.escape(str(periodo)),
        # espaço que não quebra: "R$" e o número ficam na mesma linha do título
        "__VALOR__": html.escape(valor_curto).replace(" ", "&nbsp;"),
        "__PONTOS__": str(sum(pontos.values())),
        "__DADOS__": dados,
    }
    # Uma passada só: um texto já inserido nunca é lido de novo como marcador
    return re.sub("|".join(trocas), lambda achado: trocas[achado.group()], MODELO_HTML)


MODELO_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Space+Grotesk:wght@400;600;700&display=swap">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; overflow: hidden; background: #050506; }  /* cor da página */
body { color: #e9e7e4; font-family: 'Space Grotesk', sans-serif; }
.bloco { display: grid; grid-template-columns: minmax(300px, 1fr) 2fr;
    grid-template-rows: 100%; gap: 24px; height: 100%;
    /* o bloco inteiro é um cartão, no mesmo estilo dos cartões do app */
    background: #0b0b0d; border: 1px solid #1d1d21; border-radius: 14px; padding: 24px; }
.texto { align-self: center; }
.rotulo { font-family: 'JetBrains Mono', monospace; font-size: 12px; opacity: 0.65; }
h1 { font-size: 30px; line-height: 1.15; margin: 12px 0; }
.frase { font-size: 15px; line-height: 1.5; opacity: 0.8; }
.botoes { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
button { font-family: 'JetBrains Mono', monospace; font-size: 12px; cursor: pointer;
    color: #e9e7e4; background: #0b0b0d; border: 1px solid #1d1d21; border-radius: 999px;
    padding: 8px 14px; }
button:hover, button:focus-visible { border-color: #ff7a4d; }
button[aria-pressed="true"] { background: #ff7a4d; border-color: #ff7a4d; color: #050506;
    font-weight: 600; }
.moldura { position: relative; min-width: 0; min-height: 0; background: #08080a; border: 1px solid #17171a; border-radius: 14px;
    overflow: hidden; }
canvas { position: absolute; top: 0; left: 0; display: block; width: 100%; height: 100%; }
@media (max-width: 640px) {
    .bloco { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto minmax(0, 1fr);
        gap: 14px; }
    h1 { font-size: 23px; margin: 8px 0; }
    .frase { font-size: 14px; line-height: 1.4; }
    .botoes { margin-top: 12px; }
}
/* Telas muito estreitas (quadro de até 340 px): menos espaço, para os grupos caberem */
@media (max-width: 340px) {
    .bloco { padding: 12px; gap: 10px; }
    h1 { font-size: 20px; margin: 6px 0; }
    .rotulo { font-size: 11px; }
    .frase { font-size: 12.5px; line-height: 1.35; }
    .botoes { margin-top: 8px; gap: 6px; }
    button { font-size: 11px; padding: 6px 10px; }
}
</style>
</head>
<body>
<div class="bloco">
  <div class="texto">
    <div class="rotulo">__TOTAL__ de consumo — __PERIODO__</div>
    <h1>Cada ponto são __VALOR__.</h1>
    <p class="frase">Neste extrato, cada ponto vale __VALOR__: são __PONTOS__ pontos, com
    valores arredondados. Passe o mouse para mexer e depois veja a IA separar por categoria.</p>
    <div class="botoes">
      <button type="button" id="misturado" aria-pressed="true">Misturado</button>
      <button type="button" id="categorizado" aria-pressed="false">Categorizado pela IA</button>
    </div>
  </div>
  <div class="moldura">
    <canvas id="tela" role="img" aria-label="Pontos do consumo, um grupo de cor por categoria"></canvas>
  </div>
</div>
<script>
const GRUPOS = __DADOS__;
const RAIO = 3;               // todos os pontos têm o mesmo tamanho
// Arranjos dos grupos, do mais folgado ao mais compacto: vale o primeiro que couber
const ARRANJOS = [
  { passo: 4.6, margem: 18, colunas: 22, linhas: 24, rotulo: 40, nome: 12, valor: 11 },
  { passo: 4.3, margem: 12, colunas: 14, linhas: 14, rotulo: 36, nome: 11, valor: 10 },
  { passo: 4.1, margem: 8, colunas: 10, linhas: 10, rotulo: 34, nome: 11, valor: 10 },
  { passo: 3.5, margem: 6, colunas: 8, linhas: 6, rotulo: 30, nome: 10, valor: 9 },
  { passo: 2.8, margem: 4, colunas: 6, linhas: 4, rotulo: 28, nome: 9, valor: 9 },
];
const MARGEM = 18;            // borda livre no modo misturado
// Movimento: os valores valem por quadro, a 60 quadros por segundo
const QUADRO = 1000 / 60;     // duração de um quadro, em milissegundos
const AMPLITUDE = 14;         // quanto cada ponto oscila no modo misturado
const AVANCO_FASE = 0.01;
const MOLA = 0.012;
const AMORTECIMENTO = 0.86;
const RAIO_MOUSE = 95;
const FORCA_MOUSE = 2.2;
const ANGULO = Math.PI * (3 - Math.sqrt(5));
const fonteNome = (px) => `600 ${px}px 'Space Grotesk', sans-serif`;
const fonteValor = (px) => `${px}px 'JetBrains Mono', monospace`;

const tela = document.getElementById('tela');
const ctx = tela.getContext('2d');
const moldura = tela.parentElement;
const semAnimacao = window.matchMedia('(prefers-reduced-motion: reduce)');

// Sorteio com semente fixa: os pontos misturados saem sempre nos mesmos lugares
let semente = 7;
function sortear() {
  semente = (semente * 16807) % 2147483647;
  return semente / 2147483647;
}

const pontos = [];
GRUPOS.forEach((grupo, g) => {
  for (let i = 0; i < grupo.pontos; i++) {
    pontos.push({ g, i, cor: grupo.cor, u: sortear(), v: sortear(),
      fase: sortear() * Math.PI * 2, x: null, y: null, vx: 0, vy: 0 });
  }
});

let largura = 0;
let altura = 0;
let arranjo = ARRANJOS[0];
let centros = [];             // posição de cada grupo no modo categorizado
let categorizado = false;
let opacidadeRotulos = 0;
let mouse = null;
let quadro = null;
let ultimoTempo = null;
let sobra = 0;                // tempo ainda não transformado em quadros de movimento

// Distribui os grupos (do maior para o menor) em fileiras centralizadas, sem se encostarem
function montarFileiras(a) {
  const celulas = GRUPOS.map((grupo, g) => {
    const raio = a.passo * Math.sqrt(grupo.pontos) + RAIO;
    ctx.font = fonteNome(a.nome);
    const larguraNome = ctx.measureText(grupo.nome).width;
    ctx.font = fonteValor(a.valor);
    const larguraValor = ctx.measureText(grupo.valor).width;
    return { g, raio, largura: Math.ceil(Math.max(2 * raio, larguraNome, larguraValor)) };
  });

  const fileiras = [];
  let fileira = null;
  for (const celula of celulas) {
    if (!fileira || fileira.largura + a.colunas + celula.largura > largura - 2 * a.margem) {
      fileira = { celulas: [], largura: -a.colunas, raio: 0 };
      fileiras.push(fileira);
    }
    fileira.celulas.push(celula);
    fileira.largura += a.colunas + celula.largura;
    fileira.raio = Math.max(fileira.raio, celula.raio);
  }
  const total = fileiras.reduce((s, f) => s + 2 * f.raio + a.rotulo, 0)
    + a.linhas * Math.max(0, fileiras.length - 1);
  return { fileiras, total };
}

function organizar() {
  let montagem;
  for (const a of ARRANJOS) {
    arranjo = a;
    montagem = montarFileiras(a);
    if (montagem.total <= altura - 2 * a.margem) break;
  }

  centros = [];
  let topo = (altura - montagem.total) / 2;
  for (const f of montagem.fileiras) {
    let esquerda = (largura - f.largura) / 2;
    for (const celula of f.celulas) {
      centros[celula.g] = { x: esquerda + celula.largura / 2, y: topo + f.raio,
        raio: celula.raio, largura: celula.largura,
        baseRotulo: topo + 2 * f.raio + arranjo.nome + 5 };
      esquerda += celula.largura + arranjo.colunas;
    }
    topo += 2 * f.raio + arranjo.rotulo + arranjo.linhas;
  }
}

// Para onde a mola puxa o ponto
function destino(p) {
  if (categorizado) {
    // Espiral de girassol: forma um grupo redondo com os pontos sem se sobrepor
    const c = centros[p.g];
    const distancia = arranjo.passo * Math.sqrt(p.i + 0.5);
    return { x: c.x + distancia * Math.cos(p.i * ANGULO),
             y: c.y + distancia * Math.sin(p.i * ANGULO) };
  }
  let x = MARGEM + p.u * (largura - 2 * MARGEM);
  let y = MARGEM + p.v * (altura - 2 * MARGEM);
  if (!semAnimacao.matches) {
    x += Math.sin(p.fase) * AMPLITUDE;
    y += Math.cos(0.8 * p.fase) * AMPLITUDE;
  }
  return { x, y };
}

// Coloca o ponto direto no alvo, parado (primeiro desenho e movimento reduzido)
function assentar(p) {
  const alvo = destino(p);
  p.x = alvo.x;
  p.y = alvo.y;
  p.vx = 0;
  p.vy = 0;
}

// Um quadro de movimento: mola até o alvo, empurrão do mouse (nos dois modos) e amortecimento
function avancar() {
  for (const p of pontos) {
    p.fase += AVANCO_FASE;
    const alvo = destino(p);
    p.vx += (alvo.x - p.x) * MOLA;
    p.vy += (alvo.y - p.y) * MOLA;
    if (mouse) {
      const dx = p.x - mouse.x;
      const dy = p.y - mouse.y;
      const d2 = dx * dx + dy * dy;
      if (d2 < RAIO_MOUSE * RAIO_MOUSE) {
        const d = Math.sqrt(d2) || 1;
        const forca = (1 - d2 / (RAIO_MOUSE * RAIO_MOUSE)) * FORCA_MOUSE;
        p.vx += (dx / d) * forca;
        p.vy += (dy / d) * forca;
      }
    }
    p.vx *= AMORTECIMENTO;
    p.vy *= AMORTECIMENTO;
    p.x += p.vx;
    p.y += p.vy;
  }
  opacidadeRotulos += ((categorizado ? 1 : 0) - opacidadeRotulos) * 0.05;
}

function desenhar(tempo) {
  const parado = semAnimacao.matches;
  for (const p of pontos) {
    if (parado || p.x === null) assentar(p);
  }
  if (parado) {
    opacidadeRotulos = categorizado ? 1 : 0;
  } else {
    // Quadros que se passaram: a velocidade é a mesma em telas de 60 ou 120 Hz
    sobra += ultimoTempo === null ? 0 : Math.min(100, Math.max(0, tempo - ultimoTempo));
    while (sobra > QUADRO / 2) {
      avancar();
      sobra -= QUADRO;
    }
  }
  ultimoTempo = tempo;

  ctx.clearRect(0, 0, largura, altura);
  for (const p of pontos) {
    ctx.fillStyle = p.cor;
    ctx.beginPath();
    // Raio 3; só diminui (para todos) se o arranjo precisar ficar muito apertado
    ctx.arc(p.x, p.y, Math.min(RAIO, arranjo.passo * 0.75), 0, Math.PI * 2);
    ctx.fill();
  }

  if (opacidadeRotulos > 0.01) {
    ctx.globalAlpha = opacidadeRotulos;
    ctx.textAlign = 'center';
    GRUPOS.forEach((grupo, g) => {
      const c = centros[g];
      ctx.fillStyle = '#e9e7e4';
      ctx.font = fonteNome(arranjo.nome);
      ctx.fillText(grupo.nome, c.x, c.baseRotulo);
      ctx.fillStyle = '#a5a3a0';
      ctx.font = fonteValor(arranjo.valor);
      ctx.fillText(grupo.valor, c.x, c.baseRotulo + arranjo.valor + 4);
    });
    ctx.globalAlpha = 1;
  }
}

function animar(tempo) {
  desenhar(tempo);
  quadro = semAnimacao.matches ? null : requestAnimationFrame(animar);
}

function reiniciar() {
  if (quadro !== null) cancelAnimationFrame(quadro);
  quadro = null;
  animar(performance.now());
}

function ajustarTamanho() {
  largura = moldura.clientWidth;
  altura = moldura.clientHeight;
  if (!largura || !altura) return;
  organizar();
  const escala = window.devicePixelRatio || 1;
  tela.width = Math.round(largura * escala);
  tela.height = Math.round(altura * escala);
  ctx.setTransform(escala, 0, 0, escala, 0, 0);
  reiniciar();
}

function escolherModo(novo) {
  categorizado = novo;
  document.getElementById('misturado').setAttribute('aria-pressed', String(!novo));
  document.getElementById('categorizado').setAttribute('aria-pressed', String(novo));
  if (semAnimacao.matches) reiniciar();
}

document.getElementById('misturado').addEventListener('click', () => escolherModo(false));
document.getElementById('categorizado').addEventListener('click', () => escolherModo(true));
tela.addEventListener('pointermove', (e) => {
  const caixa = tela.getBoundingClientRect();
  mouse = { x: e.clientX - caixa.left, y: e.clientY - caixa.top };
});
tela.addEventListener('pointerleave', () => { mouse = null; });
tela.addEventListener('pointercancel', () => { mouse = null; });  // toque interrompido
semAnimacao.addEventListener('change', reiniciar);
new ResizeObserver(() => {
  if (moldura.clientWidth !== largura || moldura.clientHeight !== altura) ajustarTamanho();
}).observe(moldura);

ajustarTamanho();
// Os rótulos são medidos de novo quando as fontes terminam de carregar
Promise.all([document.fonts.load(fonteNome(12)), document.fonts.load(fonteValor(11))])
  .then(ajustarTamanho, () => {});
</script>
</body>
</html>
"""
