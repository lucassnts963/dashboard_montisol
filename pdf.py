from fpdf import FPDF
import pandas as pd
import os
import matplotlib.pyplot as plt
import tempfile
import re
import math

def create_pdf_report(df_day, df_history, date_str, df_impacts_history, df_impacts_today):
    
    # --- CORES ---
    COLOR_PRIMARY = (37, 66, 230)
    COLOR_SUCCESS = (46, 204, 113)
    COLOR_DANGER = (231, 76, 60)
    COLOR_BG_LIGHT = (245, 247, 250)
    COLOR_CYAN = '#00bcd4'

    class PDF(FPDF):
        def header(self):
            if os.path.exists("logo.png"):
                self.image("logo.png", 10, 8, 30)
            self.set_font('helvetica', 'B', 16)
            self.set_text_color(*COLOR_PRIMARY)
            self.cell(40) 
            self.cell(0, 10, 'Relatório Diário de Produção', 0, 1, 'L')
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font('helvetica', 'I', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    def md_to_html(text):
        if not text or str(text) == "-": return "-"
        text = str(text)
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
        text = text.replace('\n-', '<br/> - ').replace('\n*', '<br/> - ')
        return text

    def generate_bar_chart(x_data, y_data, title):
        fig, ax = plt.subplots(figsize=(7, 3.8))
        bars = ax.bar(x_data, y_data, color=COLOR_CYAN)
        
        # Título e Estilização
        ax.set_title(title, fontsize=11, fontweight='bold', pad=15)
        plt.xticks(rotation=20, ha='right', fontsize=9)
        
        # --- AJUSTES SOLICITADOS ---
        # 1. Adiciona rótulos de dados (labels) no topo das barras
        ax.bar_label(bars, fmt='%.1fh', padding=3, fontsize=9, fontweight='bold', color='#444444')
        
        # 2. Remove valores e marcações do eixo Y
        ax.get_yaxis().set_visible(False) 
        
        # Remove as bordas (spines) para um visual clean
        for spine in ['top', 'right', 'left']:
            ax.spines[spine].set_visible(False)
            
        plt.tight_layout()
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(temp_file.name, format='png', dpi=150)
        plt.close(fig)
        return temp_file.name

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    unique_types = sorted(df_day['Tipo'].unique())

    for m_type in unique_types:
        # Página de Título do Tipo
        pdf.add_page()
        pdf.set_y(100)
        pdf.set_font("helvetica", "B", 24)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 20, m_type.upper(), 0, 1, 'C')
        
        df_type_subset = df_day[df_day['Tipo'] == m_type]

        for tag in sorted(df_type_subset['Tag'].unique()):
            pdf.add_page()
            
            pdf.set_font("helvetica", "B", 14)
            pdf.set_text_color(*COLOR_PRIMARY)
            pdf.cell(0, 10, f"Equipamento: {tag}", "B", 1)
            pdf.ln(5)

            df_tag_day = df_type_subset[df_type_subset['Tag'] == tag]
            
            for _, row in df_tag_day.iterrows():
                # --- LÓGICA DE CARD DINÂMICO ---
                gap = row['Desvio']
                status_color = COLOR_SUCCESS if gap >= 0 else COLOR_DANGER
                status_text = "META BATIDA" if gap >= 0 else "ABAIXO DA META"
                obs_html = md_to_html(row['Observações'])

                # 1. Verificar quebra de página
                if pdf.get_y() > 220:
                    pdf.add_page()

                # Guardamos a posição inicial
                start_y = pdf.get_y()

                # PASSO A: Simular a altura (usando uma margem invisível ou calculando linhas)
                # No FPDF2, multi_cell pode retornar a altura, mas write_html não.
                # Vamos estimar a altura baseada no conteúdo:
                # Turno(8) + Stats(6) + Obs(estimado) + padding(5)
                # Uma forma precisa é usar 'split_only=True' se disponível, 
                # mas vamos desenhar o fundo primeiro com uma estimativa segura ou usar multi_cell
                
                # Vamos usar um bloco de texto invisível para medir a altura se necessário,
                # ou simplesmente desenhar o fundo após calcular o fim.
                
                # --- NOVA ESTRATÉGIA: Escrever conteúdo e capturar Y, depois desenhar atrás ---
                # Para o Streamlit/FPDF2, a forma mais segura de "desenhar atrás" é:
                # 1. Salvar start_y
                # 2. Escrever o texto real
                # 3. Pegar end_y
                # 4. Usar pdf.rect(...) ANTES de pular para o próximo card (ele ficará por cima se não tomarmos cuidado)
                
                # CORREÇÃO DEFINITIVA: 
                # Vamos desenhar o retângulo primeiro com uma altura estimada 
                # OU usar o método de renderização em buffer.
                
                # Vamos estimar: Cada 100 caracteres de Obs ~ 5mm de altura + Turno/Stats (15mm)
                est_height = 15 + (len(obs_html) / 90 * 5) + 10
                
                # Desenha o fundo PRIMEIRO
                pdf.set_fill_color(*COLOR_BG_LIGHT)
                # Não sabemos a altura exata ainda, então vamos escrever o texto 
                # e usar o truque de desenhar o retângulo na posição anterior.
                
                # --- Execução real ---
                # Escrevemos o texto e guardamos a posição final
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("helvetica", "B", 10)
                pdf.set_x(15)
                pdf.cell(50, 8, str(row['Turno']), 0, 0)
                
                pdf.set_font("helvetica", "B", 8)
                pdf.set_text_color(*status_color)
                pdf.cell(0, 8, status_text, 0, 1, 'R')
                
                pdf.set_x(15)
                pdf.set_font("helvetica", "", 9)
                pdf.set_text_color(80, 80, 80)
                pdf.cell(0, 6, f"Realizado: {row['Realizado']} / Meta: {row['Meta']} / Desvio: {gap:+}", 0, 1)
                
                pdf.set_x(15)
                pdf.set_text_color(50, 50, 50)
                pdf.write_html(f"<b>Obs:</b></br> {obs_html}")
                pdf.ln(5)
                
                end_y = pdf.get_y()
                total_h = end_y - start_y

                # AGORA desenhamos o retângulo na posição start_y, mas usando o parâmetro de estilo
                # que não sobrescreve o texto (ou movendo o desenho para uma camada inferior)
                # Como FPDF não tem camadas, o segredo é desenhar o RECT antes de escrever.
                # Vamos refazer a lógica:
                
                pdf.set_y(start_y) # Volta para o topo do card
                pdf.set_fill_color(*COLOR_BG_LIGHT)
                pdf.rect(10, start_y, 190, total_h, 'F') # Desenha fundo
                pdf.set_fill_color(*status_color)
                pdf.rect(10, start_y, 2, total_h, 'F') # Desenha barra
                
                # Re-escreve o texto POR CIMA (agora ele aparece)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("helvetica", "B", 10)
                pdf.set_x(15)
                pdf.cell(50, 8, str(row['Turno']), 0, 0)
                pdf.set_font("helvetica", "B", 8)
                pdf.set_text_color(*status_color)
                pdf.cell(0, 8, status_text, 0, 1, 'R')
                pdf.set_x(15)
                pdf.set_font("helvetica", "", 9)
                pdf.set_text_color(80, 80, 80)
                pdf.cell(0, 6, f"Realizado: {row['Realizado']} / Meta: {row['Meta']} / Desvio: {gap:+}", 0, 1)
                pdf.set_x(15)
                pdf.set_text_color(50, 50, 50)
                pdf.write_html(f"<b>Obs:</b><br/><br/> {obs_html} <br/><br/>")
                pdf.ln(5)
                
                pdf.set_y(end_y + 5) # Pula para o próximo

            # Gráficos e Resumo seguem a mesma lógica...
            if not df_impacts_history.empty:
                df_tag_hist = df_impacts_history[df_impacts_history['equipment_tag'] == tag]
                if not df_tag_hist.empty:
                    if pdf.get_y() > 180: pdf.add_page()
                    grp = df_tag_hist.groupby('Categoria')['horas'].sum()
                    img = generate_bar_chart(grp.index, grp.values, f"Historico de Impactos: {tag}")
                    pdf.image(img, x=25, w=160)
                    os.remove(img)

    # --- RESUMO GERAL ---
    if not df_impacts_today.empty:
        pdf.add_page()
        pdf.set_font("helvetica", "B", 16)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.cell(0, 15, "RESUMO GERAL DE IMPACTOS DO DIA", 0, 1, 'C')
        grp_geral = df_impacts_today.groupby('equipment_tag')['horas'].sum().sort_values(ascending=False)
        img_resumo = generate_bar_chart(grp_geral.index, grp_geral.values, "Horas Paradas por Equipamento")
        pdf.image(img_resumo, x=25, w=160)
        os.remove(img_resumo)
        pdf.ln(10)
        pdf.set_font("helvetica", "B", 12)
        pdf.set_text_color(0,0,0)
        pdf.cell(0, 10, "Detalhamento dos Eventos:", 0, 1)
        for _, row in df_impacts_today.iterrows():
            pdf.write_html(f"- <b>{row['equipment_tag']}</b> ({row['Categoria']}): {round(row['horas'], 2)}h")
            pdf.ln(2)

    return bytes(pdf.output())

