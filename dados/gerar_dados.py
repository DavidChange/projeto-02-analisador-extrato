#!/usr/bin/env python3
"""Gera dados SINTÉTICOS para o Projeto 2 (analisador de extrato).

Saídas (na pasta passada como argumento, padrão ./dados):
  transacoes.csv -> o que o app recebe: id, data, descricao, valor
  gabarito.csv   -> a resposta: id, categoria, ambigua, nota

Tudo é fictício: nomes, valores, estabelecimentos "de bairro".
Semente fixa: rodar de novo gera exatamente os mesmos arquivos.
"""
import calendar
import csv
import random
import sys
from datetime import date
from pathlib import Path

SEED = 42
rng = random.Random(SEED)
MESES = [(2026, 8), (2026, 9), (2026, 10)]

CATEGORIAS = [
    "Moradia e contas", "Mercado", "Alimentação fora", "Transporte", "Saúde",
    "Educação", "Compras e serviços", "Lazer e assinaturas", "Transferências",
    "Renda", "Taxas e impostos", "Investimentos", "Outros",
]

rows = []  # (data, descricao, valor, categoria, ambigua, nota)


def add(d, desc, valor, cat, amb=0, nota=""):
    assert cat in CATEGORIAS, cat
    rows.append((d, desc, round(valor, 2), cat, amb, nota))


def val(lo, hi):
    return round(rng.uniform(lo, hi), 2)


def dia(ano, mes, d):
    return date(ano, mes, min(d, calendar.monthrange(ano, mes)[1]))


def rdia(ano, mes):
    return date(ano, mes, rng.randint(1, calendar.monthrange(ano, mes)[1]))


# ---------- 1) Itens fixos, todo mês ----------
for ano, mes in MESES:
    add(dia(ano, mes, 5), "CREDITO SALARIO EMPRESA ALFA LTDA", 4200.00, "Renda")
    add(dia(ano, mes, 6), "APLICACAO RDB", -300.00, "Investimentos")
    add(dia(ano, mes, 7), "BOLETO MENSALIDADE FACULDADE", -399.00, "Educação")
    add(dia(ano, mes, 8), "DEBITO AUTOMATICO CLARO MOVEL", -49.90, "Moradia e contas", 1,
        "celular = conta fixa da casa")
    add(dia(ano, mes, 9), "SMARTFIT ACADEMIA", -89.90, "Saúde", 1,
        "academia = Saúde (decisão de regra; poderia ser Lazer)")
    add(dia(ano, mes, 10), "PIX ENVIADO IMOB CENTRAL - ALUGUEL", -1350.00, "Moradia e contas", 1,
        "parece PIX comum, mas a finalidade explícita (aluguel) prevalece")
    add(dia(ano, mes, 10), "BOLETO CONDOMINIO RES JARDINS", -380.00, "Moradia e contas")
    add(dia(ano, mes, 12), "DEBITO AUTOMATICO VIVO FIBRA", -99.90, "Moradia e contas")
    add(dia(ano, mes, rng.randint(15, 20)), "DEBITO AUTOMATICO ENEL ENERGIA", -val(110, 190),
        "Moradia e contas")
    add(dia(ano, mes, 15), "NETFLIX.COM", -39.90, "Lazer e assinaturas")
    add(dia(ano, mes, 16), "SPOTIFY", -21.90, "Lazer e assinaturas")
    add(dia(ano, mes, 17), "GOOGLE *GOOGLE ONE", -9.99, "Lazer e assinaturas")
    add(dia(ano, mes, 18), "OPENAI *CHATGPT SUBSCR", -110.00, "Lazer e assinaturas")
    add(dia(ano, mes, 18), "IOF COMPRA INTERNACIONAL", -3.85, "Taxas e impostos")
    add(dia(ano, mes, 20), "PAGAMENTO FATURA CARTAO", -val(1100, 1900), "Transferências", 1,
        "movimentação interna: não é gasto novo; excluir dos gráficos de gasto")
    add(dia(ano, mes, 28), "TARIFA PACOTE SERVICOS", -29.90, "Taxas e impostos")

# ---------- 2) Itens variáveis, por categoria ----------
PREFIXOS = ["COMPRA NO DEBITO - ", "COMPRA NO DEBITO - ", "COMPRA CARTAO ", ""]


def loja(nome):
    pre = rng.choice(PREFIXOS)
    suf = rng.choice(["", "", f" {rng.randint(10, 999):04d}"])
    return f"{pre}{nome}{suf}"


