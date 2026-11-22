import json
import time
from functools import lru_cache

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()  # carrega o .env; o genai.Client() lê a GEMINI_API_KEY sozinho

MODELO = "gemini-3.5-flash"  # fácil de trocar
MODELO_RESERVA = "gemini-3.5-flash-lite"  # usado se o principal falhar num lote
VERSAO_PROMPT = "v2-regras"  # para comparar versões do prompt depois

PAUSA_ENTRE_LOTES = 4  # segundos (limite do plano gratuito)
ESPERAS_TENTATIVAS = [5, 15, 30]  # segundos de espera antes de cada nova tentativa
CODIGOS_TEMPORARIOS = {408, 429, 500, 502, 503, 504}


class ErroValidacao(ValueError):
    """A resposta do Gemini veio, mas está incompleta ou inválida."""

CATEGORIAS = [
    "Moradia e contas",
    "Mercado",
    "Alimentação fora",
    "Transporte",
    "Saúde",
    "Educação",
    "Compras e serviços",
    "Lazer e assinaturas",
    "Transferências",
    "Renda",
    "Taxas e impostos",
    "Investimentos",
    "Outros",
]

# Formato da resposta: lista de {id, categoria}, com categoria limitada às 13
SCHEMA_RESPOSTA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "STRING"},
            "categoria": {"type": "STRING", "enum": CATEGORIAS},
        },
        "required": ["id", "categoria"],
    },
}


REGRAS = """\
- Princípio geral: a finalidade explícita na descrição prevalece sobre o tipo de \
transação (PIX, TED, maquininha) e sobre o nome da contraparte. \
Ex.: PIX com "aluguel" = Moradia e contas; PIX com "jantar" = Alimentação fora.
- PIX recebido de pessoa, sem finalidade explícita = Transferências. Só é Renda \
quando a descrição indica trabalho, salário ou empresa pagadora.
- Transferência entre contas próprias e pagamento de fatura do cartão = \
Transferências (movimentação interna, não é gasto novo).
- Maquininha (ex.: SumUp, Stone, PagSeguro) com nome identificável = categoria \
do nome; sem nome identificável = Compras e serviços.
- Farmácia (mesmo item de higiene) = Saúde.
- Recarga de celular = Moradia e contas (conta fixa).
- Padaria = Alimentação fora (não Mercado).
- Delivery de mercado (ex.: iFood Mercado) = Mercado.
- Delivery de comida (ex.: Uber Eats, 99 Food, iFood restaurante) = Alimentação fora.
- Aplicação ou resgate em RDB, CDB ou poupança = Investimentos.
- Estorno/reembolso: use a categoria do que a descrição indica estar sendo \
estornado; se não der para saber, use Outros."""

# Exemplos inventados de propósito (não vêm de dados/transacoes.csv)
EXEMPLOS = [
    ("PIX ENVIADO OTAVIO RAMOS - AULA DE VIOLAO", -120.00, "Educação"),
    ("PIX RECEBIDO ANDRE FARIAS", 60.00, "Transferências"),
    ("PIX RECEBIDO STUDIO LUME - PAGAMENTO PROJETO", 900.00, "Renda"),
    ("STONE *LOJA 8812", -45.00, "Compras e serviços"),
    ("PADARIA PAO DOURADO", -18.50, "Alimentação fora"),
    ("IFOOD *MERCADO VERDE", -112.30, "Mercado"),
    ("ESTORNO DROGARIA POPULAR", 27.40, "Saúde"),
    ("TIM RECARGA CELULAR", -30.00, "Moradia e contas"),
]


def _montar_prompt(transacoes):
    exemplos = "\n".join(f'- "{d}", {v:.2f} -> {c}' for d, v, c in EXEMPLOS)
    categorias = "\n".join(f"- {c}" for c in CATEGORIAS)
    return (
        "Você é um assistente que categoriza transações de um extrato bancário brasileiro.\n"
        "Valores negativos são saídas (gastos) e valores positivos são entradas.\n\n"
        f"Categorias permitidas:\n{categorias}\n\n"
        f"Regras:\n{REGRAS}\n\n"
        f"Exemplos (descrição, valor -> categoria):\n{exemplos}\n\n"
        "Transações a categorizar (JSON):\n"
        + json.dumps(transacoes, ensure_ascii=False)
        + "\n\nDevolva uma categoria para cada id recebido, sem omitir nenhum."
    )


@lru_cache(maxsize=1)
def _obter_client():
    """Cria o cliente do Gemini uma vez só e reaproveita nas próximas chamadas."""
    try:
        return genai.Client()
    except Exception as e:
        raise RuntimeError(
            "Não foi possível iniciar o cliente do Gemini. "
            "Confira se o arquivo .env existe e tem a GEMINI_API_KEY preenchida."
        ) from e


