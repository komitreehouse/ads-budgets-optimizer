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
from frontend.components.loading import render_loading_spinner, render_error_message, render_empty_state
from typing import Dict, Any
from typing import Dict, Any


def render(campaign_id: int):
    """Render the enhanced campaign detail page."""
    data_service = DataService()
    
    # Back button
    if st.button("← Back to Campaigns"):
        st.session_state.selected_campaign_id = None
        st.session_state.current_page = "campaigns"
        st.rerun()
    
    # Fetch campaign data with loading state
    try:
        with st.spinner("Loading campaign data..."):
            campaign = data_service.get_campaign(campaign_id)
        
        if not campaign:
            render_empty_state(
                message="Campaign not found",
                icon="🔍",
                action_label="← Back to Campaigns",
                on_action=lambda: setattr(st.session_state, 'selected_campaign_id', None) or setattr(st.session_state, 'current_page', 'campaigns')
            )
            return
    except Exception as e:
        render_error_message(e, "loading campaign")
        if st.button("← Back to Campaigns"):
            st.session_state.selected_campaign_id = None
            st.session_state.current_page = "campaigns"
            st.rerun()
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
                    try:
                        with st.spinner("Pausing campaign..."):
                            data_service.pause_campaign(campaign_id)
                        st.success("Campaign paused")
                        st.rerun()
                    except Exception as e:
                        render_error_message(e, "pausing campaign")
            else:
                if st.button("▶ Resume", use_container_width=True):
                    try:
                        with st.spinner("Resuming campaign..."):
                            data_service.resume_campaign(campaign_id)
                        st.success("Campaign resumed")
                        st.rerun()
                    except Exception as e:
                        render_error_message(e, "resuming campaign")
        with col_b:
            # Chat toggle button
            if st.button("💬 Ask", use_container_width=True):
                if 'chat_open' not in st.session_state:
                    st.session_state.chat_open = True
                else:
                    st.session_state.chat_open = not st.session_state.chat_open
                st.rerun()
    
    st.divider()
    
    # ==========================================================================
    # CORE KPIs SECTION
    # ==========================================================================
    st.markdown("### Core KPIs (Current vs Target)")
    
    # Get campaign settings to determine default KPI
    campaign_settings = data_service.get_campaign_settings(campaign_id)
    default_kpi = campaign_settings.get('primary_kpi', 'ROAS')
    
    # Get saved KPI preference or use campaign default
    kpi_key = f"campaign_{campaign_id}_primary_kpi"
    if kpi_key not in st.session_state:
        st.session_state[kpi_key] = default_kpi
    
    # Primary KPI selector with settings button
    col_kpi, col_settings = st.columns([3, 1])
    
    with col_kpi:
        kpi_options = ["ROAS", "CPA", "Revenue", "Conversions"]
        kpi_index = kpi_options.index(st.session_state[kpi_key]) if st.session_state[kpi_key] in kpi_options else 0
        
        primary_kpi = st.selectbox(
            "Primary KPI",
            kpi_options,
            index=kpi_index,
            key="primary_kpi_selector"
        )
        
        # Save KPI preference if changed
        if primary_kpi != st.session_state[kpi_key]:
            st.session_state[kpi_key] = primary_kpi
            # Update campaign setting in database
            try:
                data_service.update_campaign_settings(campaign_id, {"primary_kpi": primary_kpi})
            except Exception as e:
                st.warning(f"Could not save KPI preference: {e}")
    
    with col_settings:
        st.markdown("<br>", unsafe_allow_html=True)  # Align with selectbox
        if st.button("⚙️ Settings", use_container_width=True, key="settings_button"):
            st.session_state[f"show_settings_{campaign_id}"] = True
            st.rerun()
    
    # Settings panel
    if st.session_state.get(f"show_settings_{campaign_id}", False):
        with st.expander("⚙️ Campaign Settings", expanded=True):
            render_campaign_settings(campaign_id, campaign_settings, data_service)
    
    # Get enhanced metrics with error handling
    try:
        with st.spinner("Loading metrics..."):
            enhanced_metrics = data_service.get_enhanced_campaign_metrics(campaign_id, primary_kpi)
    except Exception as e:
        render_error_message(e, "loading metrics")
        st.stop()
    
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
    
    # Get time series data with error handling
    try:
        with st.spinner("Loading time series data..."):
            time_series = data_service.get_performance_time_series(campaign_id, time_range)
    except Exception as e:
        render_error_message(e, "loading time series data")
        time_series = []
    
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
                cost = point.get('cost', 0)
                conversions = point.get('conversions', 0)
                if conversions > 0:
                    point['cpa'] = cost / conversions
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
    
    # Get channel breakdown with error handling
    try:
        with st.spinner("Loading channel breakdown..."):
            channel_breakdown = data_service.get_channel_breakdown(campaign_id)
    except Exception as e:
        render_error_message(e, "loading channel breakdown")
        channel_breakdown = []
    
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
    
