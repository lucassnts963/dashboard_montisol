from fpdf import FPDF
import pandas as pd
import os

def create_pdf_report(df_day, df_history, date_str):
    
    # --- CORES PERSONALIZADAS (RGB) ---
    COLOR_PRIMARY = (37, 66, 230)      # Azul do Painel
    COLOR_SUCCESS = (46, 204, 113)     # Verde
    COLOR_DANGER = (231, 76, 60)       # Vermelho
    COLOR_BG_LIGHT = (245, 247, 250)   # Cinza muito claro para fundo
    COLOR_TEXT_MAIN = (50, 50, 50)     # Cinza escuro para texto
    
    # Configuração Inicial do PDF
    class PDF(FPDF):
        def header(self):
            # 1. LOGO
            if os.path.exists("logo.png"):
                # x=10, y=8, w=30 (ajuste w conforme tamanho da sua logo)
                self.image("logo.png", 10, 8, 30)
            
            # 2. TÍTULO PRINCIPAL
            self.set_font('Arial', 'B', 16)
            self.set_text_color(*COLOR_PRIMARY)
            self.cell(40) # Espaço para não sobrepor a logo
            self.cell(0, 10, 'Relatorio Diario de Producao', 0, 1, 'L')
            
            # 3. DATA
            self.set_font('Arial', '', 10)
            self.set_text_color(100, 100, 100)
            self.cell(40)
            self.cell(0, 5, f'Data de Referencia: {date_str}', 0, 1, 'L')
            
            # Linha divisória azul
            self.ln(5)
            self.set_draw_color(*COLOR_PRIMARY)
            self.set_line_width(0.5)
            self.line(10, 30, 200, 30)
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    # Instância do PDF
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    if df_day.empty:
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, "Nenhum apontamento registrado para esta data.", 0, 1)
        return pdf.output(dest='S').encode('latin-1')

    # Função auxiliar para limpar texto e acentos (Evita erro no FPDF)
    def clean_text(text):
        if not text or pd.isna(text): return "-"
        return str(text).encode('latin-1', 'replace').decode('latin-1')

    # Agrupar por Tipo (Digestão, Precipitação)
    unique_types = sorted(df_day['Tipo'].unique())

    for m_type in unique_types:
        # --- CABEÇALHO DO TIPO DA MANUTENÇÃO ---
        pdf.set_fill_color(230, 230, 230)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 12, f"  {clean_text(m_type)}", 0, 1, 'L', fill=True)
        pdf.ln(4)

        # Filtra equipamentos deste tipo
        df_type_subset = df_day[df_day['Tipo'] == m_type]
        unique_tags = sorted(df_type_subset['Tag'].unique())

        for tag in unique_tags:
            # --- DADOS DO EQUIPAMENTO ---
            df_tag_day = df_type_subset[df_type_subset['Tag'] == tag]
            
            # Histórico para KPIs (Soma até a data selecionada)
            dt_referencia = pd.to_datetime(date_str, format="%d/%m/%Y").date()
            df_tag_hist = df_history[
                (df_history['equipment_tag'] == tag) & 
                (df_history['date'] <= dt_referencia)
            ]
            
            # Cálculos dos KPIs Globais
            total_tubos = df_tag_hist['total_tubos'].max() if 'total_tubos' in df_tag_hist.columns else 0
            acumulado = df_tag_hist['quantity'].sum()
            pendente = total_tubos - acumulado
            perc = (acumulado / total_tubos * 100) if total_tubos > 0 else 0
            meta_turno = df_tag_day['Meta'].max()

            # Variáveis de Data e Status da Manutenção (Evita erro se a coluna faltar)
            dt_inicio = clean_text(df_tag_day['maint_start_date'].iloc[0]) if 'maint_start_date' in df_tag_day.columns else '-'
            dt_previsto = clean_text(df_tag_day['maint_due_date'].iloc[0]) if 'maint_due_date' in df_tag_day.columns else '-'
            dt_real = clean_text(df_tag_day['maint_real_due_date'].iloc[0]) if 'maint_real_due_date' in df_tag_day.columns else '-'
            st_maint = clean_text(df_tag_day['maint_status'].iloc[0]) if 'maint_status' in df_tag_day.columns else '-'

            # 1. Título do Equipamento
            pdf.set_font('Arial', 'B', 12)
            pdf.set_text_color(*COLOR_PRIMARY)
            pdf.cell(0, 8, f"{clean_text(tag)}", 0, 1)
            
            # 2. Linha de Status da Manutenção
            pdf.set_font('Arial', 'B', 9)
            pdf.set_text_color(50, 50, 50)
            pdf.cell(0, 5, f"Status da Manutencao: {st_maint.upper()}", 0, 1)

            # 3. Linha de Datas (Cronograma)
            pdf.set_font('Arial', '', 9)
            pdf.set_text_color(100, 100, 100)
            cronograma_line = f"Inicio: {dt_inicio}  |  Previsto: {dt_previsto}  |  Real: {dt_real}"
            pdf.cell(0, 5, cronograma_line, 0, 1)
            
            # 4. Linha de KPIs de Produção
            stats_line = f"Capacidade: {total_tubos:.0f}  |  Acumulado: {acumulado:.0f}  |  Pendente: {pendente:.0f}  |  Progresso: {perc:.1f}%"
            pdf.cell(0, 5, stats_line, 0, 1)
            pdf.ln(3)

            # --- BLOCOS DE TURNOS (LAYOUT DE CARTÃO COLORIDO) ---
            for _, row in df_tag_day.iterrows():
                real = row['Realizado']
                meta = row['Meta']
                gap = row['Desvio']
                obs = clean_text(row['Observações'])
                turno_nome = clean_text(row['Turno'])
                
                # Define cor da borda esquerda e texto do status
                if gap >= 0:
                    status_color = COLOR_SUCCESS
                    status_text = "META BATIDA"
                else:
                    status_color = COLOR_DANGER
                    status_text = "ABAIXO DA META"

                # Posição inicial do card
                x_start = pdf.get_x()
                y_start = pdf.get_y()
                
                # Quebra de página manual para não cortar o card no meio
                if y_start > 250: 
                    pdf.add_page()
                    y_start = pdf.get_y()

                card_height = 22 if not obs or obs == "-" else 30 
                
                # Retângulo Principal (Fundo)
                pdf.set_fill_color(*COLOR_BG_LIGHT)
                pdf.rect(x_start, y_start, 190, card_height, 'F')
                
                # Borda Colorida na Esquerda
                pdf.set_fill_color(*status_color)
                pdf.rect(x_start, y_start, 2, card_height, 'F')

                # Linha 1: Nome do Turno (Esq) | Status (Dir)
                pdf.set_xy(x_start + 5, y_start + 2)
                pdf.set_font('Arial', 'B', 10)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(50, 6, turno_nome, 0, 0)
                
                pdf.set_font('Arial', 'B', 8)
                pdf.set_text_color(*status_color)
                pdf.cell(0, 6, status_text, 0, 1, 'R')

                # Linha 2: Métricas (Realizado, Meta, Gap)
                pdf.set_xy(x_start + 5, y_start + 8)
                pdf.set_font('Arial', '', 9)
                pdf.set_text_color(80, 80, 80)
                
                gap_sign = "+" if gap > 0 else ""
                metricas = f"Realizado: {real:.0f}   /   Meta: {meta:.0f}   /   Desvio: {gap_sign}{gap:.0f}"
                pdf.cell(0, 6, metricas, 0, 1)

                # Linha 3: Observações (se houver)
                if obs and obs != "-":
                    pdf.set_xy(x_start + 5, y_start + 15)
                    pdf.set_font('Arial', 'I', 8)
                    pdf.set_text_color(100, 100, 100)
                    pdf.multi_cell(180, 4, f"Obs: {obs}", 0, 'L')

                # Move o Y para baixo do card gerado
                pdf.set_y(y_start + card_height + 2)

            pdf.ln(5) # Espaço entre equipamentos
        
        pdf.add_page() # Inicia uma página nova para o próximo TIPO (ex: Precipitação em folha nova)

    # Retorna os bytes do PDF gerado em memória
    return pdf.output(dest='S').encode('latin-1')