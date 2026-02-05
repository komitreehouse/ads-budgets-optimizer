"""
Dual-axis chart component for Spend vs KPI visualization.
"""

import streamlit as st
import plotly.graph_objects as go
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np


def render_dual_axis_chart(
    data: List[Dict[str, Any]],
    x_key: str = "date",
    left_y_key: str = "spend",
    right_y_key: str = "roas",
    left_label: str = "Spend",
    right_label: str = "ROAS",
    show_rolling_avg: bool = False,
    rolling_window: int = 7,
    anomalies: Optional[List[Dict[str, Any]]] = None,
    learning_periods: Optional[List[Dict[str, Any]]] = None,
    height: int = 400
):
    """
    Render a dual-axis chart with spend on left and KPI on right.
    
    Args:
        data: List of data points with date, spend, and KPI values
        x_key: Key for x-axis (usually 'date')
        left_y_key: Key for left y-axis (usually 'spend' or 'cost')
        right_y_key: Key for right y-axis (usually 'roas', 'cpa', etc.)
        left_label: Label for left y-axis
        right_label: Label for right y-axis
        show_rolling_avg: Whether to show rolling average lines
        rolling_window: Window size for rolling average
        anomalies: List of anomaly markers with 'date' and 'type'
        learning_periods: List of learning periods with 'start' and 'end'
        height: Chart height
    """
    if not data:
        st.info("No data available")
        return
    
    df = pd.DataFrame(data)
    df[x_key] = pd.to_datetime(df[x_key])
    df = df.sort_values(x_key)
    
    # Create figure with secondary y-axis
    fig = go.Figure()
    
    # Add learning period backgrounds
    if learning_periods:
        for period in learning_periods:
            fig.add_vrect(
                x0=pd.to_datetime(period['start']),
                x1=pd.to_datetime(period['end']),
                fillcolor="rgba(124, 58, 237, 0.1)",
                layer="below",
                line_width=0,
                annotation_text="Learning Period" if period.get('label') is None else period['label'],
                annotation_position="top left"
            )
    
    # Add spend line (left axis)
    fig.add_trace(go.Scatter(
        x=df[x_key],
        y=df[left_y_key],
        name=left_label,
        line=dict(color='#7C3AED', width=2),
        yaxis='y'
    ))
    
    # Add KPI line (right axis)
    fig.add_trace(go.Scatter(
        x=df[x_key],
        y=df[right_y_key],
        name=right_label,
        line=dict(color='#22C55E', width=2),
        yaxis='y2'
    ))
    
    # Add rolling averages if requested
    if show_rolling_avg:
        df[f'{left_y_key}_rolling'] = df[left_y_key].rolling(window=rolling_window, center=True).mean()
        df[f'{right_y_key}_rolling'] = df[right_y_key].rolling(window=rolling_window, center=True).mean()
        
        fig.add_trace(go.Scatter(
            x=df[x_key],
            y=df[f'{left_y_key}_rolling'],
            name=f'{left_label} (Avg)',
            line=dict(color='#A78BFA', width=1.5, dash='dash'),
            yaxis='y'
        ))
        
        fig.add_trace(go.Scatter(
            x=df[x_key],
            y=df[f'{right_y_key}_rolling'],
            name=f'{right_label} (Avg)',
            line=dict(color='#86EFAC', width=1.5, dash='dash'),
            yaxis='y2'
        ))
    
    # Add anomaly markers
    if anomalies:
        for anomaly in anomalies:
            anomaly_date = pd.to_datetime(anomaly['date'])
            anomaly_type = anomaly.get('type', 'spike')
            
            # Find corresponding values
            closest_idx = (df[x_key] - anomaly_date).abs().idxmin()
            if closest_idx in df.index:
                if anomaly_type == 'spend_spike':
                    y_val = df.loc[closest_idx, left_y_key]
                    y_axis = 'y'
                else:  # kpi_drop
                    y_val = df.loc[closest_idx, right_y_key]
                    y_axis = 'y2'
                
                fig.add_trace(go.Scatter(
                    x=[anomaly_date],
                    y=[y_val],
                    mode='markers',
                    marker=dict(
                        symbol='triangle-down' if anomaly_type == 'kpi_drop' else 'triangle-up',
                        size=15,
                        color='#EF4444',
                        line=dict(width=2, color='white')
                    ),
                    name='Anomaly',
                    showlegend=False,
                    yaxis=y_axis
                ))
    
    # Update layout
    fig.update_layout(
        height=height,
        margin=dict(l=50, r=50, t=20, b=50),
        xaxis=dict(
            title="Date",
            showgrid=True,
            gridcolor='#E5E5E5'
        ),
        yaxis=dict(
            title=left_label,
            side='left',
            showgrid=True,
            gridcolor='#E5E5E5',
            titlefont=dict(color='#7C3AED'),
            tickfont=dict(color='#7C3AED')
        ),
        yaxis2=dict(
            title=right_label,
            side='right',
            overlaying='y',
            showgrid=False,
            titlefont=dict(color='#22C55E'),
            tickfont=dict(color='#22C55E')
        ),
        plot_bgcolor='white',
        hovermode='x unified',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)


def detect_anomalies(
    data: List[Dict[str, Any]],
    spend_key: str = "cost",
    kpi_key: str = "roas",
    threshold_std: float = 2.0
) -> List[Dict[str, Any]]:
    """
    Detect anomalies in spend and KPI data.
    
    Args:
        data: List of data points
        spend_key: Key for spend values
        kpi_key: Key for KPI values
        threshold_std: Standard deviation threshold for anomaly detection
    
    Returns:
        List of anomaly markers
    """
    if not data or len(data) < 3:
        return []
    
    df = pd.DataFrame(data)
    
    anomalies = []
    
    # Detect spend spikes
    if spend_key in df.columns:
        spend_values = df[spend_key].values
        spend_mean = np.mean(spend_values)
        spend_std = np.std(spend_values)
        
        for idx, row in df.iterrows():
            if abs(row[spend_key] - spend_mean) > threshold_std * spend_std:
                anomalies.append({
                    'date': row.get('date', ''),
                    'type': 'spend_spike',
                    'value': row[spend_key]
                })
    
    # Detect KPI drops
    if kpi_key in df.columns:
        kpi_values = df[kpi_key].values
        kpi_mean = np.mean(kpi_values)
        kpi_std = np.std(kpi_values)
        
        for idx, row in df.iterrows():
            if row[kpi_key] < kpi_mean - threshold_std * kpi_std:
                anomalies.append({
                    'date': row.get('date', ''),
                    'type': 'kpi_drop',
                    'value': row[kpi_key]
                })
    
    return anomalies
