import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import date, timedelta
import matplotlib.pyplot as plt
from io import BytesIO

from utils import get_fiscal_period
from custom_cards import card_html
from shifts import prepare_shift_dataframe
from pdf import create_pdf_report, create_one_page_type_report, create_one_page_a3_report

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
    response = supabase.table("view_dashboard")\
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

        df['maint_start_date'] = pd.to_datetime(df['maint_start_date'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')
        df['maint_due_date'] = pd.to_datetime(df['maint_due_date'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')
        df['maint_real_due_date'] = pd.to_datetime(df['maint_real_due_date'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')
        df['maint_status'] = df['maint_status'].fillna('Nao Definido').astype(str)
        
        if 'notes' not in df.columns: df['notes'] = ""
            
    return df

@st.cache_data(ttl=60)
def load_impacts_data():
    """Busca TODO o histórico de impactos com TAGs e calcula as horas."""
    # Query que faz o join com as manutenções e equipamentos para pegar a TAG e o Tipo
    response = supabase.table("maintenance_impacts")\
        .select("*, maintenances(type, equipments(tag))")\
        .execute()
    
    df_imp = pd.DataFrame(response.data)
    
    if not df_imp.empty:
        # Extrai a Tag e o Tipo do JSON retornado pelo Supabase
        df_imp['equipment_tag'] = df_imp['maintenances'].apply(lambda x: x['equipments']['tag'] if x and x.get('equipments') else 'N/A')
        df_imp['Tipo'] = df_imp['maintenances'].apply(lambda x: x['type'] if x else 'N/A')
        
        # Converte datas
        df_imp['start_time'] = pd.to_datetime(df_imp['start_time'])
        # Se não tiver end_time, assume o tempo atual (ou 0, ajuste conforme sua regra)
        df_imp['end_time'] = pd.to_datetime(df_imp['end_time']).fillna(pd.Timestamp.now(tz='UTC'))
        
        # Calcula as HORAS de impacto
        df_imp['horas'] = (df_imp['end_time'] - df_imp['start_time']).dt.total_seconds() / 3600.0
        df_imp['date'] = df_imp['start_time'].dt.date
        
        # Separa a Categoria da Descrição
        split_desc = df_imp['description'].str.split(' - ', n=1, expand=True)
        df_imp['Categoria'] = split_desc[0].str.strip()
        df_imp['Detalhe'] = split_desc[1].str.strip() if split_desc.shape[1] > 1 else df_imp['description']
        df_imp['Categoria'] = df_imp.apply(lambda x: 'OUTROS' if pd.isna(x['Detalhe']) else x['Categoria'], axis=1)
        
    return df_imp

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
    # ESTILIZAÇÃO E HTML DOS CARDS
    # ---------------------------------------------------------
    st.markdown("""
    <style>
        .kpi-card {
            background-color: #2b2b36;
            padding: 15px;
            border-radius: 8px;
            border-left: 5px solid #2542e6;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
            height: 140px;
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
    
    # Verifica se existem dados nas métricas
    if df_filtered_metrics.empty:
        st.info("Nenhuma meta contratual encontrada para os filtros selecionados.")
    else:
        # Identifica os Tipos de Manutenção únicos na view de consolidação
        unique_types = sorted(df_filtered_metrics['maintenance_type'].unique())
        
        # LOOP 1: Para cada Tipo de Manutenção (Agrupador Principal)
        for m_type in unique_types:
            
            st.markdown(f"## 🛠️ {m_type}")
            st.markdown("---")
            
            # Filtra os DFs para este Tipo de Manutenção
            df_metrics_type = df_filtered_metrics[df_filtered_metrics['maintenance_type'] == m_type]
            df_op_type = df_filtered[df_filtered['maintenance_type'] == m_type]
            
            # LOOP 2: Para cada Área dentro deste Tipo
            for index, row in df_metrics_type.iterrows():
                area_nome = row['area']
                
                # Subtítulo da Área
                st.markdown(f"#### 📍 Área: {area_nome}")

                # Variáveis Macro
                garantia_minima = row['goal']
                liberado_total = row['released']
                executado_total = row['done']

                # Meta Operacional do período filtrado
                meta_operacional_periodo = df_op_type[df_op_type['equipment_area'] == area_nome]['meta_turno'].sum()

                # Cálculos
                perc_liberado = (liberado_total / garantia_minima * 100) if garantia_minima > 0 else 0
                perc_produtividade = (executado_total / meta_operacional_periodo * 100) if meta_operacional_periodo > 0 else 0

                pendente_execucao = liberado_total - executado_total
                perc_pendente_exec = (pendente_execucao / liberado_total * 100) if liberado_total > 0 else 0

                pendente_liberar = garantia_minima - liberado_total
                perc_pendente_lib = (pendente_liberar / garantia_minima * 100) if garantia_minima > 0 else 0

                # Renderização dos 5 Cards
                c1, c2, c3, c4, c5 = st.columns(5)

                with c1:
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
                        f"{garantia_minima:,.0f}", 
                        perc_liberado, 
                        "#9b59b6"
                    ), unsafe_allow_html=True)
                    
                with c3:
                    st.markdown(card_html(
                        "Executado (Campo)", 
                        f"{executado_total:,.0f}", 
                        f"{meta_operacional_periodo:,.0f}", 
                        perc_produtividade, 
                        "#2ecc71"
                    ), unsafe_allow_html=True)
                    
                with c4:
                    st.markdown(card_html(
                        "Pendente Execução", 
                        f"{pendente_execucao:,.0f}", 
                        f"{liberado_total:,.0f}", 
                        perc_pendente_exec, 
                        "#f1c40f",
                        invert_logic=True 
                    ), unsafe_allow_html=True)
                    
                with c5:
                    st.markdown(card_html(
                        "Pendente Liberar", 
                        f"{pendente_liberar:,.0f}", 
                        f"{garantia_minima:,.0f}", 
                        perc_pendente_lib, 
                        "#e74c3c",
                        invert_logic=True
                    ), unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True) # Espaço entre as áreas

            # ---------------------------------------------------------
            # GRÁFICOS DO TIPO DE MANUTENÇÃO (Exibidos após os cards das áreas)
            # ---------------------------------------------------------
            st.markdown(f"#### 📊 Resumo Operacional - {m_type}")
            
            c_chart1, c_chart2 = st.columns(2)

            with c_chart1:
                st.subheader("Produção por Turno")
                df_shift = df_op_type.groupby('shift_name')[['quantity', 'meta_turno']].sum().reset_index()

                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(
                    x=df_shift['shift_name'], y=df_shift['quantity'], name='Executado', marker_color='#00CC96'
                ))
                fig_bar.add_trace(go.Bar(
                    x=df_shift['shift_name'], y=df_shift['meta_turno'], name='Meta', marker_color='#FF4B4B'
                ))

                fig_bar.update_layout(barmode='group', height=400)
                # Adiciona o m_type na KEY para evitar o erro "Duplicate Widget ID"
                st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_turno_tab1_{m_type}")
            
            with c_chart2:
                st.subheader("Produção por Equipamento")
                df_equip = df_op_type.groupby('equipment_tag')[['quantity', 'meta_turno']].sum().reset_index()

                fig_bar2 = go.Figure()
                fig_bar2.add_trace(go.Bar(
                    x=df_equip['equipment_tag'], y=df_equip['quantity'], name='Executado', marker_color='#00CC96'
                ))
                fig_bar2.add_trace(go.Bar(
                    x=df_equip['equipment_tag'], y=df_equip['meta_turno'], name='Meta', marker_color='#FF4B4B'
                ))

                fig_bar2.update_layout(barmode='group', height=400)
                st.plotly_chart(fig_bar2, use_container_width=True, key=f"bar_equip_tab1_{m_type}")
            
            st.divider()

            df_daily = df_op_type.groupby('date')[['quantity', 'meta_turno']].sum().reset_index()

            if not df_daily.empty:
                fig_line = px.line(
                    df_daily,
                    x='date',
                    y=['quantity', 'meta_turno'],
                    labels={'date': 'Data', 'value': 'Quantidade', 'variable': 'Tipo'},
                    title=f'Curva de Produção Diária - {m_type}',
                    color_discrete_map={'quantity': '#00CC96', 'meta_turno': '#FF4B4B'}
                )

                fig_line.update_layout(height=400)
                st.plotly_chart(fig_line, use_container_width=True, key=f"line_tab1_{m_type}")
            
            # Dá um respiro grande antes de começar o próximo TIPO DE MANUTENÇÃO
            st.markdown("<br><br>", unsafe_allow_html=True)
# ==========================================
# ABA 2: ACOMPANHAMENTO DETALHADO (POR TAG E TIPO)
# ==========================================
with tab2:
    col_header, col_btn = st.columns([4, 1])
    
    with col_header:
        st.markdown("### 📅 Acompanhamento Diário Detalhado")
    
    # 1. Gera o DataFrame consolidado do DIA
    df_daily_shifts = prepare_shift_dataframe(df_filtered, selected_date)
    # No seu app.py, antes do botão do PDF:
    df_impacts_all = load_impacts_data()

    # Filtra apenas os do dia selecionado para o resumo final
    df_impacts_today = df_impacts_all[df_impacts_all['date'] == selected_date] if not df_impacts_all.empty else pd.DataFrame()

    with col_btn:
        if not df_daily_shifts.empty:
            # Gera o PDF em memória
            # Passa para a função
            pdf_bytes = create_one_page_a3_report(
                df_daily_shifts,    
                df_filtered,        
                selected_date.strftime('%d/%m/%Y'),
                df_impacts_all,    # O histórico (Para os graficos dos equipamentos)
                df_impacts_today   # O do dia (Para o resumo no final do arquivo)
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
                df_tag_history = df_filtered[
                    (df_filtered['equipment_tag'] == tag) & 
                    (df_filtered['date'] <= selected_date)
                ]
                
                # C. Cálculos dos KPIs
                total_tubos = df_tag_history['total_tubos'].max() if 'total_tubos' in df_tag_history.columns else 0
                total_mapeado = total_tubos
                acumulado_exec = df_tag_history['quantity'].sum()
                pendente = total_mapeado - acumulado_exec
                perc_concluido = (acumulado_exec / total_mapeado * 100) if total_mapeado > 0 else 0
                meta_turno_val = df_tag_day['Meta'].max()

                # D. Captura Datas e Status (Tenta pegar da primeira linha)
                dt_inicio = df_tag_day['maint_start_date'].iloc[0] if 'maint_start_date' in df_tag_day.columns else '-'
                dt_previsto = df_tag_day['maint_due_date'].iloc[0] if 'maint_due_date' in df_tag_day.columns else '-'
                dt_real = df_tag_day['maint_real_due_date'].iloc[0] if 'maint_real_due_date' in df_tag_day.columns else '-'
                st_maint = df_tag_day['maint_status'].iloc[0] if 'maint_status' in df_tag_day.columns else '-'

                # --- VISUALIZAÇÃO DO CARTÃO (LARGURA TOTAL) ---
                
                with st.container(border=True):
                    
                    # 1. HEADER INTEGRADO
                    st.markdown(f"""
                        <div style="background-color: #2542e6; color: white; padding: 10px; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <div style="font-size: 1.2em; font-weight: bold; padding-left: 10px;">
                                🏭 {tag}
                            </div>
                            <div style="padding-right: 10px; font-size: 0.9em; opacity: 0.9;">
                                META DO TURNO: <strong>{meta_turno_val:.0f}</strong>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # 1.5. BARRA DE STATUS E DATAS (NOVO)
                    st.markdown(f"""
                        <div style="background-color: #2b2b36; border-left: 3px solid #f1c40f; padding: 8px 12px; border-radius: 4px; margin-bottom: 15px; font-size: 13px; color: #e0e0e0; display: flex; justify-content: space-between;">
                            <div><strong>STATUS:</strong> <span style="color: #f1c40f;">{str(st_maint).upper()}</span></div>
                            <div><strong>INÍCIO:</strong> {dt_inicio}</div>
                            <div><strong>TÉRMINO PREVISTO:</strong> {dt_previsto}</div>
                            <div><strong>TÉRMINO REAL:</strong> {dt_real}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # 2. KPIs SUPERIORES (4 Colunas)
                    c_kpi1, c_kpi2, c_kpi3, c_kpi4 = st.columns(4)
                    
                    lbl_style = "font-size: 11px; color: #aaa; text-transform: uppercase; letter-spacing: 0.5px;"
                    val_style = "font-size: 20px; font-weight: bold; color: #fff;"
                    
                    with c_kpi1:
                        st.markdown(f"<div><div style='{lbl_style}'>Total de Tubos</div><div style='{val_style}'>{total_tubos:.0f}</div></div>", unsafe_allow_html=True)
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
                        use_container_width=True, 
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


