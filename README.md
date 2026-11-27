# projeto-02-analisador-extrato

App em Streamlit que categoriza um extrato bancário com IA (Gemini) e mostra para onde vai o dinheiro.

Modelo: gemini-3.5-flash (reserva: gemini-3.5-flash-lite). Prompts: v2-regras (categorização) e r2 (recomendações).

**App online:** https://extrato-com-ia-david.streamlit.app/ (dados fictícios; limite de 15 pedidos de IA por dia para todos os visitantes).

> README em construção: blocos 1 a 6 concluídos, app publicado e visual pronto. Faltam o teste ao vivo da categorização no site, o GIF e o README final (bloco 7).

## Dados

Todos os dados são sintéticos: 307 transações fictícias de ago a out/2026, geradas por `dados/gerar_dados.py`. Nenhum dado real é usado.

## Categorias

1. Moradia e contas
2. Mercado
3. Alimentação fora
4. Transporte
5. Saúde
6. Educação
7. Compras e serviços
8. Lazer e assinaturas
9. Transferências
10. Renda
11. Taxas e impostos
12. Investimentos
13. Outros

## Regras de categorização (aplicadas no prompt)

- **Princípio geral:** a finalidade explícita na descrição prevalece sobre o tipo de transação (PIX, TED, maquininha) e sobre o nome da contraparte. Ex.: PIX com "aluguel" = Moradia e contas; PIX com "jantar" = Alimentação fora.
- **PIX recebido de pessoa**, sem finalidade explícita = Transferências. Só é Renda quando a descrição indica trabalho, salário ou empresa pagadora.
- **Transferência entre contas próprias** e **pagamento de fatura do cartão** = Transferências (movimentação interna, não é gasto novo).
- **Maquininha** (ex.: SumUp, Stone, PagSeguro) com nome identificável = categoria do nome; sem nome identificável = Compras e serviços.
- **Farmácia** (mesmo item de higiene) = Saúde.
- **Recarga de celular** = Moradia e contas (conta fixa).
- **Padaria** = Alimentação fora (não Mercado).
- **Delivery de mercado** (ex.: iFood Mercado) = Mercado.
- **Delivery de comida** (ex.: Uber Eats, 99 Food, iFood restaurante) = Alimentação fora.
- **Aplicação ou resgate em RDB, CDB ou poupança** = Investimentos.
- **Estorno/reembolso:** usa a categoria do que a descrição indica estar sendo estornado; se não der para saber, Outros.

## Regras planejadas (ainda não aplicadas)

Estas regras ainda não estão no prompt:

- Academia = Saúde. Conveniência de posto = Alimentação fora.
- Amazon com "prime" = Lazer e assinaturas; sem "prime" = Compras e serviços.
- Livro físico = Educação; livro digital recorrente = Lazer e assinaturas.
- Loja de apps (Apple/Google) = Lazer e assinaturas.
- Marketplace com "MERCADO" no nome = Compras e serviços.
- Pet shop e serviço pessoal = Compras e serviços.
- Maquininha com nome de pessoa (ex.: PAG*JoseSilva) não conta como nome identificável = Compras e serviços.

## Análise dos gastos (bloco 4)

Todos os números são calculados com pandas, em `analise.py`. O LLM só categoriza e nunca faz contas.

As transações são separadas em três grupos:

- **Renda:** categoria Renda (salário e freelas).
- **Consumo:** as 10 categorias de gasto. Os valores são somados com sinal, para os estornos abaterem as compras.
- **Fora do consumo:** Transferências e Investimentos. A fatura do cartão fica fora porque as compras no cartão já aparecem uma a uma no extrato, e contá-la duplicaria o gasto. PIX a pessoas e aplicações também ficam fora, porque não dizem com o que o dinheiro foi gasto.

O app mostra renda, consumo e sobra (renda menos consumo, antes de investimentos e transferências); o gasto por categoria; a evolução mensal de renda e consumo; as 10 maiores despesas; e uma tabela com o que ficou fora do consumo, com sinal.

Com os dados de exemplo e as categorias da IA: renda de R$ 24.820,13, consumo de R$ 17.748,65 e sobra de R$ 7.071,48 em 3 meses. Esses números foram conferidos com um cálculo independente, e `testar_analise.py` confere a coerência dos totais.

## Recomendações (bloco 5)

