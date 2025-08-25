import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime, timedelta

# --- Configuração da página ---
st.set_page_config(
    page_title="Dashboard PHIQ - Análise de Vendas",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PALETA DE CORES (TEMA ESCURO) ---
TEAL = "#2C8B8B"        # Verde-água (Mantido como cor de destaque e da sidebar)
SOFT_BLUE = "#3A7CA5"    # Azul suave (Mantido como cor de destaque secundária)
BACKGROUND_DARK = "#0E1117" # Cor de fundo geral (preto azulado do Streamlit)
CONTENT_BG_DARK = "#1E1E1E" # Cor de fundo da área de conteúdo (cinza escuro)
TEXT_LIGHT = "#FAFAFA"      # Cor de texto clara
GRAY_LIGHT = "#CCCCCC"  # Cinza claro
GRAY_DARK = "#AAAAAA"   # Cinza escuro

# --- Estilo CSS completo (TEMA ESCURO AJUSTADO) ---
st.markdown(f"""
<style>
    /* Fundo geral escuro */
    .stApp {{
        background-color: {BACKGROUND_DARK};
    }}

    /* Área de conteúdo principal com fundo cinza escuro */
    .main .block-container {{
        background-color: {CONTENT_BG_DARK};
        color: {TEXT_LIGHT};
        border-radius: 10px;
        padding: 2rem;
    }}
    
    /* Garante que o texto dentro da área principal seja claro */
    .main .block-container, .main .block-container [class*="st-"] {{
        color: {TEXT_LIGHT};
    }}

    /* Títulos e Cabeçalhos */
    h1, h2, h3, .stTitle, .stHeader {{
        color: {TEAL} !important;
    }}

    /* Métricas */
    .stMetric-value {{
        color: {TEXT_LIGHT} !important;
    }}
    .stMetric-label {{
        color: {TEXT_LIGHT} !important;
        opacity: 0.7;
    }}

    /* Barra Lateral */
    .stSidebar {{
        background-color: {TEAL} !important;
    }}
    .stSidebar .st-emotion-cache-16idsys p {{
        color: {TEXT_LIGHT} !important;
    }}

    /* Multiselect na barra lateral */
    .stMultiSelect [data-baseweb="tag"] {{
        background-color: {SOFT_BLUE} !important;
        color: white !important;
    }}
</style>
""", unsafe_allow_html=True)

# ====================
# Funções de Formatação
# ====================
def formatar_real(valor):
    try:
        return f"R$ {valor:,.2f}".replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"

def formatar_numero_abreviado(valor):
    try:
        valor = float(valor)
        if valor >= 1_000_000:
            return f"R$ {valor/1_000_000:.1f} M".replace('.', ',')
        if valor >= 1_000:
            return f"R$ {valor/1_000:.1f} MIL".replace('.', ',')
        return f"R$ {valor:,.2f}".replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"

def formatar_inteiro(valor):
    try:
        return f"{int(valor):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"

# ====================
# Função para carregar e preparar dados
# ====================
@st.cache_data
def load_data(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file, encoding='utf-8', on_bad_lines='skip', low_memory=False)
    except Exception as e:
        st.error(f"Erro ao ler o CSV: {e}")
        st.stop()

    df.columns = df.columns.str.strip()
    
    column_mapping = {
        'Data Faturamento Pedido': 'Data Faturamento Pedido', 'Cliente': 'Cliente',
        'Estado': 'Estado', 'UF': 'Estado', 'Vendedor': 'Vendedor',
        'Preço Venda Total (R$)': 'Valor Total', 'Valor Total': 'Valor Total',
        'Descrição': 'Descrição', 'Forma Pagamento': 'Forma Pagamento',
        'SEGMENTO ': 'Segmento', 'SEGMENTO': 'Segmento', 'Franquia': 'Franquia',
        'Data': 'Data'
    }
    for old, new in column_mapping.items():
        if old in df.columns:
            df.rename(columns={old: new}, inplace=True)

    if 'Franquia' not in df.columns:
        df['Franquia'] = 'PHIQ'

    date_cols = ['Data', 'Data Faturamento Pedido']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    
    numeric_cols = ['Valor Total', 'Quantidade']
    for col in numeric_cols:
        if col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df.dropna(subset=['Valor Total', 'Data Faturamento Pedido', 'Quantidade'], inplace=True)

    text_cols = ['Estado', 'Vendedor', 'Segmento']
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.upper()

    if 'Segmento' in df.columns:
        df['Segmento'] = df['Segmento'].replace(['', 'nan'], 'Não Informado')
        df['Segmento'] = df['Segmento'].replace({
            'CLIENTE FÁBRICA ': 'CLIENTE FÁBRICA', 'CLIENTE FÁBRICA': 'CLIENTE FÁBRICA',
            'INSTITUCIONAL ': 'INSTITUCIONAL', 'INDUSTRIAL ': 'INDUSTRIAL'
        })
    return df

# ====================
# Funções de Análise
# ====================
def calcular_recorrencia_e_previsao(df, cliente_col='Cliente', date_col='Data Faturamento Pedido'):
    if df.empty or len(df) < 2:
        return pd.DataFrame()
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df = df.dropna(subset=[date_col])
    df['Data_Sem_Hora'] = df[date_col].dt.date
    compras_unicas = df[[cliente_col, 'Data_Sem_Hora']].drop_duplicates().sort_values([cliente_col, 'Data_Sem_Hora'])
    contagem_compras = compras_unicas.groupby(cliente_col).size().reset_index(name='Nº de Compras')
    clientes_recorrentes = contagem_compras[contagem_compras['Nº de Compras'] >= 2][cliente_col]
    compras_unicas = compras_unicas[compras_unicas[cliente_col].isin(clientes_recorrentes)]
    if compras_unicas.empty:
        return pd.DataFrame()
    compras_unicas['Data_Sem_Hora'] = pd.to_datetime(compras_unicas['Data_Sem_Hora'])
    compras_unicas['Diferença Dias'] = compras_unicas.groupby(cliente_col)['Data_Sem_Hora'].diff().dt.days
    recorrencia = compras_unicas.groupby(cliente_col).agg(
        Ultima_Compra=('Data_Sem_Hora', 'max'),
        Ritmo_Dias=('Diferença Dias', 'median')
    ).reset_index()
    recorrencia = recorrencia.dropna(subset=['Ritmo_Dias'])
    recorrencia['Ritmo_Dias'] = recorrencia['Ritmo_Dias'].round(0).astype(int)
    recorrencia = recorrencia.merge(contagem_compras, on=cliente_col)
    recorrencia['Próxima Compra'] = recorrencia['Ultima_Compra'] + pd.to_timedelta(recorrencia['Ritmo_Dias'], unit='D')
    
    recorrencia['Ritmo (dias)'] = recorrencia['Ritmo_Dias'].astype(int)
    recorrencia['Nº de Compras'] = recorrencia['Nº de Compras'].astype(int)

    recorrencia['Última Compra'] = recorrencia['Ultima_Compra'].dt.strftime('%d/%m/%Y')
    recorrencia['Próxima Compra'] = recorrencia['Próxima Compra'].dt.strftime('%d/%m/%Y')
    
    return recorrencia[[
        cliente_col, 'Nº de Compras', 'Ritmo (dias)', 'Última Compra', 'Próxima Compra'
    ]].rename(columns={cliente_col: 'Cliente'})

def classificar_compras(df, cliente_col='Cliente', date_col='Data Faturamento Pedido', venda_col='Código Venda'):
    if df.empty or date_col not in df.columns:
        return pd.DataFrame()
    if venda_col not in df.columns:
        st.warning(f"Coluna '{venda_col}' não encontrada. A análise de 'Novos x Recompra' pode ser imprecisa.")
        df[date_col] = pd.to_datetime(df[date_col])
        primeira_compra = df.groupby(cliente_col)[date_col].min().reset_index()
        primeira_compra.columns = [cliente_col, 'Primeira_Compra']
        df_merged = df.merge(primeira_compra, on=cliente_col)
        df_merged['Tipo Compra'] = df_merged.apply(lambda row: 'Cliente Novo' if row[date_col].date() == row['Primeira_Compra'].date() else 'Recompra', axis=1)
        return df_merged

    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df_sem_na = df.dropna(subset=[date_col])
    primeira_transacao_idx = df_sem_na.loc[df_sem_na.groupby(cliente_col)[date_col].idxmin()]
    primeira_venda_lookup = primeira_transacao_idx[[cliente_col, venda_col]].rename(columns={venda_col: 'Primeira_Venda_Codigo'})
    df_merged = df.merge(primeira_venda_lookup, on=cliente_col, how='left')
    df_merged['Tipo Compra'] = 'Recompra'
    df_merged.loc[df_merged[venda_col] == df_merged['Primeira_Venda_Codigo'], 'Tipo Compra'] = 'Cliente Novo'
    return df_merged

def calcular_ticket_medio_por_pedido(df):
    if df.empty: return 0.0
    if 'Código Venda' in df.columns:
        faturamento_total = df['Valor Total'].sum()
        numero_de_pedidos = df['Código Venda'].nunique()
        if numero_de_pedidos == 0: return 0.0
        return faturamento_total / numero_de_pedidos
    else:
        st.warning("Coluna 'Código Venda' não encontrada para calcular o Ticket Médio.")
        return 0.0

# ====================
# Início da Aplicação Streamlit
# ====================
st.sidebar.title("📁 Importar Dados")
uploaded_file = st.sidebar.file_uploader("Carregue seu CSV (PedidosItens)", type=["csv"])

if not uploaded_file:
    st.warning("Por favor, carregue um arquivo CSV para continuar.")
    st.stop()

df = load_data(uploaded_file)

if os.path.exists("Logo_Phiq.png"):
    st.image("Logo_Phiq.png", width=200)

st.sidebar.title("🧭 Navegação")
page = st.sidebar.radio("Selecione a Página", ["Visão Geral", "Visão por Gestor"])
st.sidebar.header("Filtros Gerais")

all_estados = sorted(df['Estado'].dropna().unique())
estados = st.sidebar.multiselect("Estados", options=all_estados, default=all_estados)
franquias = st.sidebar.multiselect("Franquias", df['Franquia'].unique(), default=df['Franquia'].unique())

if page == "Visão Geral":
    if 'Segmento' in df.columns:
        all_segmentos = df['Segmento'].dropna().unique()
        default_segmentos = [s for s in all_segmentos if s != 'Não Informado']
        segmentos = st.sidebar.multiselect("Segmento", all_segmentos, default=default_segmentos)
    else:
        segmentos = None

st.sidebar.header("📅 Filtro por Período")
min_date = df['Data Faturamento Pedido'].min().date()
max_date = df['Data Faturamento Pedido'].max().date()

default_start_date = max_date - timedelta(days=30)
if default_start_date < min_date:
    default_start_date = min_date

start_date = st.sidebar.date_input("Data Inicial", value=default_start_date, min_value=min_date, max_value=max_date)
end_date = st.sidebar.date_input("Data Final", value=max_date, min_value=min_date, max_value=max_date)

if start_date > end_date:
    st.sidebar.error("A Data Inicial não pode ser posterior à Data Final.")
    st.stop()

# ====================
# PÁGINA 1: VISÃO GERAL
# ====================
if page == "Visão Geral":
    st.title("📊 Dashboard Comercial - Visão Geral")
    
    df_filtered = df[
        (df['Estado'].isin(estados)) & 
        (df['Franquia'].isin(franquias)) &
        (df['Data Faturamento Pedido'].dt.date >= start_date) &
        (df['Data Faturamento Pedido'].dt.date <= end_date)
    ]
    if segmentos:
        df_filtered = df_filtered[df_filtered['Segmento'].isin(segmentos)]

    if df_filtered.empty:
        st.warning("Nenhum dado encontrado com os filtros selecionados.")
    else:
        ticket_medio = calcular_ticket_medio_por_pedido(df_filtered)
        st.metric("🎫 Ticket Médio", formatar_real(ticket_medio))

        st.subheader("📈 Faturamento no Período")
        view_mode_geral = st.radio("Visualizar por:", ["Mês", "Dia"], horizontal=True, key='view_geral')
        
        if view_mode_geral == 'Mês':
            faturamento_grafico = df_filtered.set_index('Data Faturamento Pedido').groupby(pd.Grouper(freq='M'))['Valor Total'].sum().reset_index()
            faturamento_grafico['Eixo_X'] = faturamento_grafico['Data Faturamento Pedido'].dt.strftime('%b/%y')
            titulo = "Faturamento Mensal no Período"
        else: # Dia
            faturamento_grafico = df_filtered.set_index('Data Faturamento Pedido').groupby(pd.Grouper(freq='D'))['Valor Total'].sum().reset_index()
            faturamento_grafico['Eixo_X'] = faturamento_grafico['Data Faturamento Pedido']
            titulo = "Faturamento Diário no Período"

        fig1 = px.line(faturamento_grafico, x='Eixo_X', y='Valor Total', title=titulo, markers=True)
        fig1.update_traces(line_color=TEAL)
        fig1.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color=TEXT_LIGHT)
        st.plotly_chart(fig1, use_container_width=True)

        st.subheader("🎯 Novos Clientes vs Recompra")
        df_com_tipo = classificar_compras(df_filtered)
        if not df_com_tipo.empty:
            contagem_tipo = df_com_tipo['Tipo Compra'].value_counts().reset_index()
            contagem_tipo.columns = ['Tipo Compra', 'Quantidade']
            fig_pizza = px.pie(contagem_tipo, values='Quantidade', names='Tipo Compra', title="Distribuição de Novos Clientes e Recompras",
                               color='Tipo Compra', color_discrete_map={'Cliente Novo': TEAL, 'Recompra': SOFT_BLUE})
            fig_pizza.update_traces(textinfo='percent+label', pull=[0.05, 0.05])
            fig_pizza.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color=TEXT_LIGHT, legend_font_color=TEXT_LIGHT)
            st.plotly_chart(fig_pizza, use_container_width=True)

        st.subheader("🏆 Top 10 Clientes por Faturamento")
        top_clientes = df_filtered.groupby('Cliente')['Valor Total'].sum().nlargest(10)
        fig_top = px.bar(top_clientes.reset_index(), x='Valor Total', y='Cliente', orientation='h', title="Maiores Clientes por Faturamento")
        fig_top.update_traces(text=[formatar_numero_abreviado(v) for v in top_clientes], textposition='auto', marker_color=TEAL)
        fig_top.update_layout(yaxis=dict(autorange="reversed"), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color=TEXT_LIGHT)
        st.plotly_chart(fig_top, use_container_width=True)
        
        st.subheader("📦 Top 10 Produtos Mais Vendidos")
        analise_produtos_por_geral = st.radio("Analisar por:", ["Quantidade", "Faturamento"], horizontal=True, key='analise_produtos_geral')
        
        if 'Quantidade' in df_filtered.columns:
            df_filtered['Produto'] = df_filtered['Descrição'].str.split(' - ').str[1:].str.join(' - ').fillna(df_filtered['Descrição'])
            
            if analise_produtos_por_geral == "Quantidade":
                top_produtos = df_filtered.groupby('Produto')['Quantidade'].sum().nlargest(10)
                text_labels = [formatar_inteiro(q) for q in top_produtos]
                fig_prod = px.bar(top_produtos.reset_index(), x='Quantidade', y='Produto', orientation='h', title="Produtos Mais Vendidos por Quantidade",
                                  color='Quantidade', color_continuous_scale=[SOFT_BLUE, TEAL], text=text_labels)
                fig_prod.update_traces(textposition='auto', marker_color=SOFT_BLUE)
            else: # Faturamento
                top_produtos = df_filtered.groupby('Produto')['Valor Total'].sum().nlargest(10)
                text_labels = [formatar_numero_abreviado(v) for v in top_produtos]
                fig_prod = px.bar(top_produtos.reset_index(), x='Valor Total', y='Produto', orientation='h', title="Produtos Mais Vendidos por Faturamento",
                                  color='Valor Total', color_continuous_scale=[TEAL, SOFT_BLUE], text=text_labels)
                fig_prod.update_traces(textposition='auto', marker_color=TEAL)

            fig_prod.update_layout(yaxis=dict(autorange="reversed"), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color=TEXT_LIGHT)
            st.plotly_chart(fig_prod, use_container_width=True)
        else:
            st.warning("A coluna 'Quantidade' não foi encontrada para gerar o ranking de produtos.")
        
        st.subheader("💵 Faturamento por Forma de Pagamento")
        if 'Forma Pagamento' in df_filtered.columns:
            df_filtered['Forma Pagamento'] = df_filtered['Forma Pagamento'].astype(str).str.strip().replace({r'.*Boleto.*': 'Boleto Bancário', r'.*28.*': 'Boleto Bancário', r'.*35.*': 'Boleto Bancário'}, regex=True)
            formas_validas = ['Boleto Bancário', 'PIX', 'Dinheiro', 'Permuta']
            df_pagamento_filtrado = df_filtered[df_filtered['Forma Pagamento'].isin(formas_validas)]
            fat_forma = df_pagamento_filtrado.groupby('Forma Pagamento')['Valor Total'].sum().reset_index()
            
            fig_forma = px.pie(
                fat_forma, 
                values='Valor Total', 
                names='Forma Pagamento', 
                title="Proporção por Forma de Pagamento",
                color='Forma Pagamento',
                color_discrete_map={
                    'Boleto Bancário': TEAL, 'PIX': SOFT_BLUE,
                    'Dinheiro': GRAY_LIGHT, 'Permuta': GRAY_DARK
                }
            )
            fig_forma.update_traces(textinfo='percent+label', pull=[0.05] * len(fat_forma))
            fig_forma.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color=TEXT_LIGHT, legend_font_color=TEXT_LIGHT)
            st.plotly_chart(fig_forma, use_container_width=True)

        st.subheader("📅 Previsão da Próxima Compra por Cliente")
        clientes = sorted(df_filtered['Cliente'].dropna().unique().tolist())
        selecionados = st.multiselect("Selecione os clientes", options=clientes, default=[])
        if selecionados:
            df_sel = df_filtered[df_filtered['Cliente'].isin(selecionados)]
            previsao = calcular_recorrencia_e_previsao(df_sel)
            if not previsao.empty:
                st.dataframe(previsao, use_container_width=True, hide_index=True)
            else:
                st.info("Clientes selecionados não têm compras suficientes para calcular a recorrência.")
        else:
            st.info("Selecione um ou mais clientes para ver a previsão.")

