# Função auxiliar atualizada com Meta e %
def card_html(title, value, meta_val, perc_val, border_color="#2542e6", invert_logic=False):
    # Define cor do badge baseada no percentual
    if invert_logic: # Para pendências, quanto menor melhor
        badge_cls = "badge-green" if perc_val < 10 else "badge-red"
    else: # Para produção, quanto maior melhor
        badge_cls = "badge-green" if perc_val >= 90 else "badge-yellow" if perc_val >= 70 else "badge-red"
        
    return f"""
    <div class="kpi-card" style="border-left: 5px solid {border_color}">
        <div>
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
        </div>
        <div class="kpi-footer">
            <div class="kpi-meta">
                <span>Meta: <b>{meta_val}</b></span>
                <span class="kpi-badge {badge_cls}">{perc_val:.1f}%</span>
            </div>
        </div>
    </div>
    """