O LLM gera 3 recomendações a partir de números agregados pelo pandas. Ele nunca recebe as transações e nunca escreve um número.

**Gasto fixo x variável.** Gasto fixo é a saída de consumo cuja descrição aparece uma vez por mês em todos os meses do extrato, com variação de valor de até 50% ((maior − menor) / média). O resto do consumo é variável. A mesma regra separa a renda fixa (salário) da renda extra. Com os dados de exemplo: 13 gastos fixos, fixo de R$ 2.703,15 / R$ 2.712,10 / R$ 2.753,49 e variável de R$ 3.073,45 / R$ 3.160,41 / R$ 3.346,05 (agosto a outubro). A separação exige pelo menos 3 meses de extrato.

**O que o LLM recebe.** Um pacote só com agregados: valores por mês (renda fixa e extra, consumo, fixo, variável e sobra), diferenças entre o primeiro e o último mês, totais, total aplicado em investimentos, gasto variável por categoria e a lista de gastos fixos. Não vão transações individuais, fatura do cartão nem PIX.

**Marcadores em vez de números.** O LLM escreve marcadores como `{Transporte.diferenca}` ou `{2026-10.sobra}`, e o Python troca cada um pelo valor formatado ("alta de R$ 176,19", "R$ 1.400,46"). Assim o LLM não consegue inventar nem calcular números. Nas diferenças, quem escreve a direção ("alta de", "queda de") é o Python.

**Conferência automática.** A resposta é recusada se não vierem 3 recomendações completas, se houver marcador inexistente, se sobrar qualquer dígito fora dos marcadores ou se aparecer uma expressão como "por cento", "reais" ou "dobro". Na recusa, o LLM recebe o motivo e tem mais uma chance; se errar de novo, o app não mostra nenhuma recomendação.

**Do prompt r1 ao r2.** A primeira versão (r1) acertou o ponto principal: a sobra caiu R$ 1.800,68, e 82% disso veio do fim da renda extra (freela), não do consumo. Mas gerou uma frase torta ("apresentou sem variação") e uma recomendação de baixo impacto, sobre a categoria Outros (R$ 134,93 em outubro). O r2 mudou o texto da diferença zero, trocou "baseie-se nas maiores variações" por "priorize o impacto em reais" e passou a pedir um valor de referência para metas. Numa rodada, as três recomendações passaram a tratar do fim da renda extra, de Compras e serviços (alta de R$ 177,44) e de Transporte (alta de R$ 176,19), com metas no nível de agosto. Efeito colateral: o LLM copiou o exemplo do prompt ("o primeiro mês") nas duas metas. As duas rodadas estão em `resultados/`.

**Dados de exemplo sem chamar a API.** O botão "Usar dados de exemplo" carrega as categorias (`resultados/categorias_v2-regras.csv`) e as recomendações (`resultados/recomendacoes_r2.json`) que o Gemini já gerou, com um aviso na tela. As recomendações salvas passam pela conferência e têm os valores preenchidos na hora, a partir do pacote. Os botões continuam gerando tudo ao vivo. Motivo: no nível gratuito, o Gemini permite 20 pedidos por dia por modelo, e em 23 e 24/11 as quatro tentativas ao vivo no app falharam (sobrecarga do servidor e cota esgotada).

## Avaliação da categorização (bloco 6)

A categorização foi avaliada sem nova chamada ao Gemini, comparando as categorias já geradas (`resultados/categorias_v2-regras.csv`) com duas referências, em `avaliar_categorizacao.py`. As métricas foram registradas no DEVLOG antes de cada comparação.

| Referência | Acertos da IA |
|---|---|
| 50 rótulos manuais do autor (T001 a T050) | 49 de 50 (98,0%) |
| Os mesmos 50, sem T001 a T005 e T009 | 43 de 44 (97,7%) |
| Gabarito, 307 transações | 305 de 307 (99,3%) |
| Gabarito, só as 55 ambíguas de propósito | 53 de 55 (96,4%) |

**Os dois erros** são regras planejadas que não entraram no prompt, e as duas são convenções: academia (o gabarito diz Saúde; a IA deu Lazer e assinaturas) e livraria (Educação; a IA deu Compras e serviços). As outras regras planejadas, também fora do prompt (Amazon Prime, conveniência de posto, marketplace com "MERCADO", loja de apps, pet shop), a IA acertou sozinha. Conclusão: regra intuitiva o modelo deduz; convenção precisa estar escrita no prompt.

