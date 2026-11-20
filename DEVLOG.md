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

