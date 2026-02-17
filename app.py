import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import date, timedelta

from utils import get_fiscal_period
from custom_cards import card_html
from shifts import prepare_shift_dataframe
from pdf import create_pdf_report

# ==============================================================================
# 1. CONFIGURAÇÃO E ESTILOS
# ==============================================================================
st.set_page_config(
    page_title="Trocador de Calor",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS para Badges e ajustes visuais
st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
        .meta-badge {
            background-color: #2542e6;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 0.9rem;
            display: inline-block;
            margin-bottom: 10px;
        }
        div[data-testid="stMetricValue"] { font-size: 26px; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONEXÃO E DADOS
# ==============================================================================
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["role"]
        return create_client(url, key)
    except Exception:
        st.error("Configure os segredos do Supabase no .streamlit/secrets.toml")
        st.stop()

supabase = init_connection()

@st.cache_data(ttl=60)
def load_data(start_date, end_date):
    response = supabase.table("view_producao_dashboard")\
        .select("*")\
        .gte("date", start_date.isoformat())\
        .lte("date", end_date.isoformat())\
        .execute()
    
    df = pd.DataFrame(response.data)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date']).dt.date
        df['quantity'] = pd.to_numeric(df['quantity']).fillna(0)
        df['meta_turno'] = pd.to_numeric(df['meta_turno']).fillna(0)
        
        # --- NOVO: Tratamento da coluna total_tubos ---
        if 'total_tubos' in df.columns:
            df['total_tubos'] = pd.to_numeric(df['total_tubos']).fillna(0)
        else:
            df['total_tubos'] = 0
            
        df['shift_name'] = df['shift_name'].astype(str)
        df['equipment_tag'] = df['equipment_tag'].fillna('N/A')
        
        if 'notes' not in df.columns: df['notes'] = ""
            
    return df


@st.cache_data(ttl=60)
def get_kpi_totals(start_date, end_date):
    """
    Busca os totais Macro:
    1. Garantia Mínima (Tabela goals)
    2. Liberado/Mapeado (Tabela maintenances)
    """
    # 1. Busca Garantia Mínima (Soma do valor das metas ativas no período)
    # Ajuste o filtro 'type' conforme sua regra (ex: 'Contratual' ou 'Faturamento Mínimo')
    resp_metrics = supabase.table("view_consolidado_manutencao")\
        .select("*")\
        .execute()
    
    df_metrics = pd.DataFrame(resp_metrics.data)
        
    return df_metrics

# ==============================================================================
# 3. SIDEBAR (FILTROS GLOBAIS)
# ==============================================================================
with st.sidebar:
    st.header("⚙️ Configurações")
    selected_date = st.date_input(
        "Data de Referência", 
        date.today() - timedelta(days=1),
        format="DD/MM/YYYY"
        )
    
    start_fiscal, end_fiscal, label_mes = get_fiscal_period(selected_date)
    st.info(f"📅 **Medição Vigente:**\n{label_mes}\n\n({start_fiscal.strftime('%d/%m')} até {end_fiscal.strftime('%d/%m')})")

    df_cycle = load_data(start_fiscal, end_fiscal)
    df_metrics = get_kpi_totals(start_fiscal, end_fiscal)

    if not df_metrics.empty:
        all_areas = sorted(df_metrics['area'].dropna().unique())
        selected_areas = st.multiselect("Filtrar Áreas", all_areas, default=all_areas)

        df_filtered_metrics = df_metrics[df_metrics['area'].isin(selected_areas)]

    if not df_cycle.empty:
        all_tags = sorted(df_cycle['equipment_tag'].dropna().unique())
        selected_tags = st.multiselect("Filtrar Equipamentos", all_tags, default=all_tags)

        df_filtered = df_cycle[df_cycle['equipment_tag'].isin(selected_tags) & df_cycle['equipment_area'].isin(selected_areas)]

    else:
        df_filtered = pd.DataFrame()

st.title("")

if df_filtered.empty:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["🖥️ Gestão à Vista", "📅 Relatório Diário", "📊 Relatórios Analíticos"])

with tab1:
    st.markdown("### 🚀 Painel de Acompanhamento Contratual")
    


    # ---------------------------------------------------------
    # 2. ESTILIZAÇÃO E HTML DOS CARDS
    # ---------------------------------------------------------
    st.markdown("""
    <style>
        .kpi-card {
            background-color: #2b2b36;
            padding: 15px;
            border-radius: 8px;
            border-left: 5px solid #2542e6;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
            height: 140px; /* Altura fixa para alinhar */
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .kpi-title { font-size: 13px; color: #a0a0a0; text-transform: uppercase; font-weight: 600; }
        .kpi-value { font-size: 26px; font-weight: bold; color: #ffffff; margin: 5px 0; }
        .kpi-footer { border-top: 1px solid #444; padding-top: 8px; margin-top: auto; }
        .kpi-meta { font-size: 12px; color: #ccc; display: flex; justify-content: space-between; }
        .kpi-badge { 
            font-size: 11px; 
            padding: 2px 6px; 
            border-radius: 4px; 
            font-weight: bold;
        }
        .badge-green { background-color: rgba(46, 204, 113, 0.2); color: #2ecc71; }
        .badge-red { background-color: rgba(231, 76, 60, 0.2); color: #e74c3c; }
        .badge-yellow { background-color: rgba(241, 196, 15, 0.2); color: #f1c40f; }
    </style>
    """, unsafe_allow_html=True)
    
    for index, row in df_filtered_metrics.iterrows():
        st.markdown("#### " + row['area'] + " - " + row['type'])

        garantia_minima = row['goal']
        liberado_total = row['released']
        executado_total = row['done']

        meta_operacional_periodo = df_filtered[(df_filtered['equipment_area'] == row['area']) & (df_filtered['maintenance_type'] == row['type'])]['meta_turno'].sum()

        perc_liberado = (liberado_total / garantia_minima * 100) if garantia_minima > 0 else 0
        perc_produtividade = (executado_total / meta_operacional_periodo * 100) if meta_operacional_periodo > 0 else 0

        pendente_execucao = liberado_total - executado_total
        perc_pendente_exec = (pendente_execucao / liberado_total * 100) if liberado_total > 0 else 0

        pendente_liberar = garantia_minima - liberado_total
        perc_pendente_lib = (pendente_liberar / garantia_minima * 100) if garantia_minima > 0 else 0

        c1, c2, c3, c4, c5 = st.columns(5)

        with c1:
            # Garantia Mínima é a referência base (100%)
            st.markdown(card_html(
                "Garantia Mínima", 
                f"{garantia_minima:,.0f}", 
                "Contrato", 
                100.0, 
                "#3498db"
            ), unsafe_allow_html=True)
        
        with c2:
            st.markdown(card_html(
                "Liberado (Eng.)", 
                f"{liberado_total:,.0f}", 
                f"{garantia_minima:,.0f}", # Meta é a Garantia
                perc_liberado, 
                "#9b59b6"
            ), unsafe_allow_html=True)
            
        with c3:
            st.markdown(card_html(
                "Executado (Campo)", 
                f"{executado_total:,.0f}", 
                f"{meta_operacional_periodo:,.0f}", # Meta é o planejado operacional
                perc_produtividade, 
                "#2ecc71"
            ), unsafe_allow_html=True)
            
        with c4:
            st.markdown(card_html(
                "Pendente Execução", 
                f"{pendente_execucao:,.0f}", 
                f"{liberado_total:,.0f}", # Base é o Liberado
                perc_pendente_exec, 
                "#f1c40f",
                invert_logic=True # Queremos que seja baixo
            ), unsafe_allow_html=True)
            
        with c5:
            st.markdown(card_html(
                "Pendente Liberar", 
                f"{pendente_liberar:,.0f}", 
                f"{garantia_minima:,.0f}", # Base é a Garantia
                perc_pendente_lib, 
                "#e74c3c",
                invert_logic=True
            ), unsafe_allow_html=True)

    st.divider()

    c_chart1, c_chart2 = st.columns(2)

    with c_chart1:
        st.subheader("Produção por Turno")
        df_shift = df_filtered.groupby('shift_name')[['quantity', 'meta_turno']].sum().reset_index()

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=df_shift['shift_name'], y=df_shift['quantity'], name='Executado', marker_color='#00CC96'
        ))
        fig_bar.add_trace(go.Bar(
            x=df_shift['shift_name'], y=df_shift['meta_turno'], name='Meta', marker_color='#FF4B4B'
        ))

        fig_bar.update_layout(barmode='group', height=400)
        st.plotly_chart(fig_bar, use_container_width=True, key="bar_tab1_v2")
    
    with c_chart2:
        st.subheader("Produção por Equipamento")
        df_shift = df_filtered.groupby('equipment_tag')[['quantity', 'meta_turno']].sum().reset_index()

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=df_shift['equipment_tag'], y=df_shift['quantity'], name='Executado', marker_color='#00CC96'
        ))
        fig_bar.add_trace(go.Bar(
            x=df_shift['equipment_tag'], y=df_shift['meta_turno'], name='Meta', marker_color='#FF4B4B'
        ))

        fig_bar.update_layout(barmode='group', height=400)
        st.plotly_chart(fig_bar, use_container_width=True, key="bar_tab1_v3")
    
    st.divider()

    df_daily = df_filtered.groupby('date')[['quantity', 'meta_turno']].sum().reset_index()

    if not df_daily.empty:
        fig_line = px.line(
            df_daily,
            x='date',
            y=['quantity', 'meta_turno'],
            labels={'date': 'Data', 'value': 'Quantidade', 'variable': 'Tipo'},
            title='Curva de Produção Diária',
            color_discrete_map={'quantity': '#00CC96', 'meta_turno': '#FF4B4B'}
        )

        fig_line.update_layout(height=400)
        st.plotly_chart(fig_line, use_container_width=True, key="line_tab1_v1")

