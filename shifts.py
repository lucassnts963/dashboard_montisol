import pandas as pd

def prepare_shift_dataframe(df_source, selected_date):
    df_day = df_source[df_source['date'] == selected_date].copy()
    
    if df_day.empty:
        return pd.DataFrame()

    if 'notes' not in df_day.columns:
        df_day['notes'] = ""

    # Agrupa por TAG e Turno
    df_result = df_day.groupby(['equipment_tag', 'shift_name']).agg({
        'quantity': 'sum',
        'meta_turno': 'first', # <--- ALTERADO DE target_per_shift PARA meta_turno
        'maintenance_type': 'first',
        'notes': lambda x: " | ".join([str(v) for v in x if v and str(v).strip() != ''])
    }).reset_index()

    df_result['quantity'] = pd.to_numeric(df_result['quantity']).fillna(0)
    df_result['meta_turno'] = pd.to_numeric(df_result['meta_turno']).fillna(0)

    # Renomeia Colunas (O 'meta_turno' vira 'Meta' para exibição)
    df_result.columns = ['Tag', 'Turno', 'Realizado', 'Meta', 'Tipo', 'Observações']

    df_result['Desvio'] = df_result['Realizado'] - df_result['Meta']
    
    df_result['Status'] = df_result.apply(
        lambda x: '🟢 OK' if x['Desvio'] >= 0 else '🔴 Abaixo', 
        axis=1
    )

    return df_result