import json
from functools import lru_cache

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()  # carrega o .env; o genai.Client() lê a GEMINI_API_KEY sozinho

MODELO = "gemini-3.5-flash"  # fácil de trocar
VERSAO_PROMPT = "v2-regras"  # para comparar versões do prompt depois

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


def categorizar_lote(transacoes):
    """Recebe lista de {id, descricao, valor} e devolve lista de {id, categoria}."""
    # Garante tipos simples (ids como texto, valores como número) para o JSON
    entrada = [
        {"id": str(t["id"]), "descricao": str(t["descricao"]), "valor": float(t["valor"])}
        for t in transacoes
    ]

    resposta = _obter_client().models.generate_content(
        model=MODELO,
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
        raise ValueError("O Gemini não devolveu um JSON válido.") from e

    _validar(entrada, resultado)
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