# categoria -> (qtd por mês, [(estabelecimento, min, max)])
VARIAVEL = {
    "Mercado": (14, [("SUPERMERCADO EXTRA", 40, 260), ("ATACADAO", 80, 380),
                     ("CARREFOUR EXPRESS", 20, 140), ("MERCADO DIA", 15, 110),
                     ("SUPERMERCADOS PAGUE MENOS", 30, 220), ("ACOUGUE BOI FORTE", 35, 150),
                     ("HORTIFRUTI VERDE VIVO", 15, 80), ("MERCADINHO SAO JORGE", 10, 70)]),
    "Alimentação fora": (22, [("RESTAURANTE SABOR CASEIRO", 28, 70), ("IFOOD *RESTAURANTE", 25, 90),
                              ("IFOOD *PIZZARIA NAPOLI", 45, 110), ("IFOOD *HAMBURGUERIA", 30, 85),
                              ("LANCHES DO BAIRRO", 15, 45), ("CAFE CENTRAL", 8, 30),
                              ("MCDONALDS", 20, 65), ("SUSHI HOUSE", 60, 180),
                              ("CHURRASCARIA GAUCHA", 70, 160)]),
    "Transporte": (15, [("UBER *TRIP", 9, 48), ("99 *CORRIDA", 9, 45),
                        ("AUTO POSTO 7 ESTRELAS", 80, 230), ("POSTO IPIRANGA", 70, 220),
                        ("BILHETE UNICO RECARGA", 20, 100), ("ESTACIONAMENTO CENTRO", 12, 40)]),
    "Saúde": (3, [("DROGARIA PACHECO", 15, 120), ("DROGA RAIA", 15, 140),
                  ("CLINICA SAUDE VIVA CONSULTA", 150, 300), ("LABORATORIO CENTRAL EXAMES", 60, 280),
                  ("ODONTO CLIN", 120, 350)]),
    "Compras e serviços": (6, [("MAGAZINE LUIZA", 80, 600), ("SHOPEE", 20, 200), ("RENNER", 70, 320),
                               ("ZARA", 120, 450), ("LOJAS AMERICANAS", 20, 150),
                               ("BARBEARIA DO CHICO", 40, 70), ("LAVANDERIA EXPRESS", 30, 90)]),
    "Lazer e assinaturas": (4, [("CINEMARK", 30, 80), ("STEAM GAMES", 20, 180),
                                ("INGRESSO.COM", 60, 250), ("BOLICHE CENTRAL", 50, 120)]),
    "Educação": (1, [("CURSO ONLINE UDEMY", 20, 90), ("PAPELARIA ESCOLAR", 15, 60)]),
    "Outros": (1, [("SAQUE CAIXA ELETRONICO 24H", 50, 300)]),
}

for ano, mes in MESES:
    for cat, (qtd, lojas) in VARIAVEL.items():
        for _ in range(qtd):
            nome, lo, hi = rng.choice(lojas)
            desc = nome if cat == "Outros" else loja(nome)
            add(rdia(ano, mes), desc, -val(lo, hi), cat)

NOMES = ["MARIA SOUZA", "CARLOS ALBERTO PEREIRA", "JOAO PEDRO LIMA", "ANA CLARA ROCHA",
         "LUCAS MENDES", "FERNANDA COSTA", "RAFAEL TORRES", "BEATRIZ NUNES"]
for ano, mes in MESES:
    for _ in range(4):
        add(rdia(ano, mes), f"PIX ENVIADO {rng.choice(NOMES)}", -val(20, 300), "Transferências")
    for _ in range(2):
        add(rdia(ano, mes), f"PIX RECEBIDO {rng.choice(NOMES)}", val(30, 400), "Transferências")

