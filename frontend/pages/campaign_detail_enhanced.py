"""
Enhanced Campaign Detail Page

Features:
- Core KPIs with status indicators (current vs target)
- Spend & KPI Over Time (dual-axis chart)
- Channel & Tactic Breakdown with Budget Utilization & Pacing
- Chat widget for explanations
- Audience/Geo/Creative Insights
"""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pandas as pd
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from frontend.services.data_service import DataService
from frontend.components.metrics import render_metric_card, render_status_badge
from frontend.components.dual_axis_chart import render_dual_axis_chart, detect_anomalies
from frontend.components.chat_widget import render_chat_widget


def render(campaign_id: int):
    """Render the enhanced campaign detail page."""
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
            # Chat widget button
            render_chat_widget(campaign_id=campaign_id)
    
    st.divider()
    
    # ==========================================================================
    # CORE KPIs SECTION
    # ==========================================================================
    st.markdown("### Core KPIs (Current vs Target)")
    
    # Primary KPI selector
    primary_kpi = st.selectbox(
        "Primary KPI",
        ["ROAS", "CPA", "Revenue", "Conversions"],
        index=0,
        key="primary_kpi_selector"
    )
    
    # Get enhanced metrics
    enhanced_metrics = data_service.get_enhanced_campaign_metrics(campaign_id, primary_kpi)
    
    # Status indicator
    status = enhanced_metrics.get('status', 'stable')
    status_config = {
        'scaling': {'emoji': '🟢', 'label': 'Scaling opportunity', 'color': '#22C55E'},
        'stable': {'emoji': '🟡', 'label': 'Stable / watch', 'color': '#F59E0B'},
        'underperforming': {'emoji': '🔴', 'label': 'Underperforming', 'color': '#EF4444'}
    }
    status_info = status_config.get(status, status_config['stable'])
    
    st.markdown(f"""
    <div style="background: {status_info['color']}15; padding: 12px; border-radius: 8px; border-left: 4px solid {status_info['color']}; margin-bottom: 20px;">
        <strong>{status_info['emoji']} {status_info['label']}</strong>
        <div style="font-size: 0.875rem; color: #737373; margin-top: 4px;">
            Efficiency vs benchmark: {enhanced_metrics.get('efficiency_delta', 0):+.1f}%
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # KPI Cards
    today_data = enhanced_metrics.get('today', {})
    mtd_data = enhanced_metrics.get('mtd', {})
    total_data = enhanced_metrics.get('total', {})
    targets = enhanced_metrics.get('targets', {})
    
    # Spend row
    st.markdown("#### Spend")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        today_spend = today_data.get('spend', 0)
        target_today = campaign.get('budget', 0) / 30  # Daily target
        render_metric_card(
            "Today",
            f"${today_spend:,.2f}",
            trend=None,
            highlight=False
        )
        if target_today > 0:
            st.caption(f"Target: ${target_today:,.2f}")
    
    with col2:
        mtd_spend = mtd_data.get('spend', 0)
        mtd_target = campaign.get('budget', 0) * (datetime.now().day / 30)  # MTD target
        render_metric_card(
            "MTD",
            f"${mtd_spend:,.2f}",
            trend=None,
            highlight=False
        )
        if mtd_target > 0:
            st.caption(f"Target: ${mtd_target:,.2f}")
    
    with col3:
        total_spend = total_data.get('spend', 0)
        render_metric_card(
            "Total",
            f"${total_spend:,.2f}",
            trend=None,
            highlight=False
        )
        st.caption(f"Budget: ${campaign.get('budget', 0):,.2f}")
    
    # Primary KPI row
    st.markdown(f"#### Primary KPI: {primary_kpi}")
    col1, col2 = st.columns(2)
    
    with col1:
        primary_value = today_data.get(primary_kpi.lower(), 0)
        target_value = targets.get(primary_kpi.lower(), 0)
        
        if primary_kpi == "ROAS":
            value_str = f"{primary_value:.2f}"
        elif primary_kpi == "CPA":
            value_str = f"${primary_value:.2f}"
        elif primary_kpi == "Revenue":
            value_str = f"${primary_value:,.2f}"
        else:  # Conversions
            value_str = f"{int(primary_value):,}"
        
        render_metric_card(
            f"Current {primary_kpi}",
            value_str,
            trend=None,
            highlight=True
        )
        if target_value > 0:
            st.caption(f"Target: {value_str if primary_kpi == 'ROAS' else ('$' if primary_kpi in ['CPA', 'Revenue'] else '')}{target_value:,.2f if primary_kpi != 'ROAS' else ''}")
    
    with col2:
        efficiency_delta = enhanced_metrics.get('efficiency_delta', 0)
        render_metric_card(
            "Efficiency vs Benchmark",
            f"{efficiency_delta:+.1f}%",
            trend=efficiency_delta,
            highlight=False
        )
        st.caption("vs industry benchmark")
    
    # Secondary KPIs
    st.markdown("#### Secondary KPIs")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        cpc = today_data.get('cpc', 0)
        render_metric_card("CPC", f"${cpc:.2f}")
    
    with col2:
        cvr = today_data.get('cvr', 0)
        render_metric_card("CVR", f"{cvr:.2%}")
    
    with col3:
        aov = today_data.get('aov', 0)
        render_metric_card("AOV", f"${aov:.2f}")
    
    st.divider()
    
    # ==========================================================================
    # SPEND & KPI OVER TIME
    # ==========================================================================
    st.markdown("### Spend & KPI Over Time")
    
    # Chart controls
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        time_range = st.selectbox(
            "Time Range",
            ["7D", "30D", "90D", "MTD", "QTD"],
            index=1,
            key="time_range_selector"
        )
    
    with col2:
        show_rolling = st.checkbox("Rolling Average", value=False)
    
    with col3:
        show_anomalies = st.checkbox("Show Anomalies", value=True)
    
    # Get time series data
    time_series = data_service.get_performance_time_series(campaign_id, time_range)
    
    if time_series:
        # Map KPI key
        kpi_key_map = {
            "ROAS": "roas",
            "CPA": "cpa",
            "Revenue": "revenue",
            "Conversions": "conversions"
        }
        kpi_key = kpi_key_map.get(primary_kpi, "roas")
        
        # Calculate CPA if needed
        if primary_kpi == "CPA":
            for point in time_series:
                if point.get('conversions', 0) > 0:
                    point['cpa'] = point.get('cost', 0) / point['conversions']
                else:
                    point['cpa'] = 0
        
        # Detect anomalies
        anomalies = []
        if show_anomalies:
            anomalies = detect_anomalies(time_series, spend_key="cost", kpi_key=kpi_key)
        
        # Render dual-axis chart
        render_dual_axis_chart(
            data=time_series,
            x_key="date",
            left_y_key="cost",
            right_y_key=kpi_key,
            left_label="Spend ($)",
            right_label=primary_kpi,
            show_rolling_avg=show_rolling,
            rolling_window=7,
            anomalies=anomalies if show_anomalies else None,
            learning_periods=None,  # TODO: Add learning period detection
            height=400
        )
    else:
        st.info("No time-series data available")
    
    st.divider()
    
    # ==========================================================================
    # CHANNEL & TACTIC BREAKDOWN
    # ==========================================================================
    st.markdown("### Channel & Tactic Breakdown")
    
    channel_breakdown = data_service.get_channel_breakdown(campaign_id)
    
    if channel_breakdown:
        # Summary cards
        col1, col2, col3, col4 = st.columns(4)
        
        total_channel_spend = sum(c.get('spend', 0) for c in channel_breakdown)
        
        with col1:
            st.metric("Channels", len(channel_breakdown))
        
        with col2:
            avg_roas = sum(c.get('roas', 0) for c in channel_breakdown) / len(channel_breakdown) if channel_breakdown else 0
            st.metric("Avg ROAS", f"{avg_roas:.2f}")
        
        with col3:
            avg_pacing = sum(c.get('pacing', 0) for c in channel_breakdown) / len(channel_breakdown) if channel_breakdown else 0
            st.metric("Avg Pacing", f"{avg_pacing:.1f}%")
        
        with col4:
            total_utilization = sum(c.get('utilization', 0) for c in channel_breakdown)
            st.metric("Total Utilization", f"{total_utilization:.1f}%")
        
        # Channel table
        st.markdown("#### Budget Utilization & Pacing")
        
        channel_df = pd.DataFrame([
            {
                "Channel": c.get('channel', ''),
                "Platform": c.get('platform', ''),
                "Spend": f"${c.get('spend', 0):,.2f}",
                "Revenue": f"${c.get('revenue', 0):,.2f}",
                "ROAS": f"{c.get('roas', 0):.2f}",
                "Budget %": f"{c.get('budget_allocation', 0):.1f}%",
                "Pacing": f"{c.get('pacing', 0):.1f}%",
                "Status": "🟢" if c.get('pacing', 0) >= 95 and c.get('pacing', 0) <= 105 else ("🟡" if c.get('pacing', 0) >= 80 else "🔴")
            }
            for c in channel_breakdown
        ])
        
        st.dataframe(
            channel_df,
            hide_index=True,
            use_container_width=True
        )
        
        # Expandable detail for each channel
        for channel in channel_breakdown:
            with st.expander(f"{channel.get('channel', '')} - ${channel.get('spend', 0):,.2f}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Performance**")
                    st.metric("ROAS", f"{channel.get('roas', 0):.2f}")
                    st.metric("Conversions", f"{channel.get('conversions', 0):,}")
                    st.metric("Impressions", f"{channel.get('impressions', 0):,}")
                
                with col2:
                    st.markdown("**Budget**")
                    st.metric("Allocation", f"{channel.get('budget_allocation', 0):.1f}%")
                    st.metric("Utilization", f"{channel.get('utilization', 0):.1f}%")
                    st.metric("Pacing", f"{channel.get('pacing', 0):.1f}%")
                
                # Arms breakdown
                if channel.get('arms'):
                    st.markdown("**Arms**")
                    arms_df = pd.DataFrame(channel['arms'])
                    st.dataframe(arms_df, hide_index=True, use_container_width=True)
    else:
        st.info("No channel breakdown data available")
    
    st.divider()
    
    # ==========================================================================
    # AUDIENCE / GEO / CREATIVE INSIGHTS (MMM-lite)
    # ==========================================================================
    st.markdown("### Audience / Geo / Creative Insights")
    st.caption("Directional insights from MMM-lite + platform data")
    
    # Placeholder for insights
    # TODO: Add actual insights from MMM analysis
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Top Audiences**")
        st.info("""
        - Audience A: +15% ROAS
        - Audience B: +8% ROAS
        - Audience C: -5% ROAS
        """)
    
    with col2:
        st.markdown("**Top Geos**")
        st.info("""
        - US: +12% efficiency
        - UK: +5% efficiency
        - CA: -3% efficiency
        """)
    
    with col3:
        st.markdown("**Top Creatives**")
        st.info("""
        - Creative A: +20% CTR
        - Creative B: +10% CVR
        - Creative C: Baseline
        """)
    
    st.divider()
    
    # ==========================================================================
    # EXPLANATION SECTION (with chat integration)
    # ==========================================================================
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
        st.info("No explanation available yet. Use the chat widget to ask questions!")
    
    # Chat widget at bottom
    st.markdown("<br>", unsafe_allow_html=True)
    render_chat_widget(campaign_id=campaign_id, context="campaign_detail")
