"""Animação de partículas: cada ponto representa um pedaço do consumo.

Gera um HTML completo (canvas + JavaScript, sem bibliotecas externas). Os pontos aparecem
misturados e, a pedido, voam para um grupo por categoria.
"""

import html
import json

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


def html_particulas(gastos, periodo):
    """HTML completo da animação.

    gastos: DataFrame de gasto_por_categoria() (colunas categoria e gasto).
    periodo: texto do período, ex.: 'ago/2026 a out/2026'.
    """
    total = float(gastos["gasto"].sum())  # com os negativos, para bater com o consumo
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
    # "<" vira < para nenhum texto conseguir fechar a tag <script>
    dados = json.dumps(grupos, ensure_ascii=False).replace("<", "\\u003c")

    trocas = {
        "__TOTAL__": formatar_reais(total),
        "__PERIODO__": html.escape(str(periodo)),
        # espaço que não quebra: "R$" e o número ficam na mesma linha do título
        "__VALOR__": formatar_reais(valor).replace(" ", "&nbsp;"),
        "__PONTOS__": str(sum(pontos.values())),
    }
    pagina = MODELO_HTML
    for marcador, texto in trocas.items():
        pagina = pagina.replace(marcador, texto)
    return pagina.replace("__DADOS__", dados)  # por último: os dados não são mais trocados


MODELO_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Space+Grotesk:wght@400;600;700&display=swap">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #050506; color: #e9e7e4; font-family: 'Space Grotesk', sans-serif; }
.bloco { display: grid; grid-template-columns: minmax(230px, 1fr) 2fr; gap: 24px;
    align-items: center; }
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
.moldura { min-width: 0; background: #08080a; border: 1px solid #17171a; border-radius: 14px;
    overflow: hidden; }
canvas { display: block; width: 100%; }
@media (max-width: 640px) { .bloco { grid-template-columns: minmax(0, 1fr); } }
</style>
</head>
<body>
<div class="bloco">
  <div>
    <div class="rotulo">__TOTAL__ de consumo — __PERIODO__</div>
    <h1>Cada ponto são __VALOR__.</h1>
    <p class="frase">Neste extrato, __PONTOS__ pontos somam todo o consumo do período. Passe o
    mouse para mexer e depois veja a IA separar por categoria.</p>
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
const PASSO = 4.6;            // afastamento dos pontos dentro de um grupo
const ALTURA_MINIMA = 440;
const MARGEM = 18;
const ENTRE_COLUNAS = 22;
const ENTRE_LINHAS = 24;
const ALTURA_ROTULO = 40;     // nome e valor, em duas linhas
const ALCANCE_MOUSE = 80;
const ANGULO = Math.PI * (3 - Math.sqrt(5));
const FONTE_NOME = "600 12px 'Space Grotesk', sans-serif";
const FONTE_VALOR = "11px 'JetBrains Mono', monospace";

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
      fase: sortear() * Math.PI * 2, ritmo: 0.25 + sortear() * 0.35, x: null, y: null });
  }
});

let largura = 0;
let altura = ALTURA_MINIMA;
let centros = [];             // posição de cada grupo no modo categorizado
let categorizado = false;
let opacidadeRotulos = 0;
let mouse = null;
let quadro = null;
let ultimoTempo = null;

// Distribui os grupos (do maior para o menor) em fileiras centralizadas, sem se encostarem
function organizar() {
  const celulas = GRUPOS.map((grupo, g) => {
    const raio = PASSO * Math.sqrt(grupo.pontos) + RAIO;
    ctx.font = FONTE_NOME;
    const larguraNome = ctx.measureText(grupo.nome).width;
    ctx.font = FONTE_VALOR;
    const larguraValor = ctx.measureText(grupo.valor).width;
    return { g, raio, largura: Math.ceil(Math.max(2 * raio, larguraNome, larguraValor)) };
  });

  const fileiras = [];
  let fileira = null;
  for (const celula of celulas) {
    if (!fileira || fileira.largura + ENTRE_COLUNAS + celula.largura > largura - 2 * MARGEM) {
      fileira = { celulas: [], largura: -ENTRE_COLUNAS, raio: 0 };
      fileiras.push(fileira);
    }
    fileira.celulas.push(celula);
    fileira.largura += ENTRE_COLUNAS + celula.largura;
    fileira.raio = Math.max(fileira.raio, celula.raio);
  }

  const alturaFileiras = fileiras.reduce((s, f) => s + 2 * f.raio + ALTURA_ROTULO, 0)
    + ENTRE_LINHAS * Math.max(0, fileiras.length - 1);
  altura = Math.ceil(Math.max(ALTURA_MINIMA, alturaFileiras + 2 * MARGEM));

  centros = [];
  let topo = (altura - alturaFileiras) / 2;
  for (const f of fileiras) {
    let esquerda = (largura - f.largura) / 2;
    for (const celula of f.celulas) {
      centros[celula.g] = { x: esquerda + celula.largura / 2, y: topo + f.raio,
        raio: celula.raio, largura: celula.largura, baseRotulo: topo + 2 * f.raio + 18 };
      esquerda += celula.largura + ENTRE_COLUNAS;
    }
    topo += 2 * f.raio + ALTURA_ROTULO + ENTRE_LINHAS;
  }
}

