# CLAUDE.md — Projeto 2: Analisador de extrato financeiro

Este arquivo é lido pelo Claude Code no início de cada sessão e guarda só as regras fixas. O estado atual do projeto está na última entrada do DEVLOG.md e no git log.

## O projeto

App em Streamlit que categoriza um extrato bancário fictício com um LLM (Gemini) e analisa os gastos com pandas. Faz parte de um portfólio para uma vaga de estágio em IA para negócios.

O autor é iniciante em programação e novo no macOS. Explique os comandos do Terminal em português, de forma curta.

## Arquivos principais

- app.py: interface Streamlit.
- extrato.py: carrega e valida o CSV.
- categorizador.py: categorização com o Gemini (modelo, versão do prompt, lotes, tentativas).
- analise.py: todos os cálculos, com pandas.
- testar_analise.py e testar_categorizacao.py: testes.
- dados/transacoes.csv: 307 transações fictícias (ago a out/2026).
- dados/avaliacao_50.csv: 50 rótulos manuais do autor, para a avaliação.
- resultados/categorias_v2-regras.csv: categorias da IA já calculadas.

## Como rodar

- Testes: .venv/bin/python testar_analise.py
- App: .venv/bin/streamlit run app.py (para parar: Control+C)
- Não rode categorizações completas no Gemini sem o autor pedir: elas gastam a cota do nível gratuito.

## Regras que nunca mudam

1. NUNCA altere dados/gabarito.csv. Desde o bloco 6 (decisão de 26/11 no DEVLOG), ele só pode ser lido pelo avaliar_categorizacao.py, na avaliação secundária. Não o abra, leia, imprima ou resuma por outros meios (cat, head, grep, ferramenta de leitura), exceto a primeira linha (o cabeçalho), quando o autor pedir.
2. O LLM só categoriza e redige texto. Todo número é calculado com pandas, em analise.py.
3. Só dados fictícios. Nenhuma chave de API ou e-mail pessoal em código, prints ou commits. A chave fica só no .env, que está no .gitignore. Nunca mostre o conteúdo do .env.
4. NÃO faça commit até o autor dizer "ok". NÃO faça push até ele dizer "push".
5. git add sempre pelo nome dos arquivos. Nunca use git add . nem git add -A.
6. Antes do push, mostre git diff --stat origin/main..HEAD.
7. Mensagens de commit em português, começando pelo bloco (ex.: "Bloco 5: ...").
8. Não altere arquivos que o pedido não mencionou. Se achar que outro arquivo precisa mudar, pergunte antes.
9. No DEVLOG.md só entra o que foi realmente testado. Para corrigir uma entrada antiga, acrescente um esclarecimento; não reescreva.
10. Textos para o usuário (app, README, DEVLOG, mensagens de erro) em português.
