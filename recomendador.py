"""Marcadores e conferência das recomendações.

O LLM recebe uma lista de marcadores (com valor e significado) e escreve usando os
MARCADORES, nunca os números. O Python confere a resposta e troca cada marcador pelo valor
formatado. Assim o LLM não consegue inventar nem calcular números.
"""

import re

from categorizador import ErroValidacao

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
    """Direção escrita pelo Python: 'alta de R$ X', 'queda de R$ X' ou 'sem variação'."""
    valor = round(float(valor), 2)
    if valor > 0:
        return f"alta de {formatar_reais(valor)}"
    if valor < 0:
        return f"queda de {formatar_reais(abs(valor))}"
    return "sem variação"


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
