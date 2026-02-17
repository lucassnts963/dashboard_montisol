from datetime import date, timedelta

def get_fiscal_period(selected_date):
    """
    Calcula o ciclo fiscal (16 do mês anterior até 15 do mês referência).
    Retorna: data_inicio, data_fim, label (ex: "JANEIRO/2026")
    """
    
    # Dicionário para garantir nomes em Português independente do servidor
    month_names = {
        1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL",
        5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO",
        9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"
    }

    # Lógica: Se for dia 16 ou mais, já pertence ao mês seguinte
    if selected_date.day >= 16:
        # Data de Início: Dia 16 do mês atual da data selecionada
        start_date = date(selected_date.year, selected_date.month, 16)
        
        # Data de Fim: Dia 15 do próximo mês
        # Truque: Vamos para o dia 28, somamos 4 dias (cai no próx mês) e setamos dia 15
        next_month = (selected_date.replace(day=28) + timedelta(days=4))
        end_date = date(next_month.year, next_month.month, 15)
        
    else:
        # Data de Fim: Dia 15 do mês atual da data selecionada
        end_date = date(selected_date.year, selected_date.month, 15)
        
        # Data de Início: Dia 16 do mês anterior
        # Truque: Vamos para o dia 1, subtraímos 1 dia (cai no mês anterior)
        last_month = (selected_date.replace(day=1) - timedelta(days=1))
        start_date = date(last_month.year, last_month.month, 16)

    # Monta o Label usando a data final como referência (Regra de Negócio)
    month_name = month_names[end_date.month]
    year = end_date.year
    month_label = f"{month_name}/{year}"

    return start_date, end_date, month_label