"""
Optimizer Page

Shows optimizer service status, decision log, and factor attribution.
"""

import streamlit as st
from datetime import datetime, timedelta
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from frontend.services.data_service import DataService
from frontend.components.loading import render_loading_spinner, render_error_message, render_empty_state, render_retry_button


def render():
    """Render the optimizer status page."""
    data_service = DataService()
    
    # Header
    st.markdown("## 🤖 Optimizer Status")
    
    # Fetch status with error handling
    try:
        with st.spinner("Loading optimizer status..."):
            status = data_service.get_optimizer_status()
    except Exception as e:
        render_error_message(e, "loading optimizer status")
        render_retry_button(lambda: st.rerun(), "Retry")
        st.stop()
    
    # Status header
    status_color = {
        "running": "#22C55E",
        "paused": "#F59E0B",
        "error": "#EF4444"
    }.get(status['status'], "#737373")
    
    status_emoji = {
        "running": "🟢",
        "paused": "🟡",
        "error": "🔴"
    }.get(status['status'], "⚪")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 16px;">
            <span style="font-size: 2rem;">{status_emoji}</span>
            <div>
                <h3 style="margin: 0; color: {status_color};">
                    {status['status'].capitalize()}
                </h3>
                <p style="margin: 0; color: #737373; font-size: 0.875rem;">
                    Last run: {status.get('last_run', 'Never')} • Next run: {status.get('next_run', 'N/A')}
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if status['status'] == 'running':
            if st.button("⏸ Pause All", use_container_width=True):
                try:
                    with st.spinner("Pausing optimizer..."):
                        data_service.pause_optimizer()
                    st.success("Optimizer paused")
                    st.rerun()
                except Exception as e:
                    render_error_message(e, "pausing optimizer")
        else:
            if st.button("▶ Resume", type="primary", use_container_width=True):
                try:
                    with st.spinner("Resuming optimizer..."):
                        data_service.resume_optimizer()
                    st.success("Optimizer resumed")
                    st.rerun()
                except Exception as e:
                    render_error_message(e, "resuming optimizer")
        
        if st.button("🔄 Force Run", use_container_width=True):
            try:
                with st.spinner("Running optimization..."):
                    data_service.force_optimization_run()
                st.success("Optimization completed!")
                st.rerun()
            except Exception as e:
                render_error_message(e, "running optimization")
    
    st.divider()
    
    # Stats Overview
    st.markdown("### Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Campaigns Optimizing", status.get('active_campaigns', 0))
    
    with col2:
        st.metric("Optimizations Today", status.get('optimizations_today', 0))
    
    with col3:
        st.metric("Avg Optimization Time", f"{status.get('avg_time_ms', 0):.0f}ms")
    
    with col4:
        error_rate = status.get('error_rate', 0) * 100
        st.metric("Error Rate", f"{error_rate:.1f}%")
    
    st.divider()
    
    # Decision Log Section
    st.markdown("### Decision Log")
    
    # Filters
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        try:
            campaigns = data_service.get_campaigns()
        except Exception as e:
            render_error_message(e, "loading campaigns")
            campaigns = []
        campaign_options = ["All Campaigns"] + [c['name'] for c in campaigns]
        selected_campaign = st.selectbox(
            "Campaign",
            campaign_options,
            index=0,
            key="decision_campaign_filter"
        )
    
    with col2:
        decision_types = ["All Types", "Allocation Change", "Pause", "Resume", "Budget Update"]
        selected_type = st.selectbox(
            "Type",
            decision_types,
            index=0,
            key="decision_type_filter"
        )
    
    with col3:
        date_range = st.selectbox(
            "Period",
            ["Last 24 hours", "Last 7 days", "Last 30 days"],
            index=0,
            key="decision_date_filter"
        )
    
    # Get decisions with error handling
    try:
        with st.spinner("Loading decisions..."):
            decisions = data_service.get_decisions(
                campaign=selected_campaign if selected_campaign != "All Campaigns" else None,
                decision_type=selected_type if selected_type != "All Types" else None,
                period=date_range
            )
    except Exception as e:
        render_error_message(e, "loading decisions")
        decisions = []
    
    if decisions:
        for decision in decisions:
            render_decision_card(decision)
    else:
        st.info("No decisions found matching your criteria.")
    
    st.divider()
    
    # Factor Attribution Section
    st.markdown("### What's Driving Decisions")
    st.markdown("Aggregate view of factors influencing optimizer decisions")
    
    factors = data_service.get_factor_attribution()
    
    if factors:
        # Horizontal bar chart
        import plotly.graph_objects as go
        
        fig = go.Figure(go.Bar(
            x=[f['contribution'] for f in factors],
            y=[f['name'] for f in factors],
            orientation='h',
            marker_color='#7C3AED'
        ))
        
        fig.update_layout(
            margin=dict(l=0, r=0, t=20, b=0),
            height=300,
            xaxis=dict(
                title="Contribution to Decisions",
                showgrid=True,
                gridcolor='#E5E5E5'
            ),
            yaxis=dict(showgrid=False),
            plot_bgcolor='white'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Factor explanations
        with st.expander("Factor Explanations"):
            for factor in factors:
                st.markdown(f"""
                **{factor['name']}** ({factor['contribution']:.0%})
                
                {factor.get('description', 'No description available')}
                
                ---
                """)
    else:
        st.info("No factor attribution data available yet.")


def render_decision_card(decision: dict):
    """Render a decision card."""
    type_icons = {
        "allocation_change": "📊",
        "pause": "⏸",
        "resume": "▶",
        "budget_update": "💰"
    }
    
    icon = type_icons.get(decision.get('type', ''), "🔧")
    
    with st.expander(f"{icon} {decision['title']} - {decision['timestamp']}", expanded=False):
        st.markdown(f"""
        **Campaign:** {decision.get('campaign_name', 'Unknown')}
        
        **Type:** {decision.get('type', 'Unknown').replace('_', ' ').title()}
        
        **Description:**  
        {decision.get('description', 'No description')}
        
        **Reasoning:**  
        {decision.get('reasoning', 'No reasoning recorded')}
        """)
        
        if decision.get('factors'):
            st.markdown("**Contributing Factors:**")
            for factor, value in decision['factors'].items():
                st.markdown(f"- {factor}: {value}")
        
        if decision.get('impact'):
            impact = decision['impact']
            impact_color = "#22C55E" if impact > 0 else "#EF4444"
            st.markdown(f"**Impact:** <span style='color: {impact_color}'>{'+' if impact > 0 else ''}{impact:.1f}%</span>", unsafe_allow_html=True)