def categorizar_lote(transacoes, modelo=MODELO):
    """Recebe lista de {id, descricao, valor} e devolve lista de {id, categoria}."""
    # Garante tipos simples (ids como texto, valores como número) para o JSON
    entrada = [
        {"id": str(t["id"]), "descricao": str(t["descricao"]), "valor": float(t["valor"])}
        for t in transacoes
    ]

    resposta = _obter_client().models.generate_content(
        model=modelo,
        contents=_montar_prompt(entrada),
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=SCHEMA_RESPOSTA,
        ),
    )

    try:
        resultado = json.loads(resposta.text)
    except (TypeError, json.JSONDecodeError) as e:
        raise ErroValidacao("O Gemini não devolveu um JSON válido.") from e

    try:
        _validar(entrada, resultado)
    except ValueError as e:
        raise ErroValidacao(str(e)) from e
    return resultado


def _validar(entrada, resultado):
    """Confere se todos os ids voltaram e se todas as categorias são válidas."""
    if not isinstance(resultado, list):
        raise ValueError("A resposta do Gemini não veio como uma lista.")

    ids_enviados = {t["id"] for t in entrada}
    ids_recebidos = [str(r.get("id")) for r in resultado if isinstance(r, dict)]

    faltando = sorted(ids_enviados - set(ids_recebidos))
    if faltando:
        raise ValueError(f"O Gemini não devolveu categoria para os ids: {', '.join(faltando)}.")

    extras = sorted(set(ids_recebidos) - ids_enviados)
    if extras:
        raise ValueError(f"O Gemini devolveu ids que não foram enviados: {', '.join(extras)}.")

    if len(ids_recebidos) != len(set(ids_recebidos)):
        raise ValueError("O Gemini devolveu o mesmo id mais de uma vez.")

    for r in resultado:
        if r.get("categoria") not in CATEGORIAS:
            raise ValueError(
                f"Categoria inválida para o id {r.get('id')}: {r.get('categoria')!r}. "
                "Ela não está na lista das 13 categorias."
            )


def _erro_temporario(erro):
    """True para erros que costumam passar sozinhos: 503, 429, conexão derrubada, timeout."""
    codigo = getattr(erro, "code", None)
    if isinstance(codigo, int):
        return codigo in CODIGOS_TEMPORARIOS
    if isinstance(erro, (ConnectionError, TimeoutError)):
        return True
    # Erros de rede da biblioteca HTTP usada pelo google-genai (httpx/httpcore)
    return type(erro).__module__.split(".")[0].startswith(("httpx", "httpcore"))


def _tentar_lote(lote, modelo):
    """Chama categorizar_lote com tentativas automáticas.

    Devolve (resultado, tentativas_extras). Erros temporários: até 3 novas tentativas
    (espera de 5, 15 e 30 s). Erro de validação: 1 nova tentativa. Outros erros: sobem na hora.
    """
    extras = 0
    esperas_usadas = 0
    revalidou = False
    while True:
        try:
            return categorizar_lote(lote, modelo), extras
        except ErroValidacao:
            if revalidou:
                raise
            revalidou = True
            extras += 1
        except Exception as e:
            if not _erro_temporario(e) or esperas_usadas >= len(ESPERAS_TENTATIVAS):
                raise
            time.sleep(ESPERAS_TENTATIVAS[esperas_usadas])
            esperas_usadas += 1
            extras += 1


def _categorizar_lote_resiliente(lote, numero):
    """Tenta o modelo principal e, se esgotar as tentativas, o modelo reserva uma vez.

    Devolve (lista de {id, categoria, modelo}, tentativas_extras).
    """
    try:
        resultado, extras = _tentar_lote(lote, MODELO)
        modelo_usado = MODELO
    except Exception as e:
        if not (_erro_temporario(e) or isinstance(e, ErroValidacao)):
            raise RuntimeError(
                f"O lote {numero} falhou com um erro que não é temporário: "
                f"{type(e).__name__}: {e}"
            ) from e
        # Esgotou as tentativas com o modelo principal: 1 tentativa com o reserva
        extras = len(ESPERAS_TENTATIVAS) + 1
        try:
            resultado = categorizar_lote(lote, MODELO_RESERVA)
            modelo_usado = MODELO_RESERVA
        except Exception as e2:
            raise RuntimeError(
                f"O lote {numero} falhou. Modelo principal ({MODELO}): "
                f"{type(e).__name__}: {e}. Modelo reserva ({MODELO_RESERVA}): "
                f"{type(e2).__name__}: {e2}"
            ) from e2
    return [{**r, "modelo": modelo_usado} for r in resultado], extras


def categorizar_todos(transacoes, tamanho_lote=40, estatisticas=None, progresso=None):
    """Divide em lotes, categoriza cada um e junta. Devolve lista de {id, categoria, modelo}.

    estatisticas: dict opcional, preenchido com 'lotes' e 'tentativas_extras'.
    progresso: função opcional chamada como progresso(lote_atual, total_de_lotes).
    """
    lotes = [transacoes[i : i + tamanho_lote] for i in range(0, len(transacoes), tamanho_lote)]
    resultados = []
    tentativas_extras = 0

    for numero, lote in enumerate(lotes, start=1):
        parcial, extras = _categorizar_lote_resiliente(lote, numero)
        resultados.extend(parcial)
        tentativas_extras += extras
        if progresso:
            progresso(numero, len(lotes))
        if numero < len(lotes):
            time.sleep(PAUSA_ENTRE_LOTES)

    if estatisticas is not None:
        estatisticas["lotes"] = len(lotes)
        estatisticas["tentativas_extras"] = tentativas_extras
    return resultados
