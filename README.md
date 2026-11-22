# projeto-02-analisador-extrato

App em Streamlit que categoriza um extrato bancário com IA (Gemini) e mostra para onde vai o dinheiro.

Modelo: gemini-3.5-flash (reserva: gemini-3.5-flash-lite). Versão do prompt: v2-regras.

> README em construção: blocos 1 a 4 concluídos. Faltam recomendações (bloco 5), avaliação (bloco 6) e publicação com GIF (bloco 7).

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

## Limitações conhecidas

1. O estorno é classificado só pela descrição; o app não procura a compra original, que pode estar em outro lote.
2. As regras foram definidas pelo mesmo autor que vai rotular a avaliação, então a acurácia medida tende a ser otimista.
3. Dados sintéticos são mais limpos que um extrato real.
4. O app depende da disponibilidade da API do Gemini. Há tentativas automáticas e um modelo reserva, mas eles ainda não foram postos à prova numa falha real.
5. O cache da categorização dura só enquanto a aba do navegador estiver aberta.
6. A avaliação usa as 50 primeiras transações (agosto), não uma amostra aleatória.
7. Os totais dependem da categorização da IA, que ainda não foi avaliada (bloco 6). Uma transação na categoria errada muda o gasto por categoria.
8. PIX enviados a pessoas ficam fora do consumo, mesmo quando pagam algo que seria gasto (ex.: dividir uma conta). Isso pode subestimar o consumo.
9. As maiores despesas são quase só contas fixas (aluguel, faculdade, condomínio), o que ajuda pouco a encontrar onde cortar. Separar gasto fixo de variável fica para o bloco 5.
