"""Marcadores e conferência das recomendações.

O LLM recebe uma lista de marcadores (com valor e significado) e escreve usando os
MARCADORES, nunca os números. O Python confere a resposta e troca cada marcador pelo valor
formatado. Assim o LLM não consegue inventar nem calcular números.
"""

import json
import re
import time

from google.genai import types

from categorizador import (
    ESPERAS_TENTATIVAS,
    MODELO,
    MODELO_RESERVA,
    ErroGemini,
    ErroValidacao,
    _cota_diaria,
    _erro_temporario,
    _obter_client,
    registrar_pedido,
)

CAMPOS = ["renda", "renda_fixa", "renda_extra", "consumo", "fixo", "variavel", "sobra"]
_NOME_CAMPO = {
    "renda": "renda",
    "renda_fixa": "renda fixa",
    "renda_extra": "renda extra",
    "consumo": "consumo",
    "fixo": "gasto fixo",
    "variavel": "gasto variável",
    "sobra": "sobra",
}
_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
          "agosto", "setembro", "outubro", "novembro", "dezembro"]
CAMPOS_RECOMENDACAO = ["titulo", "diagnostico", "acao"]
NUMERO_RECOMENDACOES = 3
# Palavras que levam a números ou contas escritos por extenso; o LLM não pode usá-las.
EXPRESSOES_PROIBIDAS = ["por cento", "reais", "metade", "dobro", "triplo"]
VERSAO_PROMPT_RECOMENDACOES = "r2"

# Marcador = texto entre { e }, sem chaves dentro.
_PADRAO_MARCADOR = re.compile(r"\{[^{}]*\}")


def formatar_reais(valor):
    """Texto no formato brasileiro: 'R$ 1.350,00'; negativo '-R$ 16,95'; zero 'R$ 0,00'."""
    valor = round(float(valor), 2)
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-R$ {texto}" if valor < 0 else f"R$ {texto}"


def _mes_extenso(mes):
    """'2026-10' -> 'outubro de 2026'."""
    ano, numero = mes.split("-")
    return f"{_MESES[int(numero) - 1]} de {ano}"


def _texto_diferenca(valor):
    """Direção escrita pelo Python: 'alta de R$ X', 'queda de R$ X' ou 'variação de R$ 0,00'."""
    valor = round(float(valor), 2)
    if valor > 0:
        return f"alta de {formatar_reais(valor)}"
    if valor < 0:
        return f"queda de {formatar_reais(abs(valor))}"
    return "variação de R$ 0,00"


def montar_marcadores(pacote):
    """Dict {marcador: {"texto", "significado"}} a partir do dict de montar_pacote()."""
    marcadores = {}
    primeiro, ultimo = pacote["meses"][0], pacote["meses"][-1]
    intervalo = f"{_mes_extenso(ultimo)} menos {_mes_extenso(primeiro)}"

    for linha in pacote["mensal"]:
        for campo in CAMPOS:
            marcadores[f"{{{linha['mes']}.{campo}}}"] = {
                "texto": formatar_reais(linha[campo]),
                "significado": f"{_NOME_CAMPO[campo]} de {_mes_extenso(linha['mes'])}",
            }

    for campo in CAMPOS:
        marcadores[f"{{diferenca.{campo}}}"] = {
            "texto": _texto_diferenca(pacote["diferenca_primeiro_ultimo_mes"][campo]),
            "significado": f"{_NOME_CAMPO[campo]}: {intervalo}",
        }

    significados_totais = {
        "renda": "renda total do período",
        "consumo": "consumo total do período",
        "sobra": "sobra total do período (renda - consumo)",
        "investimentos_aplicados": "total aplicado em investimentos no período",
    }
    for campo, significado in significados_totais.items():
        marcadores[f"{{total.{campo}}}"] = {
            "texto": formatar_reais(pacote["totais"][campo]),
            "significado": significado,
        }

    for linha in pacote["variavel_por_categoria"]:
        cat = linha["categoria"]
        for mes in pacote["meses"]:
            marcadores[f"{{{cat}.{mes}}}"] = {
                "texto": formatar_reais(linha[mes]),
                "significado": f"gasto variável com {cat} em {_mes_extenso(mes)}",
            }
        marcadores[f"{{{cat}.diferenca}}"] = {
            "texto": _texto_diferenca(linha["diferenca"]),
            "significado": f"gasto variável com {cat}: {intervalo}",
        }

    for i, fixo in enumerate(pacote["gastos_fixos"], start=1):
        marcadores[f"{{fixo_{i}}}"] = {
            "texto": formatar_reais(fixo["gasto_medio"]),
            "significado": "gasto fixo mensal médio: " + fixo["descricao"],
        }
    return marcadores


def lista_para_prompt(marcadores):
    """Uma linha por marcador: '{2026-10.sobra} -> R$ 1.400,46 (sobra de outubro de 2026)'."""
    return "\n".join(
        f"{m} -> {d['texto']} ({d['significado']})" for m, d in marcadores.items()
    )


