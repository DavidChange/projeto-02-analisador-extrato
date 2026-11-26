import json
import threading
import time
from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()  # carrega o .env; o genai.Client() lê a GEMINI_API_KEY sozinho

MODELO = "gemini-3.5-flash"  # fácil de trocar
MODELO_RESERVA = "gemini-3.5-flash-lite"  # usado se o principal falhar num lote
VERSAO_PROMPT = "v2-regras"  # para comparar versões do prompt depois

TAMANHO_LOTE = 40  # transações por pedido
PAUSA_ENTRE_LOTES = 4  # segundos (limite do plano gratuito)
ESPERAS_TENTATIVAS = [5, 15, 30]  # segundos de espera antes de cada nova tentativa
CODIGOS_TEMPORARIOS = {408, 429, 500, 502, 503, 504}

# Limite de pedidos por dia feitos pelo app, para proteger a cota do app público
LIMITE_DIARIO_APP = 15
FUSO_DA_COTA = ZoneInfo("America/Los_Angeles")  # a cota do Google renova à meia-noite de lá
FRASE_LIMITE_APP = (
    "O limite diário de demonstração foi atingido. Ele volta por volta das 5h "
    '(horário de Brasília). Enquanto isso, use "Usar dados de exemplo".'
)


class ErroValidacao(ValueError):
    """A resposta do Gemini veio, mas está incompleta ou inválida."""


class ErroChave(RuntimeError):
    """Não foi possível iniciar o cliente do Gemini (em geral, chave ausente)."""


class ErroGemini(RuntimeError):
    """Falha final de uma chamada ao Gemini.

    A mensagem é o texto técnico; `erros` guarda os erros originais, na ordem
    (modelo principal e, se foi chamado, modelo reserva), para explicar_erro().
    """

    def __init__(self, mensagem, *erros):
        super().__init__(mensagem)
        self.erros = erros


class ErroLimiteApp(RuntimeError):
    """O limite diário do app não permite o pedido; nada é enviado à API."""

    def __init__(self, mensagem=FRASE_LIMITE_APP):
        super().__init__(mensagem)


# Contador em variável do módulo: é o mesmo para todos os visitantes do app
_trava_contador = threading.Lock()
_dia_contado = None
_pedidos_feitos = 0


def _agora():
    """Data e hora atuais (função separada para os testes trocarem o relógio)."""
    return datetime.now(timezone.utc)


def _zerar_se_virou_o_dia():
    """Zera o contador quando muda a data no fuso da cota. Chamar com a trava fechada."""
    global _dia_contado, _pedidos_feitos
    hoje = _agora().astimezone(FUSO_DA_COTA).date()
    if hoje != _dia_contado:
        _dia_contado = hoje
        _pedidos_feitos = 0


def pedidos_restantes():
    """Quantos pedidos ao Gemini o app ainda pode fazer hoje."""
    with _trava_contador:
        _zerar_se_virou_o_dia()
        return max(0, LIMITE_DIARIO_APP - _pedidos_feitos)