def create_one_page_type_report(df_day, df_history, date_str, df_impacts_history, df_impacts_today):
    # --- PALETA DE CORES ---
    COLOR_PRIMARY = (37, 66, 230)
    COLOR_BG_ZEBRA_1 = (255, 255, 255) 
    COLOR_BG_ZEBRA_2 = (240, 244, 255) 
    COLOR_SUCCESS = (38, 186, 164)
    COLOR_DANGER = (239, 68, 68)
    
    class PDF(FPDF):
        def header(self):
            self.set_fill_color(*COLOR_PRIMARY)
            self.rect(0, 0, 420, 20, 'F')
            self.set_xy(15, 5)
            self.set_font('helvetica', 'B', 16)
            self.set_text_color(255, 255, 255)
            self.cell(0, 10, f"DASHBOARD EXECUTIVO A3 | TIPO DE ATIVO | REFERÊNCIA: {date_str}", 0, 1, 'L')

    def clean_unicode(text):
        if not text: return ""
        return str(text).replace('•', '-').replace('·', '-').replace('\u2022', '-')

    def md_to_html(text):
        if not text or str(text) == "-": return "-"
        text = clean_unicode(str(text))
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
        text = text.replace('\n-', '<br/> - ').replace('\n*', '<br/> - ')
        return text

    def generate_side_chart(df, x, y, labels_list, title, color):
        c_plt = tuple(c/255 for c in color) if isinstance(color, tuple) else color
        fig, ax = plt.subplots(figsize=(6, 4.5))
        bars = ax.bar(df[x], df[y], color=c_plt, alpha=0.8)
        ax.set_title(title, fontsize=14, fontweight='bold', pad=25)
        
        for bar, label in zip(bars, labels_list):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    label, ha='center', va='bottom', fontsize=10, fontweight='bold')

        ax.get_yaxis().set_visible(False)
        for spine in ['top', 'right', 'left']: ax.spines[spine].set_visible(False)
        plt.xticks(rotation=15, ha='right')
        plt.tight_layout()
        
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(tmp.name, format='png', dpi=150, transparent=True)
        plt.close(fig)
        return tmp.name

    pdf = PDF(orientation='L', unit='mm', format='A3')
    
    for m_type in sorted(df_day['Tipo'].unique()):
        pdf.add_page()
        df_type = df_day[df_day['Tipo'] == m_type]
        
        # --- 1. ÁREA DE SCORECARDS (KPIs DE TOPO) ---
        real_total = df_type['Realizado'].sum()
        meta_total = df_type['Meta'].sum()
        perc_total = (real_total / meta_total * 100) if meta_total > 0 else 0
        hrs_impacto = df_impacts_today[df_impacts_today['Tipo'] == m_type]['horas'].sum()

        kpi_w = 95
        positions = [15, 115, 215, 315]
        kpis = [
            ("PRODUÇÃO TOTAL", f"{real_total:,.0f}"),
            ("META GLOBAL", f"{meta_total:,.0f}"),
            ("EFICIÊNCIA", f"{perc_total:.1f}%"),
            ("TOTAL PARADAS", f"{hrs_impacto:.1f}h")
        ]
        
        for i, (label, val) in enumerate(kpis):
            x_pos = positions[i]
            pdf.set_draw_color(220, 220, 220)
            pdf.set_fill_color(255, 255, 255)
            pdf.rect(x_pos, 30, kpi_w, 20, 'FD')
            
            pdf.set_xy(x_pos, 32)
            pdf.set_font("helvetica", "B", 9)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(kpi_w, 5, label, 0, 1, 'C')
            
            pdf.set_font("helvetica", "B", 14)
            # Cor condicional: eficiência azul/verde, paradas vermelho
            color_text = COLOR_PRIMARY if i < 2 else (COLOR_SUCCESS if i == 2 else COLOR_DANGER)
            pdf.set_text_color(*color_text)
            pdf.set_x(x_pos)
            pdf.cell(kpi_w, 8, val, 0, 1, 'C')

        # --- 2. LADO ESQUERDO: GRÁFICOS ---
        df_p = df_type.groupby('Tag')['Realizado'].sum().reset_index()
        custom_labels = []
        for tag in df_p['Tag']:
            hist = df_history[df_history['equipment_tag'] == tag]
            total = hist['total_tubos'].max() if 'total_tubos' in hist.columns else 1
            acum = hist['quantity'].sum()
            p = (acum / total * 100) if total > 0 else 0
            val_r = df_p[df_p['Tag'] == tag]['Realizado'].values[0]
            custom_labels.append(f"{val_r:,.0f}\n({p:.1f}%)")

        img_prod = generate_side_chart(df_p, 'Tag', 'Realizado', custom_labels, "Produção vs Avanço Acumulado", COLOR_PRIMARY)
        pdf.image(img_prod, x=10, y=60, w=130)
        
        df_i = df_impacts_today[df_impacts_today['Tipo'] == m_type].groupby('equipment_tag')['horas'].sum().reset_index()
        if not df_i.empty:
            labels_i = [f"{h:.1f}h" for h in df_i['horas']]
            img_imp = generate_side_chart(df_i, 'equipment_tag', 'horas', labels_i, "Impactos do Dia (Horas)", COLOR_DANGER)
            pdf.image(img_imp, x=10, y=155, w=130)
        
        # --- 3. LADO DIREITO: TABELA E RECOMENDAÇÕES ---
        pdf.set_xy(145, 60)
        pdf.set_font("helvetica", "B", 12)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.cell(0, 10, f"DETALHAMENTO OPERACIONAL - {m_type.upper()}", 0, 1, 'L')
        
        headers = [("TAG", 40), ("TURNO (AMPLIADO)", 65), ("REAL", 35), ("META", 35), ("DESVIO", 35)]
        pdf.set_x(145)
        pdf.set_fill_color(*COLOR_PRIMARY)
        pdf.set_text_color(255, 255, 255)
        for h, w in headers: pdf.cell(w, 10, h, 1, 0, 'C', fill=True)
        pdf.ln()

        pdf.set_font("helvetica", "", 10)
        unique_tags = df_type['Tag'].unique()
        tag_colors = {tag: (COLOR_BG_ZEBRA_1 if i % 2 == 0 else COLOR_BG_ZEBRA_2) for i, tag in enumerate(unique_tags)}

        for _, row in df_type.iterrows():
            pdf.set_x(145)
            pdf.set_fill_color(*tag_colors[row['Tag']])
            pdf.set_text_color(0, 0, 0)
            
            pdf.cell(40, 9, str(row['Tag']), 1, 0, 'C', fill=True)
            pdf.cell(65, 9, str(row['Turno']), 1, 0, 'C', fill=True)
            pdf.cell(35, 9, f"{row['Realizado']:,.0f}", 1, 0, 'C', fill=True)
            pdf.cell(35, 9, f"{row['Meta']:,.0f}", 1, 0, 'C', fill=True)
            
            d = row['Desvio']
            pdf.set_text_color(*(COLOR_DANGER if d < 0 else COLOR_SUCCESS))
            pdf.cell(35, 9, f"{d:+.0f}", 1, 1, 'C', fill=True)

        # --- 4. ANÁLISE E RECOMENDAÇÕES (INTEGRADO NO GRID) ---
        pdf.set_y(pdf.get_y() + 8)
        pdf.set_x(145)
        pdf.set_font("helvetica", "B", 11)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.cell(0, 8, "ANÁLISE DE OCORRÊNCIAS E RECOMENDAÇÕES", 0, 1, 'L')
        
        pdf.set_x(145)
        pdf.set_font("helvetica", "I", 10)
        pdf.set_text_color(50, 50, 50)
        
        obs_list = df_type[df_type['Observações'] != '-']['Observações'].unique()
        txt_obs = "<br/>".join([f"- {clean_unicode(o)}" for o in obs_list]) if len(obs_list) > 0 else "Nenhuma intercorrência crítica registrada."
        
        # O A3 permite uma multi_cell larga sem estourar
        pdf.write_html(f"<div style='margin-left: 145mm;'>{txt_obs}</div>")

        os.remove(img_prod)
        if not df_i.empty: os.remove(img_imp)

    return bytes(pdf.output())
    
    for m_type in sorted(df_day['Tipo'].unique()):
        pdf.add_page()
        df_type = df_day[df_day['Tipo'] == m_type]
        
        # --- LADO ESQUERDO: GRÁFICOS ---
        df_p = df_type.groupby('Tag')['Realizado'].sum().reset_index()
        custom_labels = []
        for tag in df_p['Tag']:
            hist = df_history[df_history['equipment_tag'] == tag]
            total = hist['total_tubos'].max() if 'total_tubos' in hist.columns else 1
            acum = hist['quantity'].sum()
            perc = (acum / total * 100) if total > 0 else 0
            val_real = df_p[df_p['Tag'] == tag]['Realizado'].values[0]
            custom_labels.append(f"{val_real:,.0f}\n({perc:.1f}%)")

        img_prod = generate_side_chart(df_p, 'Tag', 'Realizado', custom_labels, f"Produção e Avanço - {m_type}", COLOR_PRIMARY)
        pdf.image(img_prod, x=10, y=30, w=130)
        
        df_i = df_impacts_today[df_impacts_today['Tipo'] == m_type].groupby('equipment_tag')['horas'].sum().reset_index()
        if not df_i.empty:
            labels_i = [f"{h:.1f}h" for h in df_i['horas']]
            img_imp = generate_side_chart(df_i, 'equipment_tag', 'horas', labels_i, "Impactos por TAG (Horas)", COLOR_DANGER)
            pdf.image(img_imp, x=10, y=140, w=130)
        
        # --- LADO DIREITO: TABELA ---
        pdf.set_xy(145, 30)
        pdf.set_font("helvetica", "B", 12)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.cell(0, 10, "DETALHAMENTO OPERACIONAL", 0, 1, 'L')
        
        headers = [("TAG", 40), ("TURNO", 65), ("REAL", 35), ("META", 35), ("DESVIO", 35)]
        pdf.set_x(145)
        pdf.set_fill_color(*COLOR_PRIMARY)
        pdf.set_text_color(255, 255, 255)
        for h, w in headers:
            pdf.cell(w, 10, h, 1, 0, 'C', fill=True)
        pdf.ln()

        pdf.set_font("helvetica", "", 10)
        unique_tags_page = df_type['Tag'].unique()
        tag_colors = {tag: (COLOR_BG_ZEBRA_1 if i % 2 == 0 else COLOR_BG_ZEBRA_2) for i, tag in enumerate(unique_tags_page)}

        for _, row in df_type.iterrows():
            pdf.set_x(145)
            pdf.set_fill_color(*tag_colors[row['Tag']])
            pdf.set_text_color(0, 0, 0)
            
            pdf.cell(40, 9, str(row['Tag']), 1, 0, 'C', fill=True)
            pdf.cell(65, 9, str(row['Turno']), 1, 0, 'C', fill=True)
            pdf.cell(35, 9, f"{row['Realizado']:,.0f}", 1, 0, 'C', fill=True)
            pdf.cell(35, 9, f"{row['Meta']:,.0f}", 1, 0, 'C', fill=True)
            
            d = row['Desvio']
            pdf.set_text_color(*(COLOR_DANGER if d < 0 else COLOR_SUCCESS))
            pdf.cell(35, 9, f"{d:+.0f}", 1, 1, 'C', fill=True)

        # --- ANÁLISE E RECOMENDAÇÕES (Corrigido para evitar caracteres Unicode) ---
        pdf.set_y(pdf.get_y() + 10)
        pdf.set_x(145)
        pdf.set_font("helvetica", "B", 11)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.cell(0, 8, "ANÁLISE DE OCORRÊNCIAS E RECOMENDAÇÕES", 0, 1, 'L')
        
        pdf.set_x(145)
        pdf.set_font("helvetica", "I", 10)
        pdf.set_text_color(50, 50, 50)
        
        obs_list = df_type[df_type['Observações'] != '-']['Observações'].unique()
        if len(obs_list) > 0:
            # Substituímos explicitamente o caractere problemático por um hífen aqui
            txt_obs = "<br/>".join([f"- {clean_unicode(o)}" for o in obs_list])
        else:
            txt_obs = "Nenhuma intercorrência crítica registrada no período."
            
        pdf.write_html(txt_obs)

        os.remove(img_prod)
        if not df_i.empty: os.remove(img_imp)

    return bytes(pdf.output())

