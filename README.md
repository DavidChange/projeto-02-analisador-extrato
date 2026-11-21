# projeto-02-analisador-extrato

App em Streamlit que categoriza um extrato bancário com IA (Gemini) e mostra para onde vai o dinheiro.

> Esta é uma primeira versão do README. O README completo fica para o bloco 7.

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

## Limitações conhecidas

1. O estorno é classificado só pela descrição; o app não procura a compra original, que pode estar em outro lote.
2. As regras foram definidas pelo mesmo autor que vai rotular a avaliação, então a acurácia medida tende a ser otimista.
3. Dados sintéticos são mais limpos que um extrato real.