def render_campaign_settings(campaign_id: int, settings: Dict[str, Any], data_service: DataService):
    """Render campaign settings configuration panel."""
    st.markdown("#### Targets")
    
    col1, col2 = st.columns(2)
    
    with col1:
        target_roas = st.number_input("Target ROAS", value=settings.get('targets', {}).get('roas') or 2.0, min_value=0.0, step=0.1, key="target_roas")
        target_cpa = st.number_input("Target CPA ($)", value=settings.get('targets', {}).get('cpa') or 50.0, min_value=0.0, step=1.0, key="target_cpa")
    
    with col2:
        target_revenue = st.number_input("Target Revenue ($)", value=settings.get('targets', {}).get('revenue') or 0.0, min_value=0.0, step=100.0, key="target_revenue")
        target_conversions = st.number_input("Target Conversions", value=settings.get('targets', {}).get('conversions') or 100, min_value=0, step=10, key="target_conversions")
    
    st.markdown("#### Benchmarks")
    
    col3, col4 = st.columns(2)
    
    with col3:
        benchmark_roas = st.number_input("Benchmark ROAS", value=settings.get('benchmarks', {}).get('roas') or 1.8, min_value=0.0, step=0.1, key="benchmark_roas")
        benchmark_cpa = st.number_input("Benchmark CPA ($)", value=settings.get('benchmarks', {}).get('cpa') or 55.0, min_value=0.0, step=1.0, key="benchmark_cpa")
    
    with col4:
        benchmark_revenue = st.number_input("Benchmark Revenue ($)", value=settings.get('benchmarks', {}).get('revenue') or 0.0, min_value=0.0, step=100.0, key="benchmark_revenue")
        benchmark_conversions = st.number_input("Benchmark Conversions", value=settings.get('benchmarks', {}).get('conversions') or 90, min_value=0, step=10, key="benchmark_conversions")
    
    st.markdown("#### Status Thresholds")
    st.caption("Multipliers for target values (e.g., 1.1 = 10% above target for scaling)")
    
    col5, col6 = st.columns(2)
    
    with col5:
        scaling_threshold = st.number_input("Scaling Threshold", value=settings.get('thresholds', {}).get('scaling', 1.1), min_value=1.0, max_value=2.0, step=0.05, key="scaling_threshold")
    
    with col6:
        stable_threshold = st.number_input("Stable Threshold", value=settings.get('thresholds', {}).get('stable', 0.9), min_value=0.5, max_value=1.0, step=0.05, key="stable_threshold")
    
    col_save, col_cancel = st.columns([1, 1])
    
    with col_save:
        if st.button("💾 Save Settings", use_container_width=True, type="primary"):
            update_data = {
                "targets": {
                    "roas": target_roas,
                    "cpa": target_cpa,
                    "revenue": target_revenue if target_revenue > 0 else None,
                    "conversions": target_conversions
                },
                "benchmarks": {
                    "roas": benchmark_roas,
                    "cpa": benchmark_cpa,
                    "revenue": benchmark_revenue if benchmark_revenue > 0 else None,
                    "conversions": benchmark_conversions
                },
                "thresholds": {
                    "scaling": scaling_threshold,
                    "stable": stable_threshold
                }
            }
            
            try:
                with st.spinner("Saving settings..."):
                    result = data_service.update_campaign_settings(campaign_id, update_data)
                st.success("Settings saved successfully!")
                st.session_state[f"show_settings_{campaign_id}"] = False
                st.rerun()
            except Exception as e:
                render_error_message(e, "saving settings")
    
    with col_cancel:
        if st.button("❌ Cancel", use_container_width=True):
            st.session_state[f"show_settings_{campaign_id}"] = False
            st.rerun()


    # Chat widget at bottom (if open)
    if st.session_state.get('chat_open', False):
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("💬 Ask about this campaign", expanded=True):
            # Display messages
            if 'chat_messages' not in st.session_state:
                st.session_state.chat_messages = []
            
            for msg in st.session_state.chat_messages[-5:]:  # Show last 5
                role = msg.get('role', 'assistant')
                content = msg.get('content', '')
                
                if role == 'user':
                    st.markdown(f"**You:** {content}")
                else:
                    st.markdown(f"**Assistant:** {content}")
            
            # Input
            query = st.text_input(
                "Ask a question...",
                key="chat_input",
                placeholder="e.g., Why did ROAS drop last week?"
            )
            
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("Send", use_container_width=True, key="chat_send"):
                    if query:
                        # Add user message
                        st.session_state.chat_messages.append({
                            'role': 'user',
                            'content': query
                        })
                        
                        # TODO: Call orchestrator API
                        # For now, show placeholder response
                        st.session_state.chat_messages.append({
                            'role': 'assistant',
                            'content': f"Based on the campaign data, I can help explain that. (Orchestrator integration pending)"
                        })
                        st.rerun()
            
            with col2:
                if st.button("Close", use_container_width=True, key="chat_close"):
                    st.session_state.chat_open = False
                    st.rerun()