def create_landscape_presentation(df_day, df_history, date_str, df_impacts_history, df_impacts_today):
    
    # --- CORES ---
    COLOR_PRIMARY = (37, 66, 230)
    COLOR_SUCCESS = (46, 204, 113)
    COLOR_DANGER = (231, 76, 60)
    COLOR_BG_LIGHT = (242, 244, 247)
    COLOR_CYAN = '#00bcd4'

    # Inicializa em modo Paisagem ('L'), unidade 'mm', formato 'A4'
    class PDF(FPDF):
        def header(self):
            if os.path.exists("logo.png"):
                self.image("logo.png", 10, 8, 25)
            self.set_font('helvetica', 'B', 14)
            self.set_text_color(*COLOR_PRIMARY)
            self.cell(30) 
            self.cell(0, 10, 'Apresentacao de Producao Diaria', 0, 0, 'L')
            self.set_font('helvetica', '', 10)
            self.set_text_color(120, 120, 120)
            self.cell(0, 10, f'Data: {date_str}  ', 0, 1, 'R')
            self.set_draw_color(*COLOR_PRIMARY)
            self.line(10, 22, 287, 22) # Linha horizontal mais longa (Paisagem)
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font('helvetica', 'I', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f'Slide {self.page_no()}', 0, 0, 'C')

    def md_to_html(text):
        if not text or str(text) == "-": return "-"
        text = str(text)
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
        text = text.replace('\n-', '<br/> - ')  # Hífen simples
        text = text.replace('\n*', '<br/> > ')  # Marcador de seta
        return text

    def generate_bar_chart(x_data, y_data, title, width=9, height=4.5):
        fig, ax = plt.subplots(figsize=(width, height))
        ax.bar(x_data, y_data, color=COLOR_CYAN)
        ax.set_title(title, fontsize=12, fontweight='bold', pad=15)
        plt.xticks(rotation=20, ha='right', fontsize=9)
        plt.tight_layout()
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(temp_file.name, format='png', dpi=180) # DPI maior para telas
        plt.close(fig)
        return temp_file.name

    pdf = PDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)

    unique_types = sorted(df_day['Tipo'].unique())

    for m_type in unique_types:
        # Slide de Transição de Categoria
        pdf.add_page()
        pdf.set_y(80)
        pdf.set_font("helvetica", "B", 32)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 30, m_type.upper(), 0, 1, 'C')
        pdf.set_draw_color(*COLOR_PRIMARY)
        pdf.line(100, 115, 197, 115)
        
        df_type_subset = df_day[df_day['Tipo'] == m_type]

        for tag in sorted(df_type_subset['Tag'].unique()):
            pdf.add_page()
            
            # Título do Equipamento
            pdf.set_font("helvetica", "B", 18)
            pdf.set_text_color(*COLOR_PRIMARY)
            pdf.cell(0, 12, f"Equipamento: {tag}", 0, 1, 'L')
            pdf.ln(2)

            df_tag_day = df_type_subset[df_type_subset['Tag'] == tag]
            
            for _, row in df_tag_day.iterrows():
                gap = row['Desvio']
                status_color = COLOR_SUCCESS if gap >= 0 else COLOR_DANGER
                obs_html = md_to_html(row['Observações'])

                if pdf.get_y() > 170: pdf.add_page()

                start_y = pdf.get_y()
                
                # --- PASSO 1: Medir altura ---
                pdf.set_x(18)
                pdf.set_font("helvetica", "B", 11)
                pdf.cell(0, 8, f"Turno: {row['Turno']}", 0, 1)
                pdf.set_font("helvetica", "", 10)
                pdf.write_html(f"<b>Realizado:</b> {row['Realizado']} | <b>Meta:</b> {row['Meta']} | <b>Desvio:</b> {gap:+}<br/>")
                pdf.write_html(f"<b>Obs:</b> {obs_html}")
                pdf.ln(4)
                
                end_y = pdf.get_y()
                total_h = end_y - start_y

                # --- PASSO 2: Desenhar Fundo e Re-escrever ---
                pdf.set_y(start_y)
                pdf.set_fill_color(*COLOR_BG_LIGHT)
                pdf.rect(10, start_y, 277, total_h, 'F') # Largura total paisagem
                pdf.set_fill_color(*status_color)
                pdf.rect(10, start_y, 3, total_h, 'F') # Barra lateral mais grossa
                
                # Texto por cima
                pdf.set_x(18)
                pdf.set_font("helvetica", "B", 11)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(0, 8, f"Turno: {row['Turno']}", 0, 1)
                pdf.set_font("helvetica", "", 10)
                pdf.set_text_color(60, 60, 60)
                pdf.write_html(f"Realizado: {row['Realizado']} | Meta: {row['Meta']} | Desvio: {gap:+}<br/>")
                pdf.set_text_color(40, 40, 40)
                pdf.write_html(f"<b>Obs:</b> {obs_html}")
                
                pdf.set_y(end_y + 6)

            # Gráfico de Histórico (Aumentado para modo Paisagem)
            if not df_impacts_history.empty:
                df_tag_hist = df_impacts_history[df_impacts_history['equipment_tag'] == tag]
                if not df_tag_hist.empty:
                    pdf.add_page() # Gráfico em slide separado para maior impacto
                    grp = df_tag_hist.groupby('Categoria')['horas'].sum()
                    img = generate_bar_chart(grp.index, grp.values, f"Historico Acumulado de Paradas - {tag}", width=11)
                    pdf.image(img, x=20, y=40, w=250)
                    os.remove(img)

    # --- SLIDE DE RESUMO GERAL ---
    if not df_impacts_today.empty:
        pdf.add_page()
        pdf.set_font("helvetica", "B", 20)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.cell(0, 20, "RESUMO GERAL DE IMPACTOS - HOJE", 0, 1, 'C')
        
        grp_geral = df_impacts_today.groupby('equipment_tag')['horas'].sum().sort_values(ascending=False)
        img_resumo = generate_bar_chart(grp_geral.index, grp_geral.values, "Horas Perdidas por Equipamento (Geral)", width=11)
        pdf.image(img_resumo, x=20, y=45, w=250)
        os.remove(img_resumo)

        # Slide de Detalhes Finais
        pdf.add_page()
        pdf.set_font("helvetica", "B", 16)
        pdf.cell(0, 15, "Detalhamento de Eventos", "B", 1)
        pdf.ln(5)
        pdf.set_font("helvetica", "", 11)
        for _, row in df_impacts_today.iterrows():
            pdf.write_html(f"• <b>{row['equipment_tag']}</b> - {row['Categoria']}: {row['horas']}h | {row.get('description', '-')}")
            pdf.ln(5)

    return bytes(pdf.output())


