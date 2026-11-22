# DEVLOG — Projeto 2: Analisador de Extrato Financeiro

## 19/11/2026

- Início do projeto: analisador de extrato financeiro em Streamlit, com categorização por LLM (Gemini).
- Criado `requirements.txt` com streamlit, pandas, google-genai e python-dotenv.
- Criado `.env.example` com `GEMINI_API_KEY=` vazio (a chave real fica só no `.env`, que não vai para o Git).
- Criado `app.py` mínimo que mostra "Olá".
- Regra do projeto: usar apenas dados fictícios.

### Aprendizados

Hoje configurei o Mac do zero: instalei Python e Git, criei o ambiente virtual e rodei um app de teste. Entendi que o .venv guarda as bibliotecas do projeto e que o .env guarda a chave sem ir para o GitHub. E fui pedindo ao Claude para me explicar cada decisão e ir revisando comigo os passos.

## 20/11/2026

Dados sintéticos criados: 307 transações fictícias (ago–out/2026) em dados/transacoes.csv, geradas por dados/gerar_dados.py com semente fixa. dados/gabarito.csv traz a categoria e uma flag de ambiguidade (~18% das linhas são ambíguas de propósito). Decisões: o gabarito nunca entra no app nem no prompt do LLM. A avaliação final (bloco 6) será com 50 transações que eu rotular sozinho antes de ver o gabarito, porque esse gabarito foi escrito junto com os dados e as regras são minhas. Limitação: dado sintético é mais limpo que extrato real, então a acurácia em dados reais tende a ser pior.

O macOS cria arquivos `.DS_Store` sozinho em cada pasta; eles não têm valor para o projeto, então `.DS_Store` foi adicionado ao `.gitignore`.

## 20/11/2026 — Correção dos dados sintéticos (v2)

Correção dos dados sintéticos (v2). Ao testar o app com os dados de exemplo, os totais mostraram uma inconsistência: entradas de R$ 17.001,54 contra saídas de R$ 37.786,58 em 3 meses, ou seja, o usuário fictício gastava 2,2 vezes o que ganhava. Isso tornaria irreal qualquer recomendação do bloco 5. A primeira versão foi gerada sem conferir a proporção entre renda e gastos. Correção: salário de R$ 7.500 e gastos variáveis escalados (FATOR_VARIAVEL = 0.45) em dados/gerar_dados.py. Resultado: 307 transações, entradas R$ 26.901,54, saídas R$ 24.579,57 (cerca de 91%). As saídas incluem a fatura do cartão (cerca de R$ 3,9 mil) e as aplicações em RDB (R$ 900), que não são gasto de consumo; a análise do bloco 4 deve tratá-las à parte. Os arquivos foram substituídos mantendo os nomes; a versão anterior continua no histórico do Git. Lição: validar a plausibilidade dos dados sintéticos (renda x gastos) antes de usá-los.

## 20/11/2026 — Bloco 2 concluído

Bloco 2 concluído: app com upload e validação de CSV, ainda sem LLM. extrato.py valida as colunas obrigatórias (id, data, descricao, valor), o formato da data (AAAA-MM-DD), se o valor é numérico e se a descrição está vazia, com mensagens de erro em português. app.py tem upload de CSV, o botão 'Usar dados de exemplo' e um resumo (número de transações, período, entradas, saídas e tabela). Testes feitos: dados de exemplo (307 transações, período 01/08 a 31/10/2026), upload do transacoes.csv e upload do exemplo_invalido.csv (erro de coluna faltando: 'valor'). Limitações: a validação confere só o formato, não confere ids duplicados nem se os valores fazem sentido; o total de saídas ainda inclui o pagamento da fatura do cartão e as aplicações em RDB, que a análise do bloco 4 vai tratar à parte. Próximo: bloco 3, categorização por LLM em lotes com saída em JSON.

Corrigido o resumo do app: o período aparecia cortado ('31/10/...'), pois o st.metric trunca textos longos. Agora são duas caixas (primeira e última data).

## 21 e 22/11/2026 — Bloco 3: categorização por LLM

**Chave e modelo.** A chave do Gemini (Google AI Studio, nível gratuito, sem faturamento) fica só no `.env`. O formato novo começa com "AQ." e tem 53 caracteres. Validei a chave listando os modelos pela API, e o `git check-ignore` confirmou que o `.env` fica fora do Git. O gemini-2.5-flash aparecia na lista, mas deu 404 para a conta nova. O gemini-3.8-flash (sugerido pela própria mensagem de erro) deu 503 por alta demanda e depois a conexão caiu, em 2 tentativas. O gemini-3.5-flash funcionou na primeira tentativa e virou o modelo principal. O gemini-3.5-flash-lite respondeu a um teste de 5 transações e virou o modelo reserva. Lição: estar na lista de modelos não garante acesso, e a API pode ficar indisponível.