def validar_resposta(resposta, marcadores):
    """Confere a resposta do LLM; levanta ErroValidacao em português se algo estiver errado.

    Exige 3 recomendações com titulo, diagnostico e acao preenchidos, só marcadores que
    existem, nenhuma chave solta e nenhum dígito fora dos marcadores.
    """
    if not isinstance(resposta, dict) or not isinstance(resposta.get("recomendacoes"), list):
        raise ErroValidacao('A resposta precisa ser um objeto com a lista "recomendacoes".')
    itens = resposta["recomendacoes"]
    if len(itens) != NUMERO_RECOMENDACOES:
        raise ErroValidacao(
            f"Esperadas {NUMERO_RECOMENDACOES} recomendações, vieram {len(itens)}."
        )

    for n, item in enumerate(itens, start=1):
        for campo in CAMPOS_RECOMENDACAO:
            valor = item.get(campo) if isinstance(item, dict) else None
            if not isinstance(valor, str) or not valor.strip():
                raise ErroValidacao(
                    f'Recomendação {n}: o campo "{campo}" está ausente ou vazio.'
                )

            for marcador in _PADRAO_MARCADOR.findall(valor):
                if marcador not in marcadores:
                    raise ErroValidacao(
                        f'Recomendação {n}, campo "{campo}": marcador inexistente {marcador}.'
                    )

            sem_marcadores = _PADRAO_MARCADOR.sub("", valor)
            if "{" in sem_marcadores or "}" in sem_marcadores:
                raise ErroValidacao(
                    f'Recomendação {n}, campo "{campo}": marcador malformado em "{valor}".'
                )
            for expressao in EXPRESSOES_PROIBIDAS:
                if expressao in sem_marcadores.lower():
                    raise ErroValidacao(
                        f'Recomendação {n}, campo "{campo}": expressão proibida "{expressao}".'
                    )
            achado = re.search(r"\d", sem_marcadores)
            if achado:
                inicio = max(0, achado.start() - 15)
                trecho = sem_marcadores[inicio:achado.end() + 15]
                raise ErroValidacao(
                    f'Recomendação {n}, campo "{campo}": número escrito à mão perto de '
                    f'"{trecho}". Use só marcadores.'
                )


def preencher(texto, marcadores):
    """Troca cada marcador do texto pelo seu 'texto' formatado."""
    return _PADRAO_MARCADOR.sub(
        lambda m: marcadores[m.group(0)]["texto"] if m.group(0) in marcadores else m.group(0),
        texto,
    )


def preencher_resposta(resposta, marcadores):
    """Lista das 3 recomendações com titulo, diagnostico e acao já preenchidos."""
    return [
        {campo: preencher(item[campo], marcadores) for campo in CAMPOS_RECOMENDACAO}
        for item in resposta["recomendacoes"]
    ]


PROMPT_R2 = """\
Você é um assistente de educação financeira. Escreva exatamente 3 recomendações para uma pessoa, a partir de um resumo do extrato bancário dela de {n_meses} meses.

COMO ESCREVER NÚMEROS (regra mais importante)
- Você NÃO pode escrever nenhum número, valor ou porcentagem. Onde precisar de um valor, copie o MARCADOR exatamente como está na lista abaixo, com as chaves. O sistema troca cada marcador pelo valor.
- Não faça contas: nada de somas, médias, porcentagens, proporções ou projeções. Não use as palavras "reais", "por cento", "metade", "dobro" ou "triplo".
- Contagens de tempo vão por extenso (ex.: "três meses") e meses pelo nome (ex.: "outubro").
- Os marcadores de diferença já trazem a direção: viram "alta de R$ ...", "queda de R$ ..." ou "variação de R$ 0,00". Escreva, por exemplo, "a sobra teve {diferenca.sobra}", sem verbos como "subiu" ou "caiu" antes deles.

DEFINIÇÕES
- Consumo: gastos do dia a dia, sem transferências e investimentos.
- Gasto fixo: aparece uma vez por mês, todo mês, com valor estável (ex.: aluguel, assinaturas). Gasto variável: o resto do consumo.
- Renda fixa: entrada que se repete todo mês (ex.: salário). Renda extra: entradas que não se repetem (ex.: trabalhos avulsos).
- Sobra: renda menos consumo, antes de investimentos e transferências.
- Categoria "Outros": gastos que não se encaixam nas outras categorias, como saques em dinheiro.

CONTEÚDO
- Priorize o que tem mais impacto em reais: categorias com valores mensais altos ou com altas grandes. Não faça recomendação sobre uma categoria cujo valor mensal é pequeno perto das outras.
- Se a queda da sobra vier principalmente da renda extra, diga isso; não atribua ao consumo uma queda que vem da renda.
- Gastos fixos são difíceis de cortar no curto prazo: não faça as três recomendações sobre eles.
- Quando sugerir um limite ou uma meta, use um marcador como referência (ex.: o valor do primeiro mês da categoria).
- Cada recomendação tem: titulo (curto), diagnostico (o que os números mostram) e acao (o que a pessoa pode fazer, de forma concreta).
- Fale com a pessoa usando "você", em português do Brasil, com tom de educação financeira. Não indique produtos financeiros, bancos ou investimentos específicos.

MARCADORES DISPONÍVEIS
{lista}"""

