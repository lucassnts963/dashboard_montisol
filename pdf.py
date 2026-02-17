from fpdf import FPDF
import io
import pandas as pd
import os

def create_pdf_report(df_day, df_history, date_str):
    
    # --- CORES PERSONALIZADAS (RGB) ---
    COLOR_PRIMARY = (37, 66, 230)      # Azul do Painel
    COLOR_SUCCESS = (46, 204, 113)     # Verde
    COLOR_DANGER = (231, 76, 60)       # Vermelho
    COLOR_BG_LIGHT = (245, 247, 250)   # Cinza muito claro para fundo
    COLOR_TEXT_MAIN = (50, 50, 50)     # Cinza escuro para texto
    
    class PDF(FPDF):
        def header(self):
            # 1. LOGO
            if os.path.exists("logo.png"):
                # x=10, y=8, w=30 (ajuste w conforme tamanho da sua logo)
                self.image("logo.png", 10, 8, 30)
            
            # 2. TÍTULO PRINCIPAL
            self.set_font('Arial', 'B', 16)
            self.set_text_color(*COLOR_PRIMARY)
            # Move para a direita para não ficar em cima da logo
            self.cell(40) 
            self.cell(0, 10, 'Relatório Diário de Produção', 0, 1, 'L')
            
            # 3. DATA
            self.set_font('Arial', '', 10)
            self.set_text_color(100, 100, 100)
            self.cell(40)
            self.cell(0, 5, f'Data de Referência: {date_str}', 0, 1, 'L')
            
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

    # Função auxiliar para limpar texto (acentos)
    def clean_text(text):
        if not text: return ""
        return str(text).encode('latin-1', 'replace').decode('latin-1')

    # Agrupar por Tipo (Digestão, Precipitação)
    unique_types = sorted(df_day['Tipo'].unique())

    for m_type in unique_types:
        # --- CABEÇALHO DO TIPO (SECÇÃO) ---
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
            
            # Histórico para KPIs
            df_tag_hist = df_history[
                (df_history['equipment_tag'] == tag) & 
                (df_history['date'] <= pd.to_datetime(date_str).date())
            ]
            
            total_tubos = df_tag_hist['total_tubos'].max() if 'total_tubos' in df_tag_hist.columns else 0
            acumulado = df_tag_hist['quantity'].sum()
            pendente = total_tubos - acumulado
            perc = (acumulado / total_tubos * 100) if total_tubos > 0 else 0
            
            # 1. Título do Equipamento e KPIs Globais
            pdf.set_font('Arial', 'B', 12)
            pdf.set_text_color(*COLOR_PRIMARY)
            pdf.cell(0, 8, f"{clean_text(tag)}", 0, 1)
            
            # Linha fina de resumo abaixo do nome
            pdf.set_font('Arial', '', 9)
            pdf.set_text_color(100, 100, 100)
            stats_line = f"Capacidade: {total_tubos:.0f}  |  Acumulado: {acumulado:.0f}  |  Pendente: {pendente:.0f}  |  Progresso: {perc:.1f}%"
            pdf.cell(0, 5, stats_line, 0, 1)
            pdf.ln(3)

            # --- BLOCOS DE TURNOS (LAYOUT DE CARTÃO) ---
            for _, row in df_tag_day.iterrows():
                real = row['Realizado']
                meta = row['Meta']
                gap = row['Desvio']
                obs = clean_text(row['Observações'])
                turno_nome = clean_text(row['Turno'])
                
                # Define cor da borda esquerda baseada no status
                if gap >= 0:
                    status_color = COLOR_SUCCESS
                    status_text = "META BATIDA"
                else:
                    status_color = COLOR_DANGER
                    status_text = "ABAIXO DA META"

                # Fundo do Card do Turno
                pdf.set_fill_color(*COLOR_BG_LIGHT)
                # Desenha um retângulo de fundo para o turno
                # x, y, w, h
                x_start = pdf.get_x()
                y_start = pdf.get_y()
                
                # Verifica quebra de página manual para não cortar o card
                if y_start > 250: 
                    pdf.add_page()
                    y_start = pdf.get_y()

                card_height = 22 if not obs else 30 # Altura maior se tiver obs
                
                # Retângulo Principal
                pdf.rect(x_start, y_start, 190, card_height, 'F')
                
                # Borda Colorida na Esquerda (Indicador Visual)
                pdf.set_fill_color(*status_color)
                pdf.rect(x_start, y_start, 2, card_height, 'F')

                # Conteúdo do Card
                pdf.set_xy(x_start + 5, y_start + 2)
                
                # Linha 1: Nome do Turno (Negrito) | Status (Direita)
                pdf.set_font('Arial', 'B', 10)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(50, 6, turno_nome, 0, 0)
                
                # Status no canto direito
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
                if obs:
                    pdf.set_xy(x_start + 5, y_start + 15)
                    pdf.set_font('Arial', 'I', 8)
                    pdf.set_text_color(100, 100, 100)
                    # MultiCell para quebrar linha se a obs for longa
                    pdf.multi_cell(180, 4, f"Obs: {obs}", 0, 'L')

                # Espaço após o card
                pdf.set_y(y_start + card_height + 2)

            pdf.ln(3) # Espaço entre equipamentos
        
        pdf.add_page() # Quebra de página entre TIPOS (Opcional, remove se quiser contínuo)

    return pdf.output(dest='S').encode('latin-1')
    # Configuração Inicial do PDF
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, f'Relatorio Diario de Producao - {date_str}', 0, 1, 'C')
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Cores e Fontes
    pdf.set_text_color(0, 0, 0)

    # 1. Agrupar dados (mesma logica da Tab 2)
    if df_day.empty:
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, "Sem apontamentos para a data.", 0, 1)
        return pdf.output(dest='S').encode('latin-1', 'ignore')

    unique_types = sorted(df_day['Tipo'].unique())

    for m_type in unique_types:
        # --- CABEÇALHO DO TIPO (Ex: Digestão) ---
        pdf.set_fill_color(200, 200, 200) # Cinza Claro
        pdf.set_font('Arial', 'B', 12)
        # Tratamento simples para acentos (latin-1)
        type_str = m_type.encode('latin-1', 'ignore').decode('latin-1')
        pdf.cell(0, 10, type_str, 1, 1, 'L', fill=True)
        pdf.ln(2)

        df_type_subset = df_day[df_day['Tipo'] == m_type]
        unique_tags = sorted(df_type_subset['Tag'].unique())

        for tag in unique_tags:
            # --- DADOS DO EQUIPAMENTO ---
            # 1. Filtros e Calculos (Replicando logica da Tab 2)
            df_tag_day = df_type_subset[df_type_subset['Tag'] == tag]
            
            # Histórico para KPIs
            df_tag_hist = df_history[
                (df_history['equipment_tag'] == tag) & 
                (df_history['date'] <= pd.to_datetime(date_str).date())
            ]
            
            total_tubos = df_tag_hist['total_tubos'].max() if 'total_tubos' in df_tag_hist.columns else 0
            acumulado = df_tag_hist['quantity'].sum()
            pendente = total_tubos - acumulado
            perc = (acumulado / total_tubos * 100) if total_tubos > 0 else 0
            meta_turno = df_tag_day['Meta'].max()

            # 2. Desenhar Cartão do Equipamento no PDF
            pdf.set_font('Arial', 'B', 10)
            tag_str = tag.encode('latin-1', 'ignore').decode('latin-1')
            
            # Linha de Título do Equipamento
            pdf.set_text_color(37, 66, 230) # Azul parecido com o do painel
            pdf.cell(90, 8, f"{tag_str}", 0, 0)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Arial', '', 9)
            pdf.cell(0, 8, f"Meta Turno: {meta_turno:.0f}", 0, 1, 'R')
            
            # Linha de KPIs
            pdf.set_font('Arial', '', 8)
            kpi_text = f"Capacidade: {total_tubos:.0f}  |  Acumulado: {acumulado:.0f}  |  Pendente: {pendente:.0f}  |  Progresso: {perc:.1f}%"
            pdf.cell(0, 6, kpi_text, 'B', 1, 'L') # Borda embaixo
            pdf.ln(2)

            # 3. Tabela de Turnos
            # Header Tabela
            pdf.set_font('Arial', 'B', 8)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(30, 6, "Turno", 1, 0, 'C', True)
            pdf.cell(20, 6, "Realizado", 1, 0, 'C', True)
            pdf.cell(20, 6, "Gap", 1, 0, 'C', True)
            pdf.cell(25, 6, "Status", 1, 0, 'C', True)
            pdf.cell(0, 6, "Obs", 1, 1, 'L', True) # Resto da linha

            # Rows Tabela
            pdf.set_font('Arial', '', 8)
            for _, row in df_tag_day.iterrows():
                real = row['Realizado']
                gap = row['Desvio']
                # Traduzir Status para texto sem emoji
                status_txt = "OK" if gap >= 0 else "ATENCAO"
                obs = str(row['Observações'])[:50] # Corta obs muito longas
                
                # Tratamento acentos
                obs_clean = obs.encode('latin-1', 'ignore').decode('latin-1')
                turno_clean = str(row['Turno']).encode('latin-1', 'ignore').decode('latin-1')

                pdf.cell(30, 6, turno_clean, 1, 0, 'C')
                pdf.cell(20, 6, f"{real:.0f}", 1, 0, 'C')
                
                # Cor para Gap Negativo
                if gap < 0: pdf.set_text_color(200, 0, 0)
                pdf.cell(20, 6, f"{gap:+.0f}", 1, 0, 'C')
                pdf.set_text_color(0, 0, 0)
                
                pdf.cell(25, 6, status_txt, 1, 0, 'C')
                pdf.cell(0, 6, obs_clean, 1, 1, 'L')
            
            pdf.ln(5) # Espaço entre equipamentos

    # Retorna o binário do PDF
    return pdf.output(dest='S').encode('latin-1')