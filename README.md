#  Dashboard Interativo para Análise de Vendas da PHIQ com Streamlit

**TL;DR:** Um dashboard de vendas feito em Python que permite o upload de um CSV, realiza um ETL básico com Pandas, e gera visualizações interativas com Plotly para explorar KPIs como faturamento, ticket médio, análise de recompra e uma previsão simples da próxima compra de clientes.

##  Visão Geral do Projeto

Este projeto foi desenvolvido como um case prático de visualização de dados e web app development. O objetivo era construir uma ferramenta de *self-service BI* que permitisse a um usuário de negócio (como um gestor de vendas) explorar dados de pedidos sem a necessidade de rodar queries SQL ou mexer em planilhas complexas.

A aplicação foi construída inteiramente em Python, utilizando **Streamlit** para o front-end, **Pandas** para a manipulação e análise dos dados, e **Plotly Express** para a criação dos gráficos.

##  Features Implementadas

* **Pipeline de ETL Simplificado:** Script para carregar, limpar e padronizar os dados de um CSV de entrada, lidando com inconsistências comuns como nomes de colunas variados e tipos de dados sujos.
* **Análise de Coorte (Simplificada):** Implementação de uma lógica para classificar transações entre "Cliente Novo" e "Recompra", essencial para analisar a retenção.
* **Métricas de Negócio (KPIs):** Cálculos automáticos de Faturamento, Ticket Médio por Pedido, e contagem de Pedidos Únicos.
* **Análise de Recorrência e Previsão Heurística:** Uma função que calcula a mediana dos dias entre as compras de um cliente para estimar a data da próxima compra.
* **Filtros e Segmentação:** O dashboard permite a segmentação dinâmica dos dados por período, estado, franquia e segmento do cliente.
* **Lógica de Negócio Customizada:** Implementação de uma visão de dashboard específica por gestor, usando regras baseadas em strings para atribuir clientes a cada um.

##  Stack Utilizado

* **Linguagem:** `Python 3.9+`
* **Análise de Dados:** `Pandas`
* **Web Framework / Dashboarding:** `Streamlit`
* **Visualização de Dados:** `Plotly Express`
* **Bibliotecas Padrão:** `datetime`, `os`

##  Setup & Execução

**1. Clone o repositório e crie um ambiente virtual:**
```bash
git clone <https://github.com/iamdaviwilliam/Acompanhamento-de-Franquias-Phiq>
cd <Acompanhamento-de-Franquias-Phiq>
python -m venv .venv
source .venv/bin/activate # No Windows: .venv\Scripts\activate
```
**2. Instale as dependências
```bash
 pip install -r requirements.txt
```
**3. Como executar**
Para iniciar a aplicação, execute o seguinte comando no terminal:
```bash
streamlit run app.py
```
A aplicação será aberta em seu navegador padrão.
