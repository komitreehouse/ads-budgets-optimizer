"""
Campaign Detail Page

Shows detailed metrics, allocation breakdown, arm performance,
and explanations for a specific campaign.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pandas as pd
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from frontend.services.data_service import DataService
from frontend.components.metrics import render_metric_card


def render(campaign_id: int):
    """Render the campaign detail page."""
    data_service = DataService()
    
    # Back button
    if st.button("← Back to Campaigns"):
        st.session_state.selected_campaign_id = None
        st.session_state.current_page = "campaigns"
        st.rerun()
    
    # Fetch campaign data
    campaign = data_service.get_campaign(campaign_id)
    
    if not campaign:
        st.error("Campaign not found")
        return
    
    # Header
    col1, col2 = st.columns([3, 1])
    
    with col1:
        status_emoji = "🟢" if campaign['status'] == 'active' else "🟡"
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 16px;">
            <h1 style="margin: 0;">{campaign['name']}</h1>
            <span class="status-{'active' if campaign['status'] == 'active' else 'paused'}">
                {status_emoji} {campaign['status'].capitalize()}
            </span>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        col_a, col_b = st.columns(2)
        with col_a:
            if campaign['status'] == 'active':
                if st.button("⏸ Pause", use_container_width=True):
                    data_service.pause_campaign(campaign_id)
                    st.rerun()
            else:
                if st.button("▶ Resume", use_container_width=True):
                    data_service.resume_campaign(campaign_id)
                    st.rerun()
        with col_b:
            is_pinned = campaign_id in [c['id'] for c in st.session_state.get('pinned_campaigns', [])]
            if st.button("📌 Unpin" if is_pinned else "📌 Pin", use_container_width=True):
                toggle_pin(campaign)
                st.rerun()
    
    # Time range selector
    st.markdown("<br>", unsafe_allow_html=True)
    time_options = ["7D", "30D", "3M", "Custom"]
    selected_time = st.radio(
        "Time Range",
        time_options,
        horizontal=True,
        index=0,
        label_visibility="collapsed"
    )
    
    st.divider()
    
    # Metrics Overview
    st.markdown("### Performance Metrics")
    metrics = data_service.get_campaign_metrics(campaign_id, time_range=selected_time)
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        render_metric_card("ROAS", f"{metrics['roas']:.2f}", metrics.get('roas_trend'))
    with col2:
        render_metric_card("Spend", f"${metrics['spend']:,.2f}", metrics.get('spend_trend'))
    with col3:
        render_metric_card("Revenue", f"${metrics['revenue']:,.2f}", metrics.get('revenue_trend'))
    with col4:
        render_metric_card("Conversions", f"{metrics['conversions']:,}", metrics.get('conv_trend'))
    with col5:
        render_metric_card("CTR", f"{metrics['ctr']:.2%}", metrics.get('ctr_trend'))
    with col6:
        render_metric_card("CVR", f"{metrics['cvr']:.2%}", metrics.get('cvr_trend'))
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Performance Chart and Allocation side by side
    chart_col, alloc_col = st.columns([2, 1])
    
    with chart_col:
        st.markdown("### Performance Over Time")
        
        # Metric selector for chart
        chart_metric = st.selectbox(
            "Metric",
            ["ROAS", "Spend", "Revenue", "Conversions"],
            index=0,
            label_visibility="collapsed"
        )
        
        # Get time series data
        time_series = data_service.get_performance_time_series(campaign_id, selected_time)
        
        if time_series:
            df = pd.DataFrame(time_series)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df['date'],
                y=df[chart_metric.lower()],
                mode='lines+markers',
                line=dict(color='#7C3AED', width=2),
                marker=dict(size=6),
                hovertemplate=f"{chart_metric}: %{{y:.2f}}<br>%{{x}}<extra></extra>"
            ))
            
            fig.update_layout(
                margin=dict(l=0, r=0, t=20, b=0),
                height=300,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='#E5E5E5'),
                plot_bgcolor='white',
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No performance data available for this time range")
    
    with alloc_col:
        st.markdown("### Budget Allocation")
        
        allocation = data_service.get_allocation(campaign_id)
        
        if allocation:
            # Pie chart
            fig = go.Figure(data=[go.Pie(
                labels=[a['name'] for a in allocation],
                values=[a['allocation'] * 100 for a in allocation],
                hole=0.5,
                marker_colors=['#7C3AED', '#A78BFA', '#C4B5FD', '#DDD6FE', '#EDE9FE']
            )])
            
            fig.update_layout(
                margin=dict(l=0, r=0, t=20, b=0),
                height=250,
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Allocation list
            for arm in allocation:
                change_color = "#22C55E" if arm.get('change', 0) > 0 else "#EF4444" if arm.get('change', 0) < 0 else "#737373"
                change_text = f"+{arm.get('change', 0):.1f}%" if arm.get('change', 0) > 0 else f"{arm.get('change', 0):.1f}%"
                
                st.markdown(f"""
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0;">
                    <span style="font-size: 0.875rem;">{arm['name']}</span>
                    <div>
                        <span style="font-weight: 600;">{arm['allocation']:.1%}</span>
                        <span style="color: {change_color}; font-size: 0.75rem; margin-left: 8px;">{change_text}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No allocation data available")
    
    st.divider()
    
    # Arm Performance Table
    st.markdown("### Arm Performance")
    
    arms = data_service.get_arms_performance(campaign_id)
    
    if arms:
        # Create DataFrame for display
        arms_df = pd.DataFrame(arms)
        
        # Style the dataframe
        st.dataframe(
            arms_df[['name', 'platform', 'channel', 'allocation', 'roas', 'spend', 'conversions']],
            column_config={
                "name": "Arm",
                "platform": "Platform",
                "channel": "Channel",
                "allocation": st.column_config.ProgressColumn("Allocation", format="%.1f%%", min_value=0, max_value=100),
                "roas": st.column_config.NumberColumn("ROAS", format="%.2f"),
                "spend": st.column_config.NumberColumn("Spend", format="$%.2f"),
                "conversions": st.column_config.NumberColumn("Conv.", format="%d"),
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No arm data available")
    
    st.divider()
    
    # Explanation Section
    st.markdown("### Why These Allocations?")
    
    explanation = data_service.get_latest_explanation(campaign_id)
    
    if explanation:
        st.markdown(f"""
        <div class="explanation-card">
            <p style="margin: 0; font-size: 1rem;">{explanation['text']}</p>
            <div style="margin-top: 12px; display: flex; gap: 16px;">
                <span style="font-size: 0.75rem; color: #737373;">
                    📅 {explanation['timestamp']}
                </span>
                <span style="font-size: 0.75rem; color: #737373;">
                    🤖 {explanation['model']}
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Factors
        if explanation.get('factors'):
            st.markdown("**Contributing Factors:**")
            for factor, value in explanation['factors'].items():
                st.markdown(f"- **{factor}**: {value}")
    else:
        st.info("No explanation available yet. Run the optimizer to generate explanations.")
    
    # View history link
    if st.button("View Change History →"):
        st.session_state.current_page = "optimizer"
        st.rerun()


def toggle_pin(campaign: dict):
    """Toggle pinned status for a campaign."""
    if 'pinned_campaigns' not in st.session_state:
        st.session_state.pinned_campaigns = []
    
    pinned_ids = [c['id'] for c in st.session_state.pinned_campaigns]
    
    if campaign['id'] in pinned_ids:
        st.session_state.pinned_campaigns = [
            c for c in st.session_state.pinned_campaigns if c['id'] != campaign['id']
        ]
    else:
        st.session_state.pinned_campaigns.append({
            'id': campaign['id'],
            'name': campaign['name']
        })
