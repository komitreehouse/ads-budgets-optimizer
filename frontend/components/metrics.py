"""
Metric display components.

Reusable metric cards with trend indicators and sparklines.
"""

import streamlit as st


def render_metric_card(
    label: str,
    value: str,
    trend: float = None,
    trend_label: str = None,
    highlight: bool = False
):
    """
    Render a metric card with optional trend indicator.
    
    Args:
        label: Metric label
        value: Metric value (formatted string)
        trend: Trend percentage (positive = up, negative = down)
        trend_label: Label for trend (e.g., "vs yesterday")
        highlight: Whether to highlight the card (e.g., for pending items)
    """
    # Determine trend color and arrow
    if trend is not None:
        if trend > 0:
            trend_color = "#22C55E"
            trend_arrow = "▲"
        elif trend < 0:
            trend_color = "#EF4444"
            trend_arrow = "▼"
        else:
            trend_color = "#737373"
            trend_arrow = "—"
        
        trend_html = f"""
        <div style="display: flex; align-items: center; gap: 4px; margin-top: 4px;">
            <span style="color: {trend_color}; font-size: 0.875rem; font-weight: 500;">
                {trend_arrow} {abs(trend):.1f}%
            </span>
            {f'<span style="color: #737373; font-size: 0.75rem;">{trend_label}</span>' if trend_label else ''}
        </div>
        """
    else:
        trend_html = ""
    
    # Highlight border if needed
    border_style = "border-left: 4px solid #7C3AED;" if highlight else ""
    
    st.markdown(f"""
    <div class="metric-card" style="{border_style}">
        <p class="metric-label">{label}</p>
        <p class="metric-value">{value}</p>
        {trend_html}
    </div>
    """, unsafe_allow_html=True)


def render_metric_row(metrics: list):
    """
    Render a row of metric cards.
    
    Args:
        metrics: List of metric dicts with keys: label, value, trend, trend_label
    """
    cols = st.columns(len(metrics))
    
    for col, metric in zip(cols, metrics):
        with col:
            render_metric_card(
                label=metric['label'],
                value=metric['value'],
                trend=metric.get('trend'),
                trend_label=metric.get('trend_label'),
                highlight=metric.get('highlight', False)
            )


def render_status_badge(status: str):
    """
    Render a status badge.
    
    Args:
        status: Status string (active, paused, completed, error)
    """
    status_configs = {
        "active": {"color": "#22C55E", "bg": "#DCFCE7", "emoji": "🟢"},
        "paused": {"color": "#92400E", "bg": "#FEF3C7", "emoji": "🟡"},
        "completed": {"color": "#1E40AF", "bg": "#DBEAFE", "emoji": "✓"},
        "error": {"color": "#DC2626", "bg": "#FEE2E2", "emoji": "🔴"}
    }
    
    config = status_configs.get(status.lower(), status_configs["active"])
    
    return f"""
    <span style="
        background: {config['bg']};
        color: {config['color']};
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 500;
    ">
        {config['emoji']} {status.capitalize()}
    </span>
    """