**Categorizador (`categorizador.py`).** Saída estruturada em JSON com schema (a categoria fica limitada às 13), temperature=0 e validação de ids faltando, extras ou repetidos e de categoria inválida. O prompt `v2-regras` tem 11 regras de negócio e 8 exemplos inventados; conferimos com grep que nenhum exemplo aparece em `transacoes.csv`. As regras secundárias ficaram só no README. A categorização é feita em lotes de 40, com pausa de 4 s, tentativas automáticas em erro temporário (espera de 5, 15 e 30 s) e o modelo reserva.

**Rodada completa.** 307 transações em 8 lotes, 111,9 s, 0 tentativas extras, todas respondidas pelo gemini-3.5-flash. O resultado está em `resultados/categorias_v2-regras.csv`. Limitação: as tentativas automáticas e a troca para o modelo reserva ainda não foram postas à prova, porque não houve nenhuma falha.

**Rótulos manuais (preparação do bloco 6).** Rotulei 50 transações (T001 a T050) sem abrir o gabarito e sem ver o resultado completo da IA. O commit dos rótulos (7a48f86) foi enviado antes do commit com os resultados (e3f7517). Antes do commit, corrigi 3 rótulos que contradiziam as minhas próprias regras (T012, T026, T035). Limitações: a amostra são as 50 primeiras transações (agosto), não uma amostra aleatória; e, para T001 a T005, eu já tinha visto a resposta da IA.

**App (`app.py`).** Botão "Categorizar com IA", barra de progresso por lote, coluna de categoria na tabela, contagem por categoria e erros em português. A categorização é descartada ao trocar de arquivo. Bug: a primeira versão usava `@st.cache_data` com a barra de progresso dentro, e a segunda categorização do mesmo extrato dava `CacheReplayClosureError`. O teste automatizado com um categorizador falso não pegou o erro; o teste manual no navegador pegou. Correção: um cache próprio em `st.session_state`, com chave = extrato + modelo + versão do prompt. Testado no navegador: dados de exemplo (barra até o lote 8 de 8), segunda categorização em menos de 1 s (vinda do cache) e coluna de categoria sumindo ao trocar de arquivo. Limitação: o cache dura só enquanto a aba estiver aberta.

**Teste de fumaça.** Testei com um extrato fictício de novembro (30 transações, montado pelo Claude e mantido fora do repositório). As 30 categorias ficaram coerentes com as regras, inclusive 6 casos de regras secundárias que não estão no prompt. Isso não é métrica: as respostas esperadas foram definidas por quem montou o arquivo, já conhecendo as regras, e 30 casos é pouco. A métrica oficial vem no bloco 6.

**Próximo:** bloco 4 (totais e gráficos com pandas, tratando à parte a fatura do cartão e as aplicações).

## 22/11/2026 — Bloco 4, passo 1: cálculos com pandas

Criado `analise.py`, só com cálculos em pandas (o LLM não calcula nada). Grupos: Renda; Consumo (as 10 categorias de gasto); Fora do consumo (Transferências e Investimentos). A fatura do cartão fica fora porque as compras no cartão já aparecem uma a uma no extrato, e contá-la duplicaria o gasto. PIX enviados a pessoas também ficam fora, porque não dá para saber com o que o dinheiro foi gasto (limitação). O gasto por categoria soma os valores com sinal, para os estornos abaterem as compras. Testado com `testar_analise.py` sobre as categorias da IA (v2-regras): renda R$ 24.820,13, consumo R$ 17.748,65, sobra antes de investimentos e transferências R$ 7.071,48. Os números foram conferidos com um cálculo independente. Consumo + fora do consumo + estornos (R$ 262,38) fecha com as saídas totais de R$ 24.579,57. Teste mínimo: compra de -100 com estorno de +30 dá gasto de 70. Correção feita na revisão: o total de "fora do consumo" passou a ter sinal, porque em valor absoluto os PIX recebidos pareciam saída. Limitação: os números dependem da categorização da IA, que ainda não foi avaliada (bloco 6). Próximo: gráficos e a tela no app.

App: seção 'Análise dos gastos' com renda, consumo e sobra, gráfico de gasto por categoria (Altair, maior para menor, eixo e tooltip no formato brasileiro) e tabela 'Fora do consumo' com sinal. Testado no navegador com os dados de exemplo. Corrigido o corte dos valores no st.metric.