_NUMEROS_POR_EXTENSO = {
    3: "três", 4: "quatro", 5: "cinco", 6: "seis", 7: "sete", 8: "oito",
    9: "nove", 10: "dez", 11: "onze", 12: "doze",
}

SCHEMA_RECOMENDACOES = {
    "type": "OBJECT",
    "properties": {
        "recomendacoes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {campo: {"type": "STRING"} for campo in CAMPOS_RECOMENDACAO},
                "required": CAMPOS_RECOMENDACAO,
            },
        }
    },
    "required": ["recomendacoes"],
}


def montar_prompt(pacote, marcadores):
    """Prompt r2: troca só {n_meses} (por extenso) e {lista}; o resto fica literal."""
    n = len(pacote["meses"])
    por_extenso = _NUMEROS_POR_EXTENSO.get(n, str(n))
    return PROMPT_R2.replace("{n_meses}", por_extenso).replace(
        "{lista}", lista_para_prompt(marcadores)
    )


def _chamar_gemini(prompt, modelo):
    """Chamada real à API; devolve o texto da resposta."""
    cliente = _obter_client()  # sem chave, falha aqui e não conta pedido
    registrar_pedido()
    resposta = cliente.models.generate_content(
        model=modelo,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=SCHEMA_RECOMENDACOES,
        ),
    )
    return resposta.text


def _obter_resposta(chamar, prompt, modelo, marcadores):
    """Chama, lê o JSON e valida. Levanta ErroValidacao se a resposta for recusada."""
    texto = chamar(prompt, modelo)
    try:
        resposta = json.loads(texto)
    except (TypeError, json.JSONDecodeError) as e:
        raise ErroValidacao("A resposta não veio como um JSON válido.") from e
    validar_resposta(resposta, marcadores)
    return resposta


def _tentar(chamar, prompt_base, modelo, marcadores):
    """Devolve (resposta, tentativas_extras).

    Resposta recusada: 1 nova tentativa com o motivo no prompt. Erro temporário: até 3
    novas tentativas, com as esperas de ESPERAS_TENTATIVAS. Outros erros sobem na hora.
    """
    prompt = prompt_base
    extras = 0
    esperas_usadas = 0
    recusou = False
    while True:
        try:
            return _obter_resposta(chamar, prompt, modelo, marcadores), extras
        except ErroValidacao as e:
            if recusou:
                raise
            recusou = True
            extras += 1
            prompt = (
                prompt_base
                + f"\n\nSua resposta anterior foi recusada pelo motivo: {e}. "
                "Corrija e responda de novo seguindo todas as regras."
            )
        except Exception as e:
            if not _erro_temporario(e) or esperas_usadas >= len(ESPERAS_TENTATIVAS):
                raise
            time.sleep(ESPERAS_TENTATIVAS[esperas_usadas])
            esperas_usadas += 1
            extras += 1


def gerar_recomendacoes(pacote, chamar=None):
    """Pede as 3 recomendações ao Gemini, confere e troca os marcadores pelos valores.

    chamar: função opcional (prompt, modelo) -> texto, só para testes; None = API de verdade.
    Esgotadas as tentativas por erro temporário, tenta uma vez o MODELO_RESERVA; com a
    cota diária esgotada, vai direto para ele, sem esperas. Se tudo falhar, levanta
    ErroGemini, um RuntimeError (nenhuma recomendação é devolvida).
    """
    chamar = chamar or _chamar_gemini
    marcadores = montar_marcadores(pacote)
    prompt = montar_prompt(pacote, marcadores)

    modelo = MODELO
    try:
        resposta, extras = _tentar(chamar, prompt, MODELO, marcadores)
    except Exception as e:
        if not (_erro_temporario(e) or _cota_diaria(e)):
            raise ErroGemini(
                f"Não foi possível gerar as recomendações: {type(e).__name__}: {e}", e
            ) from e
        extras = 1 if _cota_diaria(e) else len(ESPERAS_TENTATIVAS) + 1
        modelo = MODELO_RESERVA
        try:
            resposta = _obter_resposta(chamar, prompt, MODELO_RESERVA, marcadores)
        except Exception as e2:
            raise ErroGemini(
                f"Não foi possível gerar as recomendações. Modelo principal ({MODELO}): "
                f"{type(e).__name__}: {e}. Modelo reserva ({MODELO_RESERVA}): "
                f"{type(e2).__name__}: {e2}",
                e,
                e2,
            ) from e2

    return {
        "recomendacoes": preencher_resposta(resposta, marcadores),
        "resposta_bruta": resposta,
        "modelo": modelo,
        "versao_prompt": VERSAO_PROMPT_RECOMENDACOES,
        "tentativas_extras": extras,
    }
