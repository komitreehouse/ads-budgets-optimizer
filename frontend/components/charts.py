"""
Chart components.

Reusable chart components using Plotly.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from typing import List, Dict, Any


def render_sparkline(values: List[float], color: str = "#7C3AED", height: int = 40):
    """
    Render a small sparkline chart.
    
    Args:
        values: List of numeric values
        color: Line color
        height: Chart height in pixels
    """
    if not values:
        return
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        y=values,
        mode='lines',
        line=dict(color=color, width=2),
        fill='tozeroy',
        fillcolor=f'{color}20',
        hoverinfo='skip'
    ))
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=height,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        plot_bgcolor='transparent',
        paper_bgcolor='transparent',
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


def render_time_series_chart(
    data: List[Dict[str, Any]],
    x_key: str,
    y_key: str,
    title: str = None,
    color: str = "#7C3AED",
    height: int = 300
):
    """
    Render a time series line chart.
    
    Args:
        data: List of data points with x and y values
        x_key: Key for x-axis values (usually date)
        y_key: Key for y-axis values
        title: Chart title
        color: Line color
        height: Chart height
    """
    if not data:
        st.info("No data available")
        return
    
    x_values = [d[x_key] for d in data]
    y_values = [d[y_key] for d in data]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=x_values,
        y=y_values,
        mode='lines+markers',
        line=dict(color=color, width=2),
        marker=dict(size=6, color=color),
        hovertemplate=f"{y_key}: %{{y:.2f}}<br>%{{x}}<extra></extra>"
    ))
    
    fig.update_layout(
        title=title,
        margin=dict(l=40, r=20, t=40 if title else 20, b=40),
        height=height,
        xaxis=dict(
            showgrid=False,
            showline=True,
            linecolor='#E5E5E5'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='#E5E5E5',
            showline=False
        ),
        plot_bgcolor='white',
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_pie_chart(
    data: List[Dict[str, Any]],
    label_key: str,
    value_key: str,
    title: str = None,
    colors: List[str] = None,
    height: int = 300
):
    """
    Render a donut/pie chart.
    
    Args:
        data: List of data points with labels and values
        label_key: Key for labels
        value_key: Key for values
        title: Chart title
        colors: List of colors for segments
        height: Chart height
    """
    if not data:
        st.info("No data available")
        return
    
    labels = [d[label_key] for d in data]
    values = [d[value_key] for d in data]
    
    if colors is None:
        colors = ['#7C3AED', '#A78BFA', '#C4B5FD', '#DDD6FE', '#EDE9FE', '#F5F3FF']
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.5,
        marker_colors=colors[:len(labels)],
        textinfo='label+percent',
        textposition='outside',
        hovertemplate="%{label}: %{value:.1f}%<extra></extra>"
    )])
    
    fig.update_layout(
        title=title,
        margin=dict(l=20, r=20, t=40 if title else 20, b=20),
        height=height,
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_bar_chart(
    data: List[Dict[str, Any]],
    x_key: str,
    y_key: str,
    title: str = None,
    color: str = "#7C3AED",
    orientation: str = "v",
    height: int = 300
):
    """
    Render a bar chart.
    
    Args:
        data: List of data points
        x_key: Key for x-axis (categories)
        y_key: Key for y-axis (values)
        title: Chart title
        color: Bar color
        orientation: 'v' for vertical, 'h' for horizontal
        height: Chart height
    """
    if not data:
        st.info("No data available")
        return
    
    x_values = [d[x_key] for d in data]
    y_values = [d[y_key] for d in data]
    
    if orientation == 'h':
        fig = go.Figure(go.Bar(
            x=y_values,
            y=x_values,
            orientation='h',
            marker_color=color
        ))
    else:
        fig = go.Figure(go.Bar(
            x=x_values,
            y=y_values,
            marker_color=color
        ))
    
    fig.update_layout(
        title=title,
        margin=dict(l=40, r=20, t=40 if title else 20, b=40),
        height=height,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='#E5E5E5'),
        plot_bgcolor='white'
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_comparison_chart(
    data: List[Dict[str, Any]],
    category_key: str,
    metrics: List[str],
    title: str = None,
    height: int = 300
):
    """
    Render a grouped bar chart for comparing metrics across categories.
    
    Args:
        data: List of data points
        category_key: Key for categories (x-axis)
        metrics: List of metric keys to compare
        title: Chart title
        height: Chart height
    """
    if not data:
        st.info("No data available")
        return
    
    colors = ['#7C3AED', '#22C55E', '#F59E0B', '#EF4444', '#3B82F6']
    
    fig = go.Figure()
    
    for i, metric in enumerate(metrics):
        fig.add_trace(go.Bar(
            name=metric,
            x=[d[category_key] for d in data],
            y=[d.get(metric, 0) for d in data],
            marker_color=colors[i % len(colors)]
        ))
    
    fig.update_layout(
        title=title,
        barmode='group',
        margin=dict(l=40, r=20, t=40 if title else 20, b=40),
        height=height,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='#E5E5E5'),
        plot_bgcolor='white',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
