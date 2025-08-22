import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime

# --- Configuração da página ---
st.set_page_config(
    page_title="Dashboard PHIQ - Análise de Vendas",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Paleta de cores PHIQ ---
TEAL = "#2C8B8B"          # Verde-água
SOFT_BLUE = "#3A7CA5"     # Azul suave
BACKGROUND = "#F5F7FA"    # Fundo claro
TEXT_PRIMARY = "#000000"

# --- Estilo CSS completo ---
st.markdown(f"""
<style>
    .main {{
        background-color: {BACKGROUND};
        color: {TEXT_PRIMARY};
        font-family: 'Arial', sans-serif;
    }}
    .stTitle, .stHeader {{
        color: {TEAL} !important;
    }}
    .stMetric {{
        color: {TEAL} !important;
    }}
    .stButton button {{
        background-color: {TEAL} !important;
        color: white !important;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: bold;
    }}
    .stButton button:hover {{
        background-color: {SOFT_BLUE} !important;
    }}
    .stSidebar {{
        background-color: {TEAL} !important;
        color: white !important;
    }}
    .stSidebar .stRadio > div > label,
    .stSidebar .stSelectbox > div > label {{
        color: white !important;
        font-weight: bold;
    }}

    /* Fundo transparente nos gráficos */
    .stPlotlyChart {{
        background-color: transparent !important;
        border: none !important;
    }}

    /* === ALTERAÇÃO DOS BOTÕES "X" NOS FILTROS MULTISELECT === */
    .stMultiSelect [data-baseweb="tag"] {{
        background-color: {TEAL} !important;
        color: white !important;
        border-radius: 12px !important;
        padding: 0 !important;
        height: 28px;
        display: inline-flex;
        align-items: center;
    }}

    .stMultiSelect [data-baseweb="tag"] span {{
        color: white !important;
        font-size: 14px;
        margin: 0 8px;
    }}

    .stMultiSelect [data-baseweb="tag"] button {{
        background-color: {SOFT_BLUE} !important;
        color: white !important;
        border: none;
        border-radius: 50% !important;
        width: 20px;
        height: 20px;
        margin: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
    }}

    .stMultiSelect [data-baseweb="tag"]:hover button {{
        background-color: {TEAL} !important;
    }}

    .stMultiSelect div[role="combobox"] {{
        background-color: white;
        border-radius: 6px;
        border: 1px solid #ddd;
    }}
</style>
""", unsafe_allow_html=True)

# ====================
# Função: Formatador de moeda brasileiro (R$ 1.234,56)
# ====================
def formatar_real(valor):
    try:
        return f"R$ {valor:,.2f}".replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")
    except:
        return "R$ 0,00"

# ====================
# Função para carregar dados (com upload de CSV)
# ====================
@st.cache_data
def load_data(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file, encoding='utf-8', on_bad_lines='skip', low_memory=False)
    except Exception as e:
        st.error(f"Erro ao ler o CSV: {e}")
        st.stop()

    # --- Limpeza e padronização das colunas ---
    df.columns = df.columns.str.strip()

    # --- Renomear colunas ---
    column_mapping = {
        'Data Faturamento Pedido': 'Data Faturamento Pedido',
        'Cliente': 'Cliente',
        'Estado': 'Estado',
        'UF': 'Estado',
        'Vendedor': 'Vendedor',
        'Preço Venda Total (R$)': 'Valor Total',
        'Valor Total': 'Valor Total',
        'Descrição': 'Descrição',
        'Forma Pagamento': 'Forma Pagamento',
        'SEGMENTO ': 'Segmento',
        'SEGMENTO': 'Segmento',
        'Franquia': 'Franquia',
        'Data': 'Data'
    }
    for old, new in column_mapping.items():
        if old in df.columns:
            df.rename(columns={old: new}, inplace=True)

    # Criar coluna 'Franquia' se não existir
    if 'Franquia' not in df.columns:
        df['Franquia'] = 'PHIQ'

    # --- Conversão de datas ---
    date_cols = ['Data', 'Data Faturamento Pedido']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
        else:
            st.warning(f"Coluna '{col}' não encontrada.")

    # --- Limpeza de valores numéricos ---
    if 'Valor Total' in df.columns:
        df['Valor Total'] = pd.to_numeric(
            df['Valor Total'].astype(str).str.replace(',', ''),
            errors='coerce'
        )

    # Padronizar texto
    text_cols = ['Estado', 'Vendedor', 'Segmento']
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.upper()

    if 'Segmento' in df.columns:
        df['Segmento'] = df['Segmento'].replace(['', 'nan'], 'Não Informado')
        df['Segmento'] = df['Segmento'].replace({
            'CLIENTE FÁBRICA ': 'CLIENTE FÁBRICA',
            'INSTITUCIONAL ': 'INSTITUCIONAL'
        })

    return df

# ====================
# Função: Calcular recorrência e previsão (com arredondamento)
# ====================
def calcular_recorrencia_e_previsao(df, cliente_col='Cliente', date_col='Data'):
    if df.empty or len(df) < 2:
        return pd.DataFrame()

    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df = df.dropna(subset=[date_col])

    # Agrupar por cliente e data (sem hora)
    df['Data_Sem_Hora'] = pd.to_datetime(df[date_col]).dt.date
    compras_unicas = df[[cliente_col, 'Data_Sem_Hora']].drop_duplicates().sort_values([cliente_col, 'Data_Sem_Hora'])

    # Garantir que cliente tenha pelo menos 2 compras
    contagem = compras_unicas.groupby(cliente_col).size()
    clientes_mult = contagem[contagem >= 2].index
    compras_unicas = compras_unicas[compras_unicas[cliente_col].isin(clientes_mult)]

    if compras_unicas.empty:
        return pd.DataFrame()

    compras_unicas['Data_Sem_Hora'] = pd.to_datetime(compras_unicas['Data_Sem_Hora'])
    compras_unicas = compras_unicas.sort_values([cliente_col, 'Data_Sem_Hora'])
    compras_unicas['Diferença Dias'] = compras_unicas.groupby(cliente_col)['Data_Sem_Hora'].diff().dt.days

    recorrencia = compras_unicas.groupby(cliente_col).agg(
        Ultima_Compra=('Data_Sem_Hora', 'max'),
        Tempo_Medio_Dias=('Diferença Dias', 'mean')
    ).reset_index()

    recorrencia = recorrencia.dropna(subset=['Tempo_Medio_Dias'])
    recorrencia['Tempo_Medio_Dias'] = recorrencia['Tempo_Medio_Dias'].round(0).astype(int)  # Arredondado

    recorrencia['Próxima Compra'] = recorrencia['Ultima_Compra'] + pd.to_timedelta(recorrencia['Tempo_Medio_Dias'], unit='D')

    recorrencia['Tempo Médio (dias)'] = recorrencia['Tempo_Medio_Dias']
    recorrencia['Última Compra'] = recorrencia['Ultima_Compra'].dt.strftime('%d/%m/%Y')
    recorrencia['Próxima Compra'] = recorrencia['Próxima Compra'].dt.strftime('%d/%m/%Y')

    return recorrencia[[
        cliente_col, 'Tempo Médio (dias)', 'Última Compra', 'Próxima Compra'
    ]].rename(columns={cliente_col: 'Cliente'})

# ====================
# Função: Classificar compras como Novo ou Recompra
# ====================
def classificar_compras(df, cliente_col='Cliente', date_col='Data Faturamento Pedido'):
    if df.empty:
        return pd.DataFrame()

    df[date_col] = pd.to_datetime(df[date_col])
    primeira_compra = df.groupby(cliente_col)[date_col].min().reset_index()
    primeira_compra.columns = [cliente_col, 'Primeira_Compra']

    df_merged = df.merge(primeira_compra, on=cliente_col)
    df_merged['Tipo Compra'] = df_merged.apply(
        lambda row: 'Cliente Novo' if row[date_col].date() == row['Primeira_Compra'].date() else 'Recompra',
        axis=1
    )
    return df_merged

# ====================
# Função: Calcular Ticket Médio
# ====================
def calcular_ticket_medio(df):
    if df.empty:
        return 0.0
    return df['Valor Total'].sum() / len(df)

# ====================
# Upload do CSV
# ====================
st.sidebar.title("📁 Importar Dados")
uploaded_file = st.sidebar.file_uploader("Carregue seu CSV (PedidosItens)", type=["csv"])

if not uploaded_file:
    st.warning("Por favor, carregue um arquivo CSV para continuar.")
    st.stop()

# Carregar dados
df = load_data(uploaded_file)

# ====================
# Adicionar logo no topo
# ====================
col1, col2 = st.columns([3, 1])
with col2:
    if os.path.exists("Logo_Phiq.png"):
        st.image("Logo_Phiq.png", width=350)
    else:
        st.write("")

# ====================
# Navegação
# ====================
st.sidebar.title("🧭 Navegação")
page = st.sidebar.radio("Selecione a Página", ["Visão Geral", "Visão por Gestor"])

# --- Filtros comuns ---
st.sidebar.header("Filtros")

# Filtro de Estado
estados = st.sidebar.multiselect("Estados", ['PB', 'PE', 'RN'], default=['PB', 'PE', 'RN'])

# Filtro de Franquia
franquias = st.sidebar.multiselect("Franquias", df['Franquia'].unique(), default=['PHIQ'])

# Filtro de Segmento
if 'Segmento' in df.columns:
    segmentos = st.sidebar.multiselect(
        "Segmento do Cliente",
        df['Segmento'].dropna().unique(),
        default=[s for s in df['Segmento'].dropna().unique() if s != 'Não Informado']
    )
else:
    segmentos = None

# --- Filtro de Mês ---
st.sidebar.header("📅 Filtro por Mês")
df['Ano-Mês'] = df['Data Faturamento Pedido'].dt.to_period('M')
meses_disponiveis = df['Ano-Mês'].dropna().unique()
meses_disponiveis = sorted(meses_disponiveis, reverse=True)  # Do mais recente para o mais antigo
meses_disponiveis_str = [str(m) for m in meses_disponiveis]
meses_selecionados_str = st.sidebar.multiselect(
    "Selecione os meses",
    options=meses_disponiveis_str,
    default=meses_disponiveis_str[:1]  # Mês mais recente por padrão
)
meses_selecionados = [pd.Period(m, freq='M') for m in meses_selecionados_str]

# ====================
# PÁGINA 1: VISÃO GERAL
# ====================
if page == "Visão Geral":
    st.title("📊 Dashboard Comercial - Visão Geral")

    # Aplicar filtros
    df_filtered = df[df['Estado'].isin(estados) & df['Franquia'].isin(franquias)]
    if segmentos:
        df_filtered = df_filtered[df_filtered['Segmento'].isin(segmentos)]

    # ✅ Aplicar filtro de mês
    df_filtered = df_filtered[df_filtered['Ano-Mês'].isin(meses_selecionados)]

    if df_filtered.empty:
        st.warning("Nenhum dado encontrado com os filtros selecionados.")
    else:
        # === Card: Ticket Médio ===
        ticket_medio = calcular_ticket_medio(df_filtered)
        st.metric("🎫 Ticket Médio", formatar_real(ticket_medio))

        # --- Limpeza da forma de pagamento ---
        if 'Forma Pagamento' in df_filtered.columns:
            df_filtered['Forma Pagamento'] = df_filtered['Forma Pagamento'].astype(str).str.strip()
            df_filtered['Forma Pagamento'] = df_filtered['Forma Pagamento'].replace({
                r'.*Boleto.*': 'Boleto Bancário',
                r'.*28.*': 'Boleto Bancário',
                r'.*35.*': 'Boleto Bancário'
            }, regex=True)
            formas_validas = ['Boleto Bancário', 'PIX', 'Dinheiro', 'Permuta']
            df_filtered = df_filtered[df_filtered['Forma Pagamento'].isin(formas_validas)]

        # --- Gráfico: Faturamento por Mês ---
        st.subheader("📈 Faturamento por Mês")
        faturamento_mensal = df_filtered.groupby(df_filtered['Data Faturamento Pedido'].dt.to_period('M'))['Valor Total'].sum().reset_index()
        faturamento_mensal['Mês'] = faturamento_mensal['Data Faturamento Pedido'].dt.month.map({
            1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
            5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
            9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
        })
        faturamento_mensal = faturamento_mensal.sort_values('Data Faturamento Pedido')
        fig1 = px.line(faturamento_mensal, x='Mês', y='Valor Total', markers=True, title="Faturamento Mensal")
        fig1.update_traces(line_color=TEAL, marker_color=SOFT_BLUE)
        fig1.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis_title="Mês",
            yaxis_title="Faturamento (R$)",
            yaxis=dict(tickfont=dict(color="#FFFFFF"), tickformat=",.2f"),
            xaxis=dict(tickfont=dict(color="#FFFFFF")),
            font=dict(color="#FFFFFF"),
            showlegend=False
        )
        st.plotly_chart(fig1, use_container_width=True)

        # --- Gráfico de Pizza: Novos Clientes vs Recompra ---
        st.subheader("🎯 Novos Clientes vs Recompra")
        df_com_tipo = classificar_compras(df_filtered)
        if df_com_tipo.empty:
            st.info("Não há dados suficientes para classificar compras.")
        else:
            contagem_tipo = df_com_tipo['Tipo Compra'].value_counts().reset_index()
            contagem_tipo.columns = ['Tipo Compra', 'Quantidade']
            fig_pizza = px.pie(
                contagem_tipo,
                values='Quantidade',
                names='Tipo Compra',
                title="Distribuição de Novos Clientes e Recompras",
                color='Tipo Compra',
                color_discrete_map={'Cliente Novo': TEAL, 'Recompra': SOFT_BLUE}
            )
            fig_pizza.update_traces(textinfo='percent+label', pull=[0.05, 0.05])
            fig_pizza.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color="#FFFFFF"),
                title_font_size=16
            )
            st.plotly_chart(fig_pizza, use_container_width=True)

        # --- Top 10 Clientes por Faturamento ---
        st.subheader("🏆 Top 10 Clientes por Faturamento")
        top_clientes = df_filtered.groupby('Cliente')['Valor Total'].sum().sort_values(ascending=False).head(10)
        fig_top = px.bar(
            top_clientes.reset_index(),
            x='Valor Total',
            y='Cliente',
            orientation='h',
            title="Maiores Clientes por Receita",
            color='Valor Total',
            color_continuous_scale=[TEAL, SOFT_BLUE]
        )
        fig_top.update_traces(
            text=[formatar_real(v) for v in top_clientes],
            textposition='auto',
            marker_color=TEAL
        )
        fig_top.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(tickfont=dict(color="#FFFFFF"), autorange="reversed"),
            xaxis=dict(tickfont=dict(color="#FFFFFF")),
            font=dict(color="#FFFFFF"),
            showlegend=False
        )
        st.plotly_chart(fig_top, use_container_width=True)

        # --- Top 10 Produtos Mais Vendidos ---
        st.subheader("📦 Top 10 Produtos Mais Vendidos")
        df_filtered['Produto'] = df_filtered['Descrição'].str.split(' - ').str[1:].str.join(' - ')
        df_filtered['Produto'] = df_filtered['Produto'].fillna(df_filtered['Descrição'])
        top_produtos = df_filtered.groupby('Produto')['Quantidade'].sum().sort_values(ascending=False).head(10)
        fig_prod = px.bar(
            top_produtos.reset_index(),
            x='Quantidade',
            y='Produto',
            orientation='h',
            title="Produtos Mais Vendidos",
            color='Quantidade',
            color_continuous_scale=[SOFT_BLUE, TEAL],
            text='Quantidade'
        )
        fig_prod.update_traces(
            texttemplate='%{text:,}',
            textposition='auto',
            marker_color=SOFT_BLUE
        )
        fig_prod.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(tickfont=dict(color="#FFFFFF"), autorange="reversed"),
            xaxis=dict(tickfont=dict(color="#FFFFFF")),
            font=dict(color="#FFFFFF"),
            showlegend=False
        )
        st.plotly_chart(fig_prod, use_container_width=True)

        # --- Faturamento por Forma de Pagamento ---
        st.subheader("💵 Faturamento por Forma de Pagamento")
        if 'Forma Pagamento' in df_filtered.columns:
            fat_forma = df_filtered.groupby('Forma Pagamento')['Valor Total'].sum().reset_index()
            fat_forma = fat_forma.sort_values('Valor Total', ascending=True)
            fig_forma = px.bar(
                fat_forma,
                x='Valor Total',
                y='Forma Pagamento',
                orientation='h',
                title="Faturamento por Forma de Pagamento",
                color='Forma Pagamento',
                color_discrete_map={
                    'Boleto Bancário': TEAL,
                    'PIX': SOFT_BLUE,
                    'Dinheiro': '#CCCCCC',
                    'Permuta': '#AAAAAA'
                }
            )
            fig_forma.update_traces(
                text=[formatar_real(v) for v in fat_forma['Valor Total']],
                textposition='auto'
            )
            fig_forma.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(tickfont=dict(color="#FFFFFF"), autorange="reversed"),
                xaxis=dict(tickfont=dict(color="#FFFFFF")),
                font=dict(color="#FFFFFF"),
                showlegend=False
            )
            st.plotly_chart(fig_forma, use_container_width=True)

        # --- Previsão da Próxima Compra por Cliente ---
        st.subheader("📅 Previsão da Próxima Compra por Cliente")
        clientes = df_filtered['Cliente'].dropna().unique().tolist()
        selecionados = st.multiselect("Selecione os clientes", options=sorted(clientes), default=[])
        if len(selecionados) == 0:
            st.info("Selecione um ou mais clientes.")
        else:
            df_sel = df_filtered[df_filtered['Cliente'].isin(selecionados)]
            try:
                previsao = calcular_recorrencia_e_previsao(df_sel)
                if previsao.empty:
                    st.info("Clientes selecionados não têm múltiplas compras.")
                else:
                    st.dataframe(previsao, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Erro ao calcular previsão: {e}")

# ====================
# PÁGINA 2: VISÃO POR GESTOR
# ====================
else:
    st.title("👥 Dashboard por Gestor")
    gestor = st.sidebar.selectbox("Selecione o Gestor", ["Rosimere Barboza de Abreu", "Almir Farias Albuquerque"])

    if "Rosimere" in gestor:
        df_gestor = df[df['Vendedor'].str.contains('ROSIMERI', case=False, na=False) & df['Estado'].isin(estados)]
    else:
        agro_keywords = ['AGRO', 'AGRICULTURA', 'RURAL', 'FAZENDA', 'OVOS', 'AVICULTURA']
        mask_agro = (df['Segmento'].str.contains('|'.join(agro_keywords), case=False, na=False) |
                     df['Cliente'].str.contains('|'.join(agro_keywords), case=False, na=False))
        df_gestor = df[(df['Vendedor'].str.contains('ALMIR', case=False, na=False)) | (mask_agro)]

    # Aplicar filtros de segmento
    if 'Segmento' in df.columns:
        segmentos_disponiveis_gestor = df_gestor['Segmento'].dropna().unique().tolist()
        segmentos_gestor = st.sidebar.multiselect(
            "Segmento do Cliente",
            options=segmentos_disponiveis_gestor,
            default=segmentos_disponiveis_gestor
        )
        df_gestor = df_gestor[df_gestor['Segmento'].isin(segmentos_gestor)]

    # ✅ Aplicar filtro de mês
    df_gestor = df_gestor[df_gestor['Ano-Mês'].isin(meses_selecionados)]

    if df_gestor.empty:
        st.warning("Nenhum dado encontrado para o gestor selecionado.")
    else:
        ticket_gestor = calcular_ticket_medio(df_gestor)
        st.metric("🎫 Ticket Médio", formatar_real(ticket_gestor))

        # --- Limpeza da forma de pagamento ---
        if 'Forma Pagamento' in df_gestor.columns:
            df_gestor['Forma Pagamento'] = df_gestor['Forma Pagamento'].astype(str).str.strip()
            df_gestor['Forma Pagamento'] = df_gestor['Forma Pagamento'].replace({
                r'.*Boleto.*': 'Boleto Bancário',
                r'.*28.*': 'Boleto Bancário',
                r'.*35.*': 'Boleto Bancário'
            }, regex=True)
            formas_validas = ['Boleto Bancário', 'PIX', 'Dinheiro', 'Permuta']
            df_gestor = df_gestor[df_gestor['Forma Pagamento'].isin(formas_validas)]

        # --- Faturamento por Mês (Gestor) ---
        st.subheader("📈 Faturamento por Mês")
        df_gestor['Ano-Mês'] = df_gestor['Data Faturamento Pedido'].dt.to_period('M')
        fat_mensal = df_gestor.groupby('Ano-Mês')['Valor Total'].sum().reset_index()
        fat_mensal['Mês'] = fat_mensal['Ano-Mês'].dt.month.map({
            1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
            5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
            9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
        })
        fat_mensal = fat_mensal.sort_values('Ano-Mês')
        fig5 = px.line(fat_mensal, x='Mês', y='Valor Total', markers=True, title=f"Faturamento Mensal - {gestor}")
        fig5.update_traces(line_color=TEAL, marker_color=SOFT_BLUE)
        fig5.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis_title="Mês",
            yaxis_title="Faturamento (R$)",
            yaxis=dict(tickfont=dict(color="#FFFFFF"), tickformat=",.2f"),
            xaxis=dict(tickfont=dict(color="#FFFFFF")),
            font=dict(color="#FFFFFF"),
            showlegend=False
        )
        st.plotly_chart(fig5, use_container_width=True)

        # --- Novos vs Recompra (Gestor) ---
        st.subheader("🎯 Novos Clientes vs Recompra")
        df_gestor_tipo = classificar_compras(df_gestor)
        if df_gestor_tipo.empty:
            st.info("Não há dados suficientes para classificar compras.")
        else:
            contagem_tipo_gestor = df_gestor_tipo['Tipo Compra'].value_counts().reset_index()
            contagem_tipo_gestor.columns = ['Tipo Compra', 'Quantidade']
            fig_pizza_gestor = px.pie(
                contagem_tipo_gestor,
                values='Quantidade',
                names='Tipo Compra',
                title=f"Novos vs Recompra - {gestor}",
                color='Tipo Compra',
                color_discrete_map={'Cliente Novo': TEAL, 'Recompra': SOFT_BLUE}
            )
            fig_pizza_gestor.update_traces(textinfo='percent+label', pull=[0.05, 0.05])
            fig_pizza_gestor.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color="#FFFFFF"),
                title_font_size=16
            )
            st.plotly_chart(fig_pizza_gestor, use_container_width=True)

        # --- Top 10 Clientes por Faturamento (Gestor) ---
        st.subheader("🏆 Top 10 Clientes por Faturamento")
        top_clientes_gestor = df_gestor.groupby('Cliente')['Valor Total'].sum().sort_values(ascending=False).head(10)
        fig_top_clientes_gestor = px.bar(
            top_clientes_gestor.reset_index(),
            x='Valor Total',
            y='Cliente',
            orientation='h',
            title=f"Top 10 Clientes - {gestor}",
            color='Valor Total',
            color_continuous_scale=[TEAL, SOFT_BLUE]
        )
        fig_top_clientes_gestor.update_traces(
            text=[formatar_real(v) for v in top_clientes_gestor],
            textposition='auto',
            marker_color=TEAL
        )
        fig_top_clientes_gestor.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(tickfont=dict(color="#FFFFFF"), autorange="reversed"),
            xaxis=dict(tickfont=dict(color="#FFFFFF")),
            font=dict(color="#FFFFFF"),
            showlegend=False
        )
        st.plotly_chart(fig_top_clientes_gestor, use_container_width=True)

        # --- Top 10 Produtos Mais Vendidos (Gestor) ---
        st.subheader("📦 Top 10 Produtos Mais Vendidos")
        df_gestor['Produto'] = df_gestor['Descrição'].str.split(' - ').str[1:].str.join(' - ')
        df_gestor['Produto'] = df_gestor['Produto'].fillna(df_gestor['Descrição'])
        top_produtos_gestor = df_gestor.groupby('Produto')['Quantidade'].sum().sort_values(ascending=False).head(10)
        fig_top_produtos_gestor = px.bar(
            top_produtos_gestor.reset_index(),
            x='Quantidade',
            y='Produto',
            orientation='h',
            title=f"Top Produtos Vendidos - {gestor}",
            color='Quantidade',
            color_continuous_scale=[SOFT_BLUE, TEAL],
            text='Quantidade'
        )
        fig_top_produtos_gestor.update_traces(
            texttemplate='%{text:,}',
            textposition='auto',
            marker_color=SOFT_BLUE
        )
        fig_top_produtos_gestor.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(tickfont=dict(color="#FFFFFF"), autorange="reversed"),
            xaxis=dict(tickfont=dict(color="#FFFFFF")),
            font=dict(color="#FFFFFF"),
            showlegend=False
        )
        st.plotly_chart(fig_top_produtos_gestor, use_container_width=True)

        # --- Faturamento por Forma de Pagamento (Gestor) ---
        st.subheader("💵 Faturamento por Forma de Pagamento")
        if 'Forma Pagamento' in df_gestor.columns:
            faturamento_por_forma_gestor = df_gestor.groupby('Forma Pagamento')['Valor Total'].sum().reset_index()
            faturamento_por_forma_gestor = faturamento_por_forma_gestor.sort_values('Valor Total', ascending=True)
            fig_pagamento_gestor = px.bar(
                faturamento_por_forma_gestor,
                x='Valor Total',
                y='Forma Pagamento',
                orientation='h',
                title=f"Faturamento por Forma de Pagamento - {gestor}",
                labels={'Valor Total': 'Faturamento (R$)', 'Forma Pagamento': 'Forma de Pagamento'},
                color='Forma Pagamento',
                color_discrete_map={
                    'Boleto Bancário': TEAL,
                    'PIX': SOFT_BLUE,
                    'Dinheiro': '#CCCCCC',
                    'Permuta': '#AAAAAA'
                }
            )
            fig_pagamento_gestor.update_traces(
                text=[formatar_real(v) for v in faturamento_por_forma_gestor['Valor Total']],
                textposition='auto'
            )
            fig_pagamento_gestor.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(tickfont=dict(color="#FFFFFF"), autorange="reversed"),
                xaxis=dict(tickfont=dict(color="#FFFFFF")),
                font=dict(color="#FFFFFF"),
                showlegend=False
            )
            st.plotly_chart(fig_pagamento_gestor, use_container_width=True)

        # --- Previsão da Próxima Compra por Cliente (Gestor) ---
        st.subheader("📅 Previsão da Próxima Compra por Cliente")
        clientes_disponiveis_gestor = df_gestor['Cliente'].dropna().unique().tolist()
        clientes_selecionados_gestor = st.multiselect(
            "Selecione os clientes",
            options=sorted(clientes_disponiveis_gestor),
            default=[]
        )
        if len(clientes_selecionados_gestor) == 0:
            st.info("Selecione um ou mais clientes acima.")
        else:
            df_clientes_gestor = df_gestor[df_gestor['Cliente'].isin(clientes_selecionados_gestor)]
            try:
                previsao_gestor_df = calcular_recorrencia_e_previsao(df_clientes_gestor)
                if previsao_gestor_df.empty:
                    st.info("Os clientes selecionados não têm mais de um pedido para calcular recorrência.")
                else:
                    st.dataframe(previsao_gestor_df, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Erro ao calcular previsão: {e}")

# Rodapé
st.sidebar.markdown("---")
st.sidebar.info("Dashboard criado com Streamlit | Fonte: CSV importado")