def registrar_pedido():
    """Conta 1 pedido antes de chamar a API; levanta ErroLimiteApp se não houver saldo."""
    global _pedidos_feitos
    with _trava_contador:
        _zerar_se_virou_o_dia()
        if _pedidos_feitos >= LIMITE_DIARIO_APP:
            raise ErroLimiteApp()
        _pedidos_feitos += 1


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
        raise ErroChave(
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

    cliente = _obter_client()  # sem chave, falha aqui e não conta pedido
    registrar_pedido()
    resposta = cliente.models.generate_content(
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


def _cota_diaria(erro):
    """True para o 429 de cota diária, que não passa com novas tentativas no mesmo dia."""
    return getattr(erro, "code", None) == 429 and "perday" in str(erro).lower()


def _erro_de_conexao(erro):
    """True para conexão derrubada ou timeout."""
    if isinstance(erro, (ConnectionError, TimeoutError)):
        return True
    # Erros de rede da biblioteca HTTP usada pelo google-genai (httpx/httpcore)
    return type(erro).__module__.split(".")[0].startswith(("httpx", "httpcore"))


def _erro_temporario(erro):
    """True para erros que costumam passar sozinhos: 503, 429, conexão derrubada, timeout.

    O 429 de cota diária não conta como temporário.
    """
    if _cota_diaria(erro):
        return False
    codigo = getattr(erro, "code", None)
    if isinstance(codigo, int):
        return codigo in CODIGOS_TEMPORARIOS
    return _erro_de_conexao(erro)


def _frase_do_erro(erro):
    """Frase curta em português para um erro só, sem o texto bruto da API."""
    if isinstance(erro, ErroLimiteApp):
        return str(erro)  # a mensagem já é nossa, em português
    if _cota_diaria(erro):
        return (
            "A cota diária gratuita do Gemini acabou e se renova por volta das 5h "
            '(horário de Brasília). Enquanto isso, use "Usar dados de exemplo".'
        )
    codigo = getattr(erro, "code", None)
    if codigo == 429:  # a cota diária já foi tratada acima: aqui é o limite por minuto
        return "Foram muitos pedidos ao Gemini em pouco tempo. Espere um minuto e tente de novo."
    if codigo in (500, 502, 503, 504):
        return "O Gemini está sobrecarregado ou fora do ar. Tente de novo em alguns minutos."
    if codigo == 408 or _erro_de_conexao(erro):
        return "A conexão com o Gemini caiu ou demorou demais. Confira a internet e tente de novo."
    texto = str(erro).lower()
    chave_recusada = codigo == 400 and ("api_key_invalid" in texto or "api key" in texto)
    if chave_recusada or codigo in (401, 403) or isinstance(erro, ErroChave):
        return (
            "O Gemini não aceitou o acesso: a chave da API pode estar inválida ou ausente. "
            "Confira a GEMINI_API_KEY."
        )
    return (
        "Não foi possível obter uma resposta válida do Gemini. "
        'Tente de novo mais tarde ou use "Usar dados de exemplo".'
    )


def explicar_erro(erro):
    """Frase em português para mostrar ao usuário.

    Se o modelo principal e o reserva falharam por motivos diferentes, explica os dois.
    """
    erros = getattr(erro, "erros", None) if isinstance(erro, ErroGemini) else None
    frases = [_frase_do_erro(e) for e in (erros or (erro,))]
    if len(set(frases)) == 1:
        return frases[0]
    return f"Modelo principal: {frases[0]} Modelo reserva: {frases[1]}"


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

    Com a cota diária esgotada no principal, vai direto para o reserva, sem esperas.
    Devolve (lista de {id, categoria, modelo}, tentativas_extras).
    """
    try:
        resultado, extras = _tentar_lote(lote, MODELO)
        modelo_usado = MODELO
    except Exception as e:
        if not (_erro_temporario(e) or _cota_diaria(e) or isinstance(e, ErroValidacao)):
            raise ErroGemini(
                f"O lote {numero} falhou com um erro que não é temporário: "
                f"{type(e).__name__}: {e}",
                e,
            ) from e
        # Esgotou as tentativas (ou a cota diária) do principal: 1 tentativa com o reserva
        extras = 1 if _cota_diaria(e) else len(ESPERAS_TENTATIVAS) + 1
        try:
            resultado = categorizar_lote(lote, MODELO_RESERVA)
            modelo_usado = MODELO_RESERVA
        except Exception as e2:
            raise ErroGemini(
                f"O lote {numero} falhou. Modelo principal ({MODELO}): "
                f"{type(e).__name__}: {e}. Modelo reserva ({MODELO_RESERVA}): "
                f"{type(e2).__name__}: {e2}",
                e,
                e2,
            ) from e2
    return [{**r, "modelo": modelo_usado} for r in resultado], extras


def _chave_do_lote(lote):
    """Identifica um lote pelo conteúdo enviado: (id, descrição, valor) de cada transação."""
    return tuple((str(t["id"]), str(t["descricao"]), float(t["valor"])) for t in lote)


def categorizar_todos(
    transacoes, tamanho_lote=TAMANHO_LOTE, estatisticas=None, progresso=None, lotes_prontos=None
):
    """Divide em lotes, categoriza cada um e junta. Devolve lista de {id, categoria, modelo}.

    estatisticas: dict opcional, preenchido com 'lotes' e 'tentativas_extras'.
    progresso: função opcional chamada como progresso(lotes_concluidos, total_de_lotes).
    lotes_prontos: dict opcional {chave do lote: resultado}. Lote que já está nele não é
        chamado de novo, e cada lote concluído é gravado nele na hora; assim, se um lote
        falhar, a próxima chamada continua de onde parou.
    Se faltarem mais lotes que os pedidos restantes hoje, levanta ErroLimiteApp sem chamar
    a API.
    """
    prontos = {} if lotes_prontos is None else lotes_prontos
    lotes = [transacoes[i : i + tamanho_lote] for i in range(0, len(transacoes), tamanho_lote)]
    chaves = [_chave_do_lote(lote) for lote in lotes]
    faltam = [i for i, chave in enumerate(chaves) if chave not in prontos]

    restantes = pedidos_restantes()
    if len(faltam) > restantes:
        raise ErroLimiteApp(
            f"Esta categorização precisa de pelo menos {len(faltam)} pedidos ao Gemini, e o "
            f"limite diário de demonstração só tem {restantes} restantes. Ele volta por volta "
            'das 5h (horário de Brasília). Enquanto isso, use "Usar dados de exemplo".'
        )
    tentativas_extras = 0

    for posicao, i in enumerate(faltam, start=1):
        parcial, extras = _categorizar_lote_resiliente(lotes[i], i + 1)
        prontos[chaves[i]] = parcial
        tentativas_extras += extras
        if progresso:
            progresso(len(lotes) - len(faltam) + posicao, len(lotes))
        if posicao < len(faltam):
            time.sleep(PAUSA_ENTRE_LOTES)

    if estatisticas is not None:
        estatisticas["lotes"] = len(lotes)
        estatisticas["tentativas_extras"] = tentativas_extras
    return [resultado for chave in chaves for resultado in prontos[chave]]