# ---------- 3) Casos ambíguos de propósito ----------
# (descrição, min, max, categoria, nota, sinal, repetições)
AMBIGUOS = [
    ("IFOOD *MERCADO BOM PRECO", 40, 160, "Mercado", "app de delivery, mas o que se compra é mercado", -1, 2),
    ("IFOOD *HORTIFRUTI DO ZE", 25, 90, "Mercado", "app de delivery, mas o que se compra é mercado", -1, 1),
    ("IFOOD *CASA DE CARNES", 45, 180, "Mercado", "app de delivery, mas o que se compra é mercado", -1, 1),
    ("RAPPI *MERCADO", 40, 170, "Mercado", "app de delivery, mas o que se compra é mercado", -1, 1),
    ("IFOOD *FARMACIA SAO JOAO", 20, 110, "Saúde", "app de delivery, mas o que se compra é farmácia", -1, 1),
    ("UBER *EATS", 25, 85, "Alimentação fora", "Uber Eats é comida, não transporte", -1, 2),
    ("99FOOD *PEDIDO", 25, 80, "Alimentação fora", "99 Food é comida, não transporte", -1, 1),
    ("AMAZON BR", 30, 350, "Compras e serviços", "sem 'prime' no nome = compra avulsa", -1, 2),
    ("AMAZON PRIME BR", 14.90, 14.90, "Lazer e assinaturas", "com 'prime' = assinatura", -1, 1),
    ("AMAZON KINDLE UNLIMITED", 19.90, 19.90, "Lazer e assinaturas", "livro digital, mas recorrente: assinatura prevalece", -1, 1),
    ("APPLE.COM/BILL", 6.90, 34.90, "Lazer e assinaturas", "cobrança da loja de apps: tratada como assinatura", -1, 2),
    ("SHELL SELECT CONVENIENCIA", 12, 45, "Alimentação fora", "conveniência de posto: lanche, não combustível", -1, 2),
    ("PADARIA PAO QUENTE", 8, 40, "Alimentação fora", "padaria = refeição fora, não mercado", -1, 2),
    ("PADARIA DO BAIRRO", 10, 45, "Alimentação fora", "padaria = refeição fora, não mercado", -1, 1),
    ("SUMUP *LANCHONETE DO ZE", 12, 50, "Alimentação fora", "maquininha com nome identificável após o asterisco", -1, 1),
    ("MP *LOJA5521", 25, 220, "Compras e serviços", "maquininha sem nome identificável: padrão Compras e serviços", -1, 2),
    ("PAGSEGURO *BARBEARIA", 35, 70, "Compras e serviços", "serviço pessoal", -1, 1),
    ("PAG*JoseSilva", 20, 180, "Compras e serviços", "pessoa via maquininha, sem contexto: padrão Compras e serviços", -1, 2),
    ("PIX ENVIADO ANA LIMA - JANTAR", 35, 120, "Alimentação fora", "finalidade explícita prevalece sobre 'PIX para pessoa'", -1, 1),
    ("PIX ENVIADO RACHA CONTA CHURRASCO", 30, 90, "Alimentação fora", "finalidade explícita prevalece sobre 'PIX para pessoa'", -1, 1),
    ("PIX RECEBIDO PEDRO ALVES - FREELA SITE", 800, 1500, "Renda", "finalidade explícita (trabalho) = Renda, não transferência", 1, 2),
    ("PIX RECEBIDO REEMBOLSO MERCADO", 25, 120, "Mercado", "reembolso volta para a categoria da despesa original", 1, 1),
    ("TRANSF POUPANCA", 200, 500, "Investimentos", "movimentação para poupança = Investimentos, não Transferências", -1, 1),
    ("ESTORNO COMPRA SHOPEE", 30, 150, "Compras e serviços", "estorno = categoria da compra original", 1, 1),
    ("ESTORNO UBER *TRIP", 10, 40, "Transporte", "estorno = categoria da compra original", 1, 1),
    ("ESTORNO IFOOD *RESTAURANTE", 25, 80, "Alimentação fora", "estorno = categoria da compra original", 1, 1),
    ("DROGASIL 1234", 20, 130, "Saúde", "farmácia = Saúde, mesmo que seja item de higiene", -1, 2),
    ("PETZ SAO PAULO", 40, 260, "Compras e serviços", "pet shop = Compras e serviços", -1, 1),
    ("LIVRARIA CULTURA", 30, 140, "Educação", "livros = Educação (decisão de regra)", -1, 1),
    ("MERCADO LIVRE *VENDEDOR", 30, 300, "Compras e serviços", "contém 'MERCADO', mas é marketplace = Compras", -1, 2),
    ("MERCADOPAGO *PAGAMENTO", 20, 200, "Compras e serviços", "carteira digital sem contexto: padrão Compras e serviços", -1, 1),
    ("CLARO MOVEL RECARGA", 20, 50, "Moradia e contas", "celular = conta fixa da casa", -1, 1),
]

for desc, lo, hi, cat, nota, sinal, reps in AMBIGUOS:
    for _ in range(reps):
        ano, mes = rng.choice(MESES)
        valor = lo if lo == hi else val(lo, hi)
        add(rdia(ano, mes), desc, sinal * valor, cat, 1, nota)

# ---------- 4) Ordenar, numerar e gravar ----------
rng.shuffle(rows)
rows.sort(key=lambda r: r[0])  # estável: só a data define a ordem

saida = Path(sys.argv[1] if len(sys.argv) > 1 else "dados")
saida.mkdir(parents=True, exist_ok=True)

with open(saida / "transacoes.csv", "w", newline="", encoding="utf-8") as f1, \
     open(saida / "gabarito.csv", "w", newline="", encoding="utf-8") as f2:
    w1, w2 = csv.writer(f1), csv.writer(f2)
    w1.writerow(["id", "data", "descricao", "valor"])
    w2.writerow(["id", "categoria", "ambigua", "nota"])
    for i, (d, desc, valor, cat, amb, nota) in enumerate(rows, start=1):
        tid = f"T{i:03d}"
        w1.writerow([tid, d.isoformat(), desc, f"{valor:.2f}"])
        w2.writerow([tid, cat, amb, nota])

print(f"{len(rows)} transações em {saida.resolve()}")