# ====================
# PÁGINA 2: VISÃO POR GESTOR
# ====================
else:
    st.title("👥 Dashboard por Gestor")
    gestor = st.sidebar.selectbox("Selecione o Gestor", ["Rosimere Barboza de Abreu", "Almir Farias Albuquerque"])

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"##### Filtros Específicos ({gestor.split(' ')[0]})")

    agro_keywords = ['AGRO', 'AGRICULTURA', 'RURAL', 'FAZENDA', 'OVOS', 'AVICULTURA']
    mask_agro = (df['Segmento'].str.contains('|'.join(agro_keywords), case=False, na=False) |
                 df['Cliente'].str.contains('|'.join(agro_keywords), case=False, na=False))

    if "Almir" in gestor:
        df_gestor_base = df[df['Vendedor'].str.contains('ALMIR', case=False, na=False) | mask_agro]
    else: # Rosimere
        df_gestor_base = df[df['Vendedor'].str.contains('ROSIMERI', case=False, na=False) & ~mask_agro]

    df_gestor_filtrado = df_gestor_base[
        (df_gestor_base['Estado'].isin(estados)) &
        (df_gestor_base['Data Faturamento Pedido'].dt.date >= start_date) &
        (df_gestor_base['Data Faturamento Pedido'].dt.date <= end_date)
    ]

    segmentos_selecionados_gestor = []
    if 'Segmento' in df_gestor_filtrado.columns:
        if "Rosimere" in gestor:
            rosimeri_segments_by_state = {
                'PB': ['INSTITUCIONAL', 'INDUSTRIAL', 'CLIENTE FÁBRICA'],
                'PE': ['INDUSTRIAL'],
                'RN': ['INDUSTRIAL']
            }
            allowed_segments = set()
            for state in estados:
                allowed_segments.update(rosimeri_segments_by_state.get(state, []))
            
            options = sorted([s for s in allowed_segments if s in df_gestor_filtrado['Segmento'].unique()])
            segmentos_selecionados_gestor = st.sidebar.multiselect("Segmentos Atendidos", options=options, default=options)
        else: # Almir
            options = sorted(df_gestor_filtrado['Segmento'].dropna().unique())
            segmentos_selecionados_gestor = st.sidebar.multiselect("Segmentos Atendidos", options=options, default=options)

    if segmentos_selecionados_gestor:
        df_gestor = df_gestor_filtrado[df_gestor_filtrado['Segmento'].isin(segmentos_selecionados_gestor)]
    else:
        df_gestor = df_gestor_filtrado
        
    if df_gestor.empty:
        st.warning("Nenhum dado encontrado para o gestor com os filtros selecionados.")
    else:
        col1, col2, col3 = st.columns(3)
        
        faturamento_total_gestor = df_gestor['Valor Total'].sum()
        col1.metric("💰 Faturamento Total", formatar_numero_abreviado(faturamento_total_gestor))

        ticket_gestor = calcular_ticket_medio_por_pedido(df_gestor)
        col2.metric("🎫 Ticket Médio", formatar_real(ticket_gestor))

        if 'Código Venda' in df_gestor.columns:
            pedidos_unicos_gestor = df_gestor['Código Venda'].nunique()
            col3.metric("🛒 Pedidos Únicos", f"{pedidos_unicos_gestor}")

        st.subheader("📈 Faturamento no Período")
        view_mode_gestor = st.radio("Visualizar por:", ["Mês", "Dia"], horizontal=True, key='view_gestor')
        
        if view_mode_gestor == 'Mês':
            faturamento_grafico_gestor = df_gestor.set_index('Data Faturamento Pedido').groupby(pd.Grouper(freq='M'))['Valor Total'].sum().reset_index()
            faturamento_grafico_gestor['Eixo_X'] = faturamento_grafico_gestor['Data Faturamento Pedido'].dt.strftime('%b/%y')
            titulo_gestor = f"Faturamento Mensal - {gestor}"
        else: # Dia
            faturamento_grafico_gestor = df_gestor.set_index('Data Faturamento Pedido').groupby(pd.Grouper(freq='D'))['Valor Total'].sum().reset_index()
            faturamento_grafico_gestor['Eixo_X'] = faturamento_grafico_gestor['Data Faturamento Pedido']
            titulo_gestor = f"Faturamento Diário - {gestor}"

        fig5 = px.line(faturamento_grafico_gestor, x='Eixo_X', y='Valor Total', title=titulo_gestor, markers=True)
        fig5.update_traces(line_color=TEAL)
        fig5.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color=TEXT_LIGHT)
        st.plotly_chart(fig5, use_container_width=True)

        st.subheader("🎯 Novos Clientes vs Recompra")
        df_gestor_tipo = classificar_compras(df_gestor)
        if not df_gestor_tipo.empty:
            contagem_tipo_gestor = df_gestor_tipo['Tipo Compra'].value_counts().reset_index()
            contagem_tipo_gestor.columns = ['Tipo Compra', 'Quantidade']
            fig_pizza_gestor = px.pie(contagem_tipo_gestor, values='Quantidade', names='Tipo Compra', title=f"Novos vs Recompra - {gestor}",
                                      color='Tipo Compra', color_discrete_map={'Cliente Novo': TEAL, 'Recompra': SOFT_BLUE})
            fig_pizza_gestor.update_traces(textinfo='percent+label', pull=[0.05, 0.05])
            fig_pizza_gestor.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color=TEXT_LIGHT, legend_font_color=TEXT_LIGHT)
            st.plotly_chart(fig_pizza_gestor, use_container_width=True)

        st.subheader("🏆 Top 10 Clientes por Faturamento")
        top_clientes_gestor = df_gestor.groupby('Cliente')['Valor Total'].sum().nlargest(10)
        fig_top_clientes_gestor = px.bar(top_clientes_gestor.reset_index(), x='Valor Total', y='Cliente', orientation='h', title=f"Top 10 Clientes por Faturamento - {gestor}")
        fig_top_clientes_gestor.update_traces(text=[formatar_numero_abreviado(v) for v in top_clientes_gestor], textposition='auto', marker_color=TEAL)
        fig_top_clientes_gestor.update_layout(yaxis=dict(autorange="reversed"), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color=TEXT_LIGHT)
        st.plotly_chart(fig_top_clientes_gestor, use_container_width=True)
        
        st.subheader("📦 Top 10 Produtos Mais Vendidos")
        analise_produtos_por_gestor = st.radio("Analisar por:", ["Quantidade", "Faturamento"], horizontal=True, key='analise_produtos_gestor')

        if 'Quantidade' in df_gestor.columns:
            df_gestor['Produto'] = df_gestor['Descrição'].str.split(' - ').str[1:].str.join(' - ').fillna(df_gestor['Descrição'])
            
            if analise_produtos_por_gestor == "Quantidade":
                top_produtos_gestor = df_gestor.groupby('Produto')['Quantidade'].sum().nlargest(10)
                text_labels_gestor = [formatar_inteiro(q) for q in top_produtos_gestor]
                fig_top_produtos_gestor = px.bar(top_produtos_gestor.reset_index(), x='Quantidade', y='Produto', orientation='h', title=f"Top Produtos Vendidos por Quantidade - {gestor}",
                                                 color='Quantidade', color_continuous_scale=[SOFT_BLUE, TEAL], text=text_labels_gestor)
                fig_top_produtos_gestor.update_traces(textposition='auto', marker_color=SOFT_BLUE)
            else: # Faturamento
                top_produtos_gestor = df_gestor.groupby('Produto')['Valor Total'].sum().nlargest(10)
                text_labels_gestor = [formatar_numero_abreviado(v) for v in top_produtos_gestor]
                fig_top_produtos_gestor = px.bar(top_produtos_gestor.reset_index(), x='Valor Total', y='Produto', orientation='h', title=f"Top Produtos Vendidos por Faturamento - {gestor}",
                                                 color='Valor Total', color_continuous_scale=[TEAL, SOFT_BLUE], text=text_labels_gestor)
                fig_top_produtos_gestor.update_traces(textposition='auto', marker_color=TEAL)

            fig_top_produtos_gestor.update_layout(yaxis=dict(autorange="reversed"), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color=TEXT_LIGHT)
            st.plotly_chart(fig_top_produtos_gestor, use_container_width=True)
        else:
            st.warning("A coluna 'Quantidade' não foi encontrada para gerar o ranking de produtos.")
        
        st.subheader("💵 Faturamento por Forma de Pagamento")
        if 'Forma Pagamento' in df_gestor.columns:
            df_gestor['Forma Pagamento'] = df_gestor['Forma Pagamento'].astype(str).str.strip().replace({r'.*Boleto.*': 'Boleto Bancário', r'.*28.*': 'Boleto Bancário', r'.*35.*': 'Boleto Bancário'}, regex=True)
            formas_validas = ['Boleto Bancário', 'PIX', 'Dinheiro', 'Permuta']
            df_pagamento_gestor_filtrado = df_gestor[df_gestor['Forma Pagamento'].isin(formas_validas)]
            faturamento_por_forma_gestor = df_pagamento_gestor_filtrado.groupby('Forma Pagamento')['Valor Total'].sum().reset_index()

            fig_pagamento_gestor = px.pie(
                faturamento_por_forma_gestor,
                values='Valor Total',
                names='Forma Pagamento',
                title=f"Proporção por Forma de Pagamento - {gestor}",
                color='Forma Pagamento',
                color_discrete_map={
                    'Boleto Bancário': TEAL, 'PIX': SOFT_BLUE,
                    'Dinheiro': GRAY_LIGHT, 'Permuta': GRAY_DARK
                }
            )
            fig_pagamento_gestor.update_traces(textinfo='percent+label', pull=[0.05] * len(faturamento_por_forma_gestor))
            fig_pagamento_gestor.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color=TEXT_LIGHT, legend_font_color=TEXT_LIGHT)
            st.plotly_chart(fig_pagamento_gestor, use_container_width=True)

        st.subheader("📅 Previsão da Próxima Compra por Cliente")
        clientes_disponiveis_gestor = sorted(df_gestor['Cliente'].dropna().unique().tolist())
        clientes_selecionados_gestor = st.multiselect("Selecione os clientes ", options=clientes_disponiveis_gestor, default=[])
        if clientes_selecionados_gestor:
            df_clientes_gestor = df_gestor[df_gestor['Cliente'].isin(clientes_selecionados_gestor)]
            previsao_gestor_df = calcular_recorrencia_e_previsao(df_clientes_gestor)
            if not previsao_gestor_df.empty:
                st.dataframe(previsao_gestor_df, use_container_width=True, hide_index=True)
            else:
                st.info("Os clientes selecionados não têm mais de um pedido para calcular recorrência.")
        else:
            st.info("Selecione um ou mais clientes acima.")

# Rodapé
st.sidebar.markdown("---")
st.sidebar.info("Dashboard criado com Streamlit")
