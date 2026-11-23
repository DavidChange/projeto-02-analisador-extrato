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

Evolução mensal (renda x consumo por mês) e as 10 maiores despesas de consumo no app. Testado no navegador. Bloco 4 concluído. Próximo: bloco 5, 3 recomendações do LLM a partir dos agregados.

Esclarecimento (23/11): a correção de sinal valeu só para fora_do_consumo() (tabela do app). O resumo() tinha um total só das saídas, em módulo (R$ 6.568,54), com o mesmo nome; ele foi renomeado para saidas_fora_consumo e documentado, para não ser confundido com o saldo com sinal (-R$ 4.749,51). Esse total não aparece na tela. O testar_analise.py agora tem asserts para o sinal dos PIX enviados e recebidos e para transferências não mexerem na sobra.

## 23/11/2026 — Bloco 5: recomendações do LLM

**Decisão: o que é gasto fixo.** Gasto fixo é uma saída de consumo cuja descrição aparece uma vez por mês em todos os meses do extrato, com variação de valor de até 50% ((maior − menor) / média). O resto do consumo é variável. Se o extrato tiver menos de 3 meses, o app não faz a separação. Motivo: só "aparecer todo mês" puxaria hábitos para o fixo (saque 24h, açougue e Café Central aparecem uma vez por mês, mas variam de 64% a 77%), e exigir valor idêntico deixaria a conta de luz de fora (varia 36%). Limitações: o limite de 50% foi escolhido olhando estes dados sintéticos; 3 meses é pouca evidência; o IOF de R$ 3,85 entra como fixo sem ser; conta anual ou que muda de nome não é detectada; e a separação depende da categoria dada pela IA (o aluguel é um PIX que a IA colocou em Moradia). Os totais de fixo e variável serão registrados depois de testados na função.


Criado o CLAUDE.md com as regras fixas do projeto, que o Claude Code lê no início de cada sessão; antes elas só existiam nos prompts. Criado também o .claude/settings.json com uma regra que bloqueia a leitura e a edição de dados/gabarito.csv pelas ferramentas de arquivo do Claude Code. Limitação: o bloqueio não cobre comandos do Terminal (como cat); para esses, vale a regra escrita no CLAUDE.md. O .claude/settings.local.json (permissões pessoais) foi colocado no .gitignore.

Passo 1: criadas gastos_fixos() e fixo_variavel_mensal() em analise.py, com testes em testar_analise.py. Com as categorias da IA, há 13 gastos fixos: aluguel (R$ 1.350), faculdade (R$ 399), condomínio (R$ 380), contas de luz, internet e celular, assinaturas, tarifa do banco e o IOF; a luz entrou com variação de 0,363. Fixo por mês: R$ 2.703,15 / R$ 2.712,10 / R$ 2.753,49. Variável por mês: R$ 3.073,45 / R$ 3.160,41 / R$ 3.346,05. De agosto a outubro o consumo subiu R$ 322,94, dos quais R$ 272,60 (84%) vieram do gasto variável; o fixo subiu R$ 50,34, só por causa da luz. Em cada mês, fixo + variável bate com o consumo. Mini-testes: um extrato de 3 meses (luz com variação de 0,333 vira fixo; café com variação de 1,0 e Uber duas vezes por mês ficam variáveis; o estorno abate o variável) e um de 2 meses (as funções devolvem tabela vazia).

Passo 2: criadas renda_fixa_extra_mensal(), variavel_por_categoria_mensal() e montar_pacote() em analise.py; a regra de "recorrente" virou um auxiliar (_recorrentes), usado também por gastos_fixos(), com o mesmo resultado. O pacote para o LLM tem só agregados: valores mensais (renda fixa e extra, consumo, fixo, variável e sobra), diferenças entre o primeiro e o último mês, totais, investimentos aplicados (R$ 1.076,33), variável por categoria e os 13 gastos fixos, com descrição e valor médio (o que inclui a descrição do PIX do aluguel). Fora os gastos fixos, nenhuma descrição de transação vai para o LLM; o teste confere que o JSON não contém "UBER" nem "PIX RECEBIDO". A informação sobre os freelas é calculada (renda fixa de R$ 7.500 nos 3 meses; renda extra de R$ 1.477,74 / R$ 842,39 / R$ 0), e não escrita à mão, para valer com qualquer extrato. Com as categorias da IA, a sobra cai de R$ 3.201,14 para R$ 1.400,46 (−R$ 1.800,68): R$ 1.477,74 (82%) vêm do fim da renda extra e R$ 322,94 (18%) da alta do consumo. No gasto variável, Compras e serviços (+R$ 177,44) e Transporte (+R$ 176,19) puxam a alta, e Mercado cai R$ 101,24. Correções: o zero negativo (-0.0) que aparecia no JSON (corrigido em _reais, com assert) e o contador global dos mini-testes, trocado pelo tamanho da lista. Testes novos: renda fixa x extra, estorno abatendo o variável, mês sem gasto = 0 (e não vazio), extrato de 2 meses (ValueError) e a conferência do JSON citada acima.