# ==========================================
# ABA 2: ACOMPANHAMENTO DETALHADO (POR TAG E TIPO)
# ==========================================
with tab2:
    col_header, col_btn = st.columns([4, 1])
    
    with col_header:
        st.markdown("### 📅 Acompanhamento Diário Detalhado")
    
    # 1. Gera o DataFrame consolidado do DIA
    df_daily_shifts = prepare_shift_dataframe(df_filtered, selected_date)

    with col_btn:
        if not df_daily_shifts.empty:
            # Gera o PDF em memória
            pdf_bytes = create_pdf_report(
                df_daily_shifts,    # Dados do dia (tabelas)
                df_filtered,        # Dados historicos (KPIs acumulados)
                selected_date.strftime('%d/%m/%Y')
            )
            
            st.download_button(
                label="📄 Baixar PDF",
                data=pdf_bytes,
                file_name=f"Relatorio_{selected_date}.pdf",
                mime="application/pdf"
            )
    
    if df_daily_shifts.empty:
        st.info(f"Sem apontamentos para a data {selected_date.strftime('%d/%m/%Y')}.")
    else:
        # 2. Identifica os TIPOS únicos presentes no dia
        unique_types = sorted(df_daily_shifts['Tipo'].unique())
        
        # LOOP 1: Para cada Tipo de Manutenção (Seção)
        for m_type in unique_types:
            
            # Cabeçalho da Seção (Ex: DIGESTÃO, PRECIPITAÇÃO)
            st.markdown(f"## 🛠️ {m_type}")
            st.markdown("---") # Linha divisória para separar seções
            
            # Filtra equipamentos deste tipo
            df_type_subset = df_daily_shifts[df_daily_shifts['Tipo'] == m_type]
            unique_tags = sorted(df_type_subset['Tag'].unique())
            
            # LOOP 2: Para cada Equipamento deste Tipo
            for tag in unique_tags:
                
                # --- PREPARAÇÃO DOS DADOS ---
                
                # A. Dados do DIA (para a tabela deste equipamento)
                df_tag_day = df_type_subset[df_type_subset['Tag'] == tag].copy()
                
                # B. Dados do CICLO/HISTÓRICO (para os acumulados - KPIs)
                # Buscamos no df_filtered (global) para pegar o histórico até hoje
                df_tag_history = df_filtered[
                    (df_filtered['equipment_tag'] == tag) & 
                    (df_filtered['date'] <= selected_date)
                ]
                
                # C. Cálculos dos KPIs
                # Total Tubos (Capacidade)
                total_tubos = df_tag_history['total_tubos'].max() if 'total_tubos' in df_tag_history.columns else 0
                
                # Mapeado (Meta Total da Manutenção)
                # Se não houver coluna específica de escopo, assumimos igual ao total de tubos
                total_mapeado = total_tubos
                
                # Acumulado Executado
                acumulado_exec = df_tag_history['quantity'].sum()
                
                # Pendente
                pendente = total_mapeado - acumulado_exec
                perc_concluido = (acumulado_exec / total_mapeado * 100) if total_mapeado > 0 else 0
                
                # Meta do Turno Atual
                meta_turno_val = df_tag_day['Meta'].max()

                # --- VISUALIZAÇÃO DO CARTÃO (LARGURA TOTAL) ---
                
                with st.container(border=True):
                    
                    # Layout Interno do Cartão: Título à esquerda, KPIs à direita
                    # Isso otimiza o uso da largura total
                    
                    # 1. HEADER INTEGRADO
                    st.markdown(f"""
                        <div style="background-color: #2542e6; color: white; padding: 10px; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                            <div style="font-size: 1.2em; font-weight: bold; padding-left: 10px;">
                                🏭 {tag}
                            </div>
                            <div style="padding-right: 10px; font-size: 0.9em; opacity: 0.9;">
                                META DO TURNO: <strong>{meta_turno_val:.0f}</strong>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # 2. KPIs SUPERIORES (4 Colunas)
                    c_kpi1, c_kpi2, c_kpi3, c_kpi4 = st.columns(4)
                    
                    # Estilo CSS inline para padronizar
                    lbl_style = "font-size: 11px; color: #aaa; text-transform: uppercase; letter-spacing: 0.5px;"
                    val_style = "font-size: 20px; font-weight: bold; color: #fff;"
                    
                    with c_kpi1:
                        st.markdown(f"<div><div style='{lbl_style}'>Capacidade Total</div><div style='{val_style}'>{total_tubos:.0f}</div></div>", unsafe_allow_html=True)
                    with c_kpi2:
                        st.markdown(f"<div><div style='{lbl_style}'>Mapeado</div><div style='{val_style}'>{total_mapeado:.0f}</div></div>", unsafe_allow_html=True)
                    with c_kpi3:
                        st.markdown(f"<div><div style='{lbl_style}'>Acumulado Realizado</div><div style='color: #2ecc71; font-size:20px; font-weight:bold'>{acumulado_exec:.0f}</div></div>", unsafe_allow_html=True)
                    with c_kpi4:
                        color_pend = "#e74c3c" if pendente > 0 else "#2ecc71"
                        st.markdown(f"<div><div style='{lbl_style}'>Pendente</div><div style='color: {color_pend}; font-size:20px; font-weight:bold'>{pendente:.0f}</div></div>", unsafe_allow_html=True)

                    # Barra de progresso logo abaixo dos KPIs
                    st.progress(min(perc_concluido/100, 1.0))
                    st.caption(f"Progresso da Manutenção: {perc_concluido:.1f}% concluído")

                    st.divider()

                    # 3. TABELA DE TURNOS (Largura Total)
                    st.dataframe(
                        df_tag_day[['Turno', 'Realizado', 'Desvio', 'Status', 'Observações']],
                        use_container_width=True, # Garante que ocupe a tela toda
                        hide_index=True,
                        column_config={
                            "Turno": st.column_config.TextColumn("Turno", width="small"),
                            "Realizado": st.column_config.NumberColumn("Realizado", format="%d"),
                            "Desvio": st.column_config.NumberColumn("Gap", format="%+d"),
                            "Status": st.column_config.TextColumn("Status", width="small"),
                            "Observações": st.column_config.TextColumn("Anotações Operacionais", width="large")
                        }
                    )
            
            # Espaçamento entre tipos
            st.markdown("<br>", unsafe_allow_html=True)

with tab3:
    st.write("Em desenvolvimento")