**Inconsistência:** as três cobranças da academia, com a mesma descrição, receberam Lazer e assinaturas em agosto e Saúde em setembro e outubro, mesmo com temperature 0.

**Como ler esses números:** eles medem se a IA segue as regras do autor, não o acerto num extrato real. Os rótulos manuais, o gabarito e o prompt seguem as mesmas regras (os rótulos concordaram com o gabarito em 50 de 50), os dados são sintéticos e os 50 rótulos são as primeiras transações de agosto, quase todas fáceis. Num extrato real, a acurácia tende a ser menor.

## Limitações conhecidas

1. O estorno é classificado só pela descrição; o app não procura a compra original, que pode estar em outro lote.
2. As regras, os rótulos manuais e o gabarito foram definidos pelo mesmo autor e seguem as mesmas regras do prompt, então as acurácias medidas (98% e 99,3%) são otimistas: medem se a IA segue as regras, não o acerto num extrato real.
3. Dados sintéticos são mais limpos que um extrato real.
4. O app depende da disponibilidade da API do Gemini. Em 23 e 24/11, as quatro tentativas ao vivo no app falharam (503 por sobrecarga e 429 por cota diária), e o modelo reserva também falhou em todas as vezes. Desde o bloco 7, a cota diária esgotada vai direto ao reserva, sem esperas, e os erros aparecem em português; a detecção da cota diária procura "PerDay" no texto do erro e só foi testada com erros simulados.
5. O cache da categorização dura só enquanto a aba do navegador estiver aberta.
6. Os 50 rótulos manuais são as 50 primeiras transações (agosto), não uma amostra aleatória, e quase todas são fáceis; os casos difíceis só foram medidos contra o gabarito.
7. Os totais dependem da categorização da IA. Uma transação na categoria errada muda o gasto por categoria (ex.: a academia aparece em Lazer em agosto e em Saúde nos outros meses).
8. PIX enviados a pessoas ficam fora do consumo, mesmo quando pagam algo que seria gasto (ex.: dividir uma conta). Isso pode subestimar o consumo.
9. As maiores despesas são quase só contas fixas (aluguel, faculdade, condomínio). Desde o bloco 5, o app separa gasto fixo de variável, mas a tabela de maiores despesas continua misturando os dois.
10. Se um lote falha, os lotes já prontos ficam guardados na sessão, e um novo clique continua de onde parou. Eles se perdem ao trocar de arquivo ou fechar a aba, e a retomada só foi testada com um Gemini simulado.
11. O critério de gasto fixo foi calibrado nos próprios dados de exemplo (a conta de luz varia 36%; o primeiro hábito, 64%). Ele também erra em casos previsíveis: o IOF de R$ 3,85 entra como fixo; um mês incompleto conta como mês inteiro; e uma conta paga duas vezes no mesmo mês, ou um salário que cai no dia 31 e depois no dia 1º, deixa de ser fixo.
12. A conferência garante que os números vêm do pandas, mas não avalia a qualidade das recomendações nem pega um texto que contradiga a direção (ex.: "subiu" antes de uma queda).
13. A regra de nenhum dígito obriga o LLM a escrever números por extenso ("três meses"), e a palavra "reais" é recusada até como adjetivo ("riscos reais"). Valores escritos por extenso sem as expressões proibidas ("mil e oitocentos") passariam.
14. Parte da qualidade das recomendações vem de regras escritas pelo autor no prompt (ex.: atribuir a queda da sobra à renda extra quando for o caso), e cada versão do prompt foi avaliada em uma rodada só.
15. Com temperature 0, a mesma descrição pode receber categorias diferentes em lotes diferentes (caso da academia). O app não confere a consistência entre lotes.
16. Depois de usado na avaliação, o gabarito deixou de ser um teste cego: uma versão futura do prompt (ex.: com as regras de academia e livro) precisaria de rótulos novos para ser avaliada.
17. Proteção da cota na demonstração: no máximo 15 pedidos ao Gemini por dia, somando todos os visitantes, e uploads de até 400 transações. O contador fica na memória do app e volta a zero se o app reiniciar; nesse caso, vale só o limite do próprio Google.
18. Se a execução for parada pelo "Stop" do Streamlit, os botões de IA podem ficar desativados até a página ser recarregada.
