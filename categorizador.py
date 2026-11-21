import json

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()  # carrega o .env; o genai.Client() lê a GEMINI_API_KEY sozinho

MODELO = "gemini-3.5-flash"  # fácil de trocar

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


def _montar_prompt(transacoes):
    return (
        "Você categoriza transações de um extrato bancário brasileiro.\n"
        "Valores negativos são saídas (gastos) e valores positivos são entradas.\n"
        "Responda com uma categoria para cada id recebido, sem omitir nenhum.\n\n"
        "Transações (JSON):\n"
        + json.dumps(transacoes, ensure_ascii=False)
    )


def categorizar_lote(transacoes):
    """Recebe lista de {id, descricao, valor} e devolve lista de {id, categoria}."""
    # Garante tipos simples (ids como texto, valores como número) para o JSON
    entrada = [
        {"id": str(t["id"]), "descricao": str(t["descricao"]), "valor": float(t["valor"])}
        for t in transacoes
    ]

    try:
        client = genai.Client()
    except Exception as e:
        raise RuntimeError(
            "Não foi possível iniciar o cliente do Gemini. "
            "Confira se o arquivo .env existe e tem a GEMINI_API_KEY preenchida."
        ) from e

    resposta = client.models.generate_content(
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