def create_one_page_a3_report(df_day, df_history, date_str, df_impacts_history, df_impacts_today):
    # --- 1. CONFIGURAÇÕES E METAS ---
    FIXED_GOALS = {
        "DESOBSTRUÇÃO": 26,
        "DESOBSTRUÇÃO - PRECIPITAÇÃO": 54,
        "DESOBSTRUÇÃO - AQUECEDOR DE POLPA": 8
    }
    
    RGB_PRIMARY = (37, 66, 230)
    RGB_SUCCESS = (38, 186, 164)
    RGB_DANGER = (239, 68, 68)
    RGB_BG_ZEBRA_1 = (255, 255, 255)
    RGB_BG_ZEBRA_2 = (242, 245, 252)
    IMPACT_COLORS = ['#FF5733', '#33FF57', '#3357FF', '#F333FF', '#CCAC00', '#33FFF3']

    # --- 2. TRATAMENTO DE DADOS ---
    df_day = df_day.copy()
    cols_data = ['maint_start_date', 'maint_due_date', 'maint_real_due_date']
    for col in cols_data:
        if col in df_day.columns:
            temp_dates = pd.to_datetime(df_day[col], errors='coerce', dayfirst=True)
            df_day[col] = temp_dates.apply(lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x) else "-")

    class PDF(FPDF):
        def header(self):
            # Banner Azul
            self.set_fill_color(*RGB_PRIMARY)
            self.rect(0, 0, 420, 22, 'F')
            
            # Título Esquerdo
            self.set_xy(15, 6)
            self.set_font('helvetica', 'B', 18)
            self.set_text_color(255, 255, 255)
            self.cell(200, 10, f"DASHBOARD OPERACIONAL A3 | {date_str}", 0, 0, 'L')

        def footer(self):
            self.set_y(-10)
            self.set_font('helvetica', 'I', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 5, f"Pagina {self.page_no()}", 0, 0, 'C')

    def clean_unicode(text):
        if not text: return ""
        return str(text).replace('•', '-').replace('·', '-').replace('\u2022', '-')

    def generate_mini_bar(tag, df_imp, categories):
        fig, ax = plt.subplots(figsize=(4.2, 1.2))
        data = df_imp[df_imp['equipment_tag'] == tag]
        if not data.empty:
            grp = data.groupby('Categoria')['horas'].sum().reindex(categories, fill_value=0)
            bars = ax.bar(categories, grp.values, color=IMPACT_COLORS[:len(categories)])
            ax.bar_label(bars, fmt='%.1fh', padding=2, fontsize=9, fontweight='bold')
        
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)
        for s in ax.spines.values(): s.set_visible(False)
        plt.tight_layout()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(tmp.name, transparent=True, dpi=100)
        plt.close(fig)
        return tmp.name

    pdf = PDF(orientation='L', unit='mm', format='A3')
    all_categories = sorted(df_impacts_today['Categoria'].unique())[:6]

    try:
        dt_ref = pd.to_datetime(date_str, format="%d/%m/%Y").date()
    except:
        dt_ref = pd.to_datetime(date_str).date()

    for m_type in sorted(df_day['Tipo'].unique()):
        pdf.add_page()
        df_type = df_day[df_day['Tipo'] == m_type]
        base_goal = FIXED_GOALS.get(m_type, 0)
        
        # --- 3. LEGENDA NO CABEÇALHO (LADO DIREITO) ---
        pdf.set_xy(220, 5)
        pdf.set_font("helvetica", "B", 7)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(30, 5, "LEGENDA IMPACTOS:", 0, 0, 'L')
        
        for i, cat in enumerate(all_categories):
            h = IMPACT_COLORS[i].lstrip('#')
            r, g, b = tuple(int(h[j:j+2], 16) for j in (0, 2, 4))
            pdf.set_fill_color(r, g, b)
            pdf.rect(pdf.get_x(), 6.5, 3, 3, 'F')
            pdf.set_x(pdf.get_x() + 4)
            pdf.cell(28, 5, cat[:15], 0, 0, 'L')

        # --- 4. SCORECARDS (KPIs) ---
        total_real_dia = df_type['Realizado'].sum()
        total_impacto_dia = df_impacts_today[df_impacts_today['Tipo'] == m_type]['horas'].sum()
        total_meta_dia = df_type['Meta'].sum()

        kpi_vals = [
            ("META DIA", f"{total_meta_dia:,.0f}"),
            ("REALIZADO TOTAL", f"{total_real_dia:,.0f}"),
            ("DESVIO DO DIA", f"{(total_real_dia - total_meta_dia):+,.0f}"),
            ("TOTAL HORAS PARADAS", f"{total_impacto_dia:.1f}h")
        ]
        
        for i, (lab, val) in enumerate(kpi_vals):
            x_kpi = 15 + (i * 100)
            pdf.set_xy(x_kpi, 28)
            pdf.set_draw_color(200, 200, 200)
            pdf.set_fill_color(255, 255, 255)
            pdf.rect(x_kpi, 28, 90, 18, 'DF')
            
            pdf.set_font("helvetica", "B", 10)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(90, 8, lab, 0, 1, 'C')
            
            pdf.set_font("helvetica", "B", 15)
            color_val = RGB_PRIMARY if i < 3 else RGB_DANGER
            if i == 2 and (total_real_dia - total_meta_dia) >= 0: color_val = RGB_SUCCESS
            pdf.set_text_color(*color_val)
            pdf.set_x(x_kpi)
            pdf.cell(90, 6, val, 0, 1, 'C')
        
        # --- 5. CABEÇALHOS DAS COLUNAS (ÚNICO POR PÁGINA) ---
        pdf.set_y(50)
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(*RGB_PRIMARY)
        
        pdf.set_xy(15, 50)
        pdf.cell(85, 5, "INFORMAÇÕES GERAIS", 0, 0, 'L')
        
        pdf.set_xy(105, 50)
        pdf.cell(85, 5, "PRODUÇÃO", 0, 0, 'L')
        
        pdf.set_xy(200, 50)
        pdf.cell(110, 5, "DISTRIBUIÇÃO DE IMPACTOS", 0, 0, 'L')
        
        pdf.set_xy(320, 50)
        pdf.cell(85, 5, "OBSERVAÇÕES", 0, 0, 'L')
        
        # --- 6. GRADE DE ATIVOS ---
        pdf.set_y(56)
        tags = sorted(df_type['Tag'].unique())[:6]
        
        for idx, tag in enumerate(tags):
            df_tag = df_type[df_type['Tag'] == tag]
            
            df_tag_hist = df_history[(df_history['equipment_tag'] == tag) & (df_history['date'] <= dt_ref)]
            total_tubos = df_tag_hist['total_tubos'].max() if 'total_tubos' in df_tag_hist.columns else 0
            acumulado_total = df_tag_hist['quantity'].sum() if not df_tag_hist.empty else 0
            pendentes = total_tubos - acumulado_total
            
            start_y = pdf.get_y()
            # Altura do cartão reduzida pois os títulos saíram
            card_height = 36 
            
            pdf.set_fill_color(*(RGB_BG_ZEBRA_1 if idx % 2 == 0 else RGB_BG_ZEBRA_2))
            pdf.rect(10, start_y, 400, card_height, 'F')
            
            # --- BLOCO 1: INFORMAÇÕES GERAIS (X=15) ---
            pdf.set_xy(15, start_y + 3)
            pdf.set_font("helvetica", "B", 11)
            pdf.set_text_color(*RGB_PRIMARY)
            pdf.cell(85, 5, f"{tag}", 0, 1)
            
            pdf.set_font("helvetica", "", 8)
            pdf.set_text_color(80, 80, 80)
            
            y_info = start_y + 8
            linha_h = 4.5
            
            pdf.set_xy(15, y_info)
            pdf.cell(85, linha_h, f"Inicio LB: {df_tag['maint_start_date'].iloc[0]}", 0, 1)
            
            pdf.set_x(15)
            pdf.cell(85, linha_h, f"Término LB: {df_tag['maint_due_date'].iloc[0]}", 0, 1)
            
            pdf.set_x(15)
            pdf.cell(85, linha_h, f"Término Real: {df_tag['maint_real_due_date'].iloc[0]}", 0, 1)
            
            pdf.set_x(15)
            pdf.cell(85, linha_h, f"Qtd. Total de Tubos: {total_tubos:.0f}", 0, 1)
            
            pdf.set_x(15)
            pdf.cell(85, linha_h, f"Realizado Acumulado: {acumulado_total:.0f}", 0, 1)

            pdf.set_x(15)
            pdf.cell(85, linha_h, f"Pendentes: {pendentes:.0f}", 0, 1)

            # --- BLOCO 2: PRODUÇÃO (X=105) ---
            pdf.set_xy(105, start_y + 3)
            pdf.set_font("helvetica", "B", 8)
            pdf.set_fill_color(*RGB_PRIMARY)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(45, 5, "TURNO", 1, 0, 'C', fill=True)
            pdf.cell(20, 5, "REAL", 1, 0, 'C', fill=True)
            pdf.cell(20, 5, "DESVIO", 1, 1, 'C', fill=True)
            
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("helvetica", "", 8)
            
            for _, row in df_tag.head(4).iterrows():
                pdf.set_x(105)
                pdf.cell(45, 6, str(row['Turno']), 1, 0, 'C')
                pdf.cell(20, 6, f"{row['Realizado']:.0f}", 1, 0, 'C')
                d = row['Realizado'] - base_goal
                pdf.set_text_color(*(RGB_DANGER if d < 0 else RGB_SUCCESS))
                pdf.cell(20, 6, f"{d:+.0f}", 1, 1, 'C')
                pdf.set_text_color(0, 0, 0)

            # --- BLOCO 3: GRÁFICO DE IMPACTOS (X=200) ---
            img_bar = generate_mini_bar(tag, df_impacts_today, all_categories)
            pdf.image(img_bar, x=198, y=start_y + 3, w=110)
            os.remove(img_bar)

            # --- BLOCO 4: OBSERVAÇÕES (X=320) ---
            pdf.set_xy(320, start_y + 3)
            pdf.set_font("helvetica", "I", 8)
            pdf.set_text_color(60, 60, 60)
            obs = clean_unicode(str(df_tag['Observações'].iloc[0]))[:250]
            
            pdf.multi_cell(85, 4.5, obs if obs != "-" else "Sem intercorrências registradas.")
            
            pdf.set_y(start_y + card_height + 1)

    return bytes(pdf.output())