function destino(p, segundos) {
  if (categorizado) {
    // Espiral de girassol: forma um grupo redondo com os pontos sem se sobrepor
    const c = centros[p.g];
    const distancia = PASSO * Math.sqrt(p.i + 0.5);
    return { x: c.x + distancia * Math.cos(p.i * ANGULO),
             y: c.y + distancia * Math.sin(p.i * ANGULO) };
  }
  let x = MARGEM + p.u * (largura - 2 * MARGEM);
  let y = MARGEM + p.v * (altura - 2 * MARGEM);
  if (!semAnimacao.matches) {
    x += Math.sin(segundos * p.ritmo + p.fase) * 9;
    y += Math.cos(segundos * p.ritmo * 0.8 + p.fase) * 9;
    if (mouse) {
      const dx = x - mouse.x;
      const dy = y - mouse.y;
      const d = Math.hypot(dx, dy) || 1;
      if (d < ALCANCE_MOUSE) {
        x += (dx / d) * (ALCANCE_MOUSE - d);
        y += (dy / d) * (ALCANCE_MOUSE - d);
      }
    }
  }
  return { x, y };
}

function desenhar(tempo) {
  const parado = semAnimacao.matches;
  // Quanto avançar neste quadro: a velocidade não depende dos quadros por segundo da tela
  const passados = ultimoTempo === null ? 16.7 : Math.min(250, Math.max(0, tempo - ultimoTempo));
  ultimoTempo = tempo;
  const avanco = 1 - Math.pow(1 - 0.07, passados / 16.7);
  const avancoRotulos = 1 - Math.pow(1 - 0.05, passados / 16.7);
  ctx.clearRect(0, 0, largura, altura);
  for (const p of pontos) {
    const alvo = destino(p, tempo / 1000);
    if (parado || p.x === null) {
      p.x = alvo.x;
      p.y = alvo.y;
    } else {
      p.x += (alvo.x - p.x) * avanco;
      p.y += (alvo.y - p.y) * avanco;
    }
    ctx.fillStyle = p.cor;
    ctx.beginPath();
    ctx.arc(p.x, p.y, RAIO, 0, Math.PI * 2);
    ctx.fill();
  }

  const alvoOpacidade = categorizado ? 1 : 0;
  opacidadeRotulos = parado ? alvoOpacidade
    : opacidadeRotulos + (alvoOpacidade - opacidadeRotulos) * avancoRotulos;
  if (opacidadeRotulos > 0.01) {
    ctx.globalAlpha = opacidadeRotulos;
    ctx.textAlign = 'center';
    GRUPOS.forEach((grupo, g) => {
      const c = centros[g];
      ctx.fillStyle = '#e9e7e4';
      ctx.font = FONTE_NOME;
      ctx.fillText(grupo.nome, c.x, c.baseRotulo);
      ctx.fillStyle = '#a5a3a0';
      ctx.font = FONTE_VALOR;
      ctx.fillText(grupo.valor, c.x, c.baseRotulo + 16);
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
  if (!largura) return;
  organizar();
  const escala = window.devicePixelRatio || 1;
  tela.width = Math.round(largura * escala);
  tela.height = Math.round(altura * escala);
  tela.style.height = altura + 'px';
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
semAnimacao.addEventListener('change', reiniciar);
new ResizeObserver(() => {
  if (moldura.clientWidth !== largura) ajustarTamanho();
}).observe(moldura);

ajustarTamanho();
// Os rótulos são medidos de novo quando as fontes terminam de carregar
Promise.all([document.fonts.load(FONTE_NOME), document.fonts.load(FONTE_VALOR)])
  .then(ajustarTamanho, () => {});
</script>
</body>
</html>
"""
