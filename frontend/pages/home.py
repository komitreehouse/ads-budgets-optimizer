"""
Home Page - Dashboard Overview

Shows brand budget overview, channel splits, recent campaigns, and recommendations.
"""

import streamlit as st
from datetime import datetime, timedelta
import sys
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from frontend.components.metrics import render_metric_card, render_metric_row
from frontend.components.charts import render_sparkline
from frontend.components.loading import render_loading_spinner, render_error_message, render_empty_state, render_retry_button
from frontend.services.data_service import DataService


def render(greeting: str):
    """Render the home page."""
    data_service = DataService()
    
    # Initialize session state for channel drill-down
    if 'selected_channel' not in st.session_state:
        st.session_state.selected_channel = None
    
    # Greeting
    st.markdown(f"""
    <h1 class="greeting">{greeting} 👋</h1>
    """, unsafe_allow_html=True)
    
    # ==========================================================================
    # BUDGET OVERVIEW SECTION
    # ==========================================================================
    st.markdown("### 💰 Brand Budget Overview")
    
    # Time range selector
    col_filter, col_spacer = st.columns([1, 3])
    with col_filter:
        time_range = st.selectbox(
            "Time Range",
            options=["MTD", "QTD", "YTD", "FY"],
            format_func=lambda x: {
                "MTD": "Month to Date",
                "QTD": "Quarter to Date", 
                "YTD": "Year to Date",
                "FY": "Fiscal Year"
            }.get(x, x),
            key="budget_time_range",
            label_visibility="collapsed"
        )
    
    # Get budget data with error handling
    try:
        with st.spinner("Loading budget data..."):
            budget_data = data_service.get_brand_budget_overview(time_range)
            channel_data = data_service.get_channel_splits(time_range)
    except Exception as e:
        render_error_message(e, "loading budget data")
        render_retry_button(lambda: st.rerun(), "Retry")
        st.stop()
    
    # Budget summary cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        render_metric_card(
            label="Total Budget",
            value=f"${budget_data['total_budget']:,.0f}",
            trend=None
        )
    
    with col2:
        render_metric_card(
            label="Spent",
            value=f"${budget_data['spent']:,.0f}",
            trend=None
        )
    
    with col3:
        render_metric_card(
            label="Remaining",
            value=f"${budget_data['remaining']:,.0f}",
            trend=None
        )
    
    with col4:
        pacing_color = "#22C55E" if budget_data['pacing_percent'] <= 1.0 else "#EF4444"
        st.markdown(f"""
        <div class="card">
            <p style="margin: 0; font-size: 0.875rem; color: #737373;">Pacing</p>
            <p style="margin: 4px 0 0 0; font-size: 1.5rem; font-weight: 600; color: {pacing_color};">
                {budget_data['pacing_percent']:.1%}
            </p>
            <p style="margin: 4px 0 0 0; font-size: 0.75rem; color: #737373;">{budget_data['period_label']}</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Main budget visualization: Pie Chart + Channel Splits
    chart_col, splits_col = st.columns([1, 1])
    
    with chart_col:
        st.markdown("##### Budget Allocation by Channel")
        
        # Create pie chart
        fig = go.Figure(data=[go.Pie(
            labels=[c['name'] for c in channel_data],
            values=[c['budget'] for c in channel_data],
            hole=0.4,
            marker=dict(colors=[c['color'] for c in channel_data]),
            textinfo='percent+label',
            textposition='outside',
            hovertemplate="<b>%{label}</b><br>" +
                         "Budget: $%{value:,.0f}<br>" +
                         "Allocation: %{percent}<extra></extra>"
        )])
        
        fig.update_layout(
            showlegend=False,
            margin=dict(t=20, b=20, l=20, r=20),
            height=350,
            annotations=[dict(
                text=f"${budget_data['total_budget']/1000:.0f}K",
                x=0.5, y=0.5,
                font_size=20,
                showarrow=False
            )]
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with splits_col:
        st.markdown("##### Channel Performance")
        
        # Channel cards - clickable to drill down
        for channel in channel_data:
            is_selected = st.session_state.selected_channel == channel['id']
            border_style = f"border-left: 4px solid {channel['color']};"
            bg_style = "background: linear-gradient(135deg, #F9FAFB 0%, #F3F4F6 100%);" if is_selected else ""
            
            spent_percent = channel['spent'] / channel['budget'] if channel['budget'] > 0 else 0
            trend_color = "#22C55E" if channel['roas_trend'] > 0 else "#EF4444"
            trend_arrow = "▲" if channel['roas_trend'] > 0 else "▼"
            
            st.markdown(f"""
            <div class="card" style="{border_style} {bg_style} cursor: pointer; margin-bottom: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 1.25rem;">{channel['icon']}</span>
                        <span style="font-weight: 600;">{channel['name']}</span>
                    </div>
                    <span style="font-size: 0.875rem; color: #737373;">{channel['campaign_count']} campaigns</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-top: 8px;">
                    <div>
                        <span style="font-size: 1.1rem; font-weight: 600;">${channel['spent']:,.0f}</span>
                        <span style="font-size: 0.75rem; color: #737373;"> / ${channel['budget']:,.0f}</span>
                    </div>
                    <div>
                        <span style="font-size: 0.875rem;">ROAS: {channel['roas']:.2f}</span>
                        <span style="font-size: 0.75rem; color: {trend_color}; margin-left: 4px;">
                            {trend_arrow} {abs(channel['roas_trend']):.1f}%
                        </span>
                    </div>
                </div>
                <div style="margin-top: 8px; height: 4px; background: #E5E5E5; border-radius: 2px;">
                    <div style="height: 100%; width: {spent_percent*100}%; background: {channel['color']}; border-radius: 2px;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Button to select channel for drill-down
            if st.button(f"View Details →", key=f"channel_{channel['id']}", use_container_width=True):
                st.session_state.selected_channel = channel['id']
                st.rerun()
    
    # ==========================================================================
    # CHANNEL DRILL-DOWN SECTION (shows when a channel is selected)
    # ==========================================================================
    if st.session_state.selected_channel:
        st.markdown("---")
        render_channel_drilldown(data_service, st.session_state.selected_channel, time_range)
    
    st.markdown("---")
    
    # ==========================================================================
    # CAMPAIGNS AND RECOMMENDATIONS SECTION
    # ==========================================================================
    
    # Summary Metrics Row
    st.markdown("### 📊 Performance Overview")
    
    try:
        with st.spinner("Loading dashboard summary..."):
            summary = data_service.get_dashboard_summary()
    except Exception as e:
        render_error_message(e, "loading dashboard summary")
        render_retry_button(lambda: st.rerun(), "Retry")
        st.stop()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        render_metric_card(
            label="Total Spend Today",
            value=f"${summary['total_spend_today']:,.2f}",
            trend=summary['spend_trend'],
            trend_label="vs yesterday"
        )
    
    with col2:
        render_metric_card(
            label="Average ROAS",
            value=f"{summary['avg_roas']:.2f}",
            trend=summary['roas_trend'],
            trend_label="vs last week"
        )
    
    with col3:
        render_metric_card(
            label="Active Campaigns",
            value=str(summary['active_campaigns']),
            trend=None
        )
    
    with col4:
        render_metric_card(
            label="Pending Recommendations",
            value=str(summary['pending_recommendations']),
            trend=None,
            highlight=summary['pending_recommendations'] > 0
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Two column layout
    left_col, right_col = st.columns([2, 1])
    
    with left_col:
        # Recent Campaigns Section
        st.markdown("### Your Campaigns")
        
        try:
            campaigns = data_service.get_campaigns()
        except Exception as e:
            render_error_message(e, "loading campaigns")
            campaigns = []
        
        if campaigns:
            # Display as cards in a grid
            cols = st.columns(3)
            for i, campaign in enumerate(campaigns[:6]):
                with cols[i % 3]:
                    render_campaign_card(campaign)
        else:
            st.info("No campaigns found. Create your first campaign to get started!")
        
        # View all campaigns link
        if len(campaigns) > 6:
            if st.button("View All Campaigns →", key="view_all_campaigns"):
                st.session_state.current_page = "campaigns"
                st.rerun()
    
    with right_col:
        # Pending Recommendations
        st.markdown("### Pending Recommendations")
        
        try:
            recommendations = data_service.get_pending_recommendations()
        except Exception as e:
            render_error_message(e, "loading recommendations")
            recommendations = []
        
        if recommendations:
            for rec in recommendations[:3]:
                render_recommendation_preview(rec)
            
            if len(recommendations) > 3:
                if st.button("View All Recommendations", key="view_all_recs"):
                    st.session_state.current_page = "recommendations"
                    st.rerun()
        else:
            st.success("✓ No pending recommendations")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Recent Decisions Section
    st.markdown("### Recent Optimizer Decisions")
    
    try:
        decisions = data_service.get_recent_decisions(limit=5)
    except Exception as e:
        render_error_message(e, "loading decisions")
        decisions = []
    
    if decisions:
        for decision in decisions:
            render_decision_item(decision)
    else:
        st.info("No recent decisions. The optimizer will make decisions when campaigns are running.")


def render_channel_drilldown(data_service: DataService, channel_id: str, time_range: str):
    """Render the channel drill-down view."""
    
    # Get channel info
    channels = data_service.get_channel_splits(time_range)
    channel = next((c for c in channels if c['id'] == channel_id), None)
    
    if not channel:
        st.warning("Channel not found")
        return
    
    # Header with back button
    col_back, col_title = st.columns([1, 4])
    with col_back:
        if st.button("← Back to Overview"):
            st.session_state.selected_channel = None
            st.rerun()
    
    with col_title:
        st.markdown(f"""
        <h3 style="margin: 0;">{channel['icon']} {channel['name']} - Campaign Breakdown</h3>
        """, unsafe_allow_html=True)
    
    # Get campaigns and recommendations for this channel
    try:
        campaigns = data_service.get_channel_campaigns(channel_id, time_range)
        recommendations = data_service.get_channel_recommendations(channel_id)
    except Exception as e:
        render_error_message(e, "loading channel data")
        campaigns = []
        recommendations = []
    
    # Channel summary
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        render_metric_card(
            label="Channel Budget",
            value=f"${channel['budget']:,.0f}",
            trend=None
        )
    
    with col2:
        render_metric_card(
            label="Spent",
            value=f"${channel['spent']:,.0f}",
            trend=None
        )
    
    with col3:
        render_metric_card(
            label="Channel ROAS",
            value=f"{channel['roas']:.2f}",
            trend=channel['roas_trend'],
            trend_label="vs last period"
        )
    
    with col4:
        render_metric_card(
            label="Active Campaigns",
            value=str(channel['campaign_count']),
            trend=None
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Two column layout: Campaigns + Recommendations
    camp_col, rec_col = st.columns([2, 1])
    
    with camp_col:
        st.markdown("##### Live Campaigns & Spend Allocation")
        
        # Campaign allocation pie chart
        if campaigns:
            fig = go.Figure(data=[go.Pie(
                labels=[c['name'] for c in campaigns],
                values=[c['spent'] for c in campaigns],
                hole=0.3,
                marker=dict(colors=px.colors.qualitative.Set2[:len(campaigns)]),
                textinfo='percent',
                hovertemplate="<b>%{label}</b><br>" +
                             "Spent: $%{value:,.0f}<br>" +
                             "Allocation: %{percent}<extra></extra>"
            )])
            
            fig.update_layout(
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2),
                margin=dict(t=10, b=60, l=10, r=10),
                height=250
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Campaign details table
        st.markdown("##### Campaign Details")
        
        for campaign in campaigns:
            status_class = "status-active" if campaign['status'] == 'active' else "status-paused"
            status_emoji = "🟢" if campaign['status'] == 'active' else "🟡"
            trend_color = "#22C55E" if campaign['roas_trend'] > 0 else "#EF4444"
            trend_arrow = "▲" if campaign['roas_trend'] > 0 else "▼"
            pacing = campaign['spent'] / campaign['budget'] if campaign['budget'] > 0 else 0
            
            st.markdown(f"""
            <div class="card" style="margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div>
                        <h4 style="margin: 0; font-size: 1rem; font-weight: 600;">{campaign['name']}</h4>
                        <span class="{status_class}" style="font-size: 0.75rem;">{status_emoji} {campaign['status'].capitalize()}</span>
                    </div>
                    <div style="text-align: right;">
                        <p style="margin: 0; font-size: 0.875rem; color: #737373;">Allocation</p>
                        <p style="margin: 0; font-weight: 600;">{campaign['allocation_percent']:.0%}</p>
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 12px;">
                    <div>
                        <p style="margin: 0; font-size: 0.75rem; color: #737373;">Budget</p>
                        <p style="margin: 0; font-weight: 500;">${campaign['budget']:,.0f}</p>
                    </div>
                    <div>
                        <p style="margin: 0; font-size: 0.75rem; color: #737373;">Spent</p>
                        <p style="margin: 0; font-weight: 500;">${campaign['spent']:,.0f}</p>
                    </div>
                    <div>
                        <p style="margin: 0; font-size: 0.75rem; color: #737373;">ROAS</p>
                        <p style="margin: 0; font-weight: 500;">
                            {campaign['roas']:.2f}
                            <span style="font-size: 0.75rem; color: {trend_color}; margin-left: 4px;">
                                {trend_arrow} {abs(campaign['roas_trend']):.1f}%
                            </span>
                        </p>
                    </div>
                    <div>
                        <p style="margin: 0; font-size: 0.75rem; color: #737373;">Daily Spend</p>
                        <p style="margin: 0; font-weight: 500;">${campaign['daily_spend']:,.0f}</p>
                    </div>
                </div>
                
                <div style="margin-top: 12px;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #737373; margin-bottom: 4px;">
                        <span>Budget Pacing</span>
                        <span>{pacing:.1%}</span>
                    </div>
                    <div style="height: 6px; background: #E5E5E5; border-radius: 3px;">
                        <div style="height: 100%; width: {min(pacing*100, 100)}%; background: {'#22C55E' if pacing <= 1.0 else '#EF4444'}; border-radius: 3px;"></div>
                    </div>
                </div>
                
                <div style="display: flex; gap: 16px; margin-top: 12px; font-size: 0.75rem; color: #737373;">
                    <span>👁️ {campaign['impressions']:,} impressions</span>
                    <span>👆 {campaign['clicks']:,} clicks</span>
                    <span>🎯 {campaign['conversions']:,} conversions</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # View campaign button
            if st.button(f"View Campaign Details", key=f"view_camp_{campaign['id']}", use_container_width=True):
                st.session_state.selected_campaign_id = campaign['id']
                st.session_state.current_page = "campaign_detail"
                st.rerun()
    
    with rec_col:
        st.markdown("##### 🎯 Optimizer Recommendations")
        
        if recommendations:
            for rec in recommendations:
                rec_type_icons = {
                    'increase_budget': '📈',
                    'decrease_budget': '📉',
                    'reallocation': '🔄',
                    'pause': '⏸️',
                    'creative_refresh': '🎨',
                    'audience_expansion': '👥'
                }
                icon = rec_type_icons.get(rec['type'], '💡')
                confidence_color = "#22C55E" if rec['confidence'] >= 0.8 else "#F59E0B" if rec['confidence'] >= 0.6 else "#EF4444"
                
                st.markdown(f"""
                <div class="recommendation-card" style="margin-bottom: 12px;">
                    <div style="display: flex; align-items: start; gap: 8px;">
                        <span style="font-size: 1.5rem;">{icon}</span>
                        <div style="flex: 1;">
                            <h4 style="margin: 0; font-size: 0.9rem; font-weight: 600;">{rec['title']}</h4>
                            <p style="font-size: 0.8rem; color: #737373; margin: 4px 0 0 0;">{rec['description']}</p>
                            
                            <div style="display: flex; gap: 12px; margin-top: 8px; font-size: 0.75rem;">
                                <span style="color: {confidence_color};">
                                    ⚡ {rec['confidence']:.0%} confidence
                                </span>
                                <span style="color: #22C55E;">
                                    {rec['expected_impact']}
                                </span>
                            </div>
                            
                            <div style="background: #F3F4F6; padding: 8px; border-radius: 6px; margin-top: 8px; font-size: 0.75rem;">
                                <div style="display: flex; justify-content: space-between;">
                                    <span style="color: #737373;">Current:</span>
                                    <span>{rec['current_value']}</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; margin-top: 4px;">
                                    <span style="color: #737373;">Proposed:</span>
                                    <span style="font-weight: 600; color: #6366F1;">{rec['proposed_value']}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                col_approve, col_reject = st.columns(2)
                with col_approve:
                    if st.button("✓ Apply", key=f"apply_rec_{rec['id']}", use_container_width=True):
                        # Would apply recommendation
                        st.success("Applied!")
                        st.rerun()
                with col_reject:
                    if st.button("✗ Dismiss", key=f"dismiss_rec_{rec['id']}", use_container_width=True):
                        # Would dismiss recommendation
                        st.rerun()
        else:
            st.success("✓ No pending recommendations for this channel")


def render_campaign_card(campaign: dict):
    """Render a campaign card."""
    status_class = "status-active" if campaign['status'] == 'active' else "status-paused"
    status_emoji = "🟢" if campaign['status'] == 'active' else "🟡"
    
    st.markdown(f"""
    <div class="card" style="cursor: pointer;">
        <div style="display: flex; justify-content: space-between; align-items: start;">
            <h4 style="margin: 0; font-size: 1rem; font-weight: 600;">{campaign['name']}</h4>
            <span class="{status_class}">{status_emoji} {campaign['status'].capitalize()}</span>
        </div>
        <div style="margin-top: 12px;">
            <p style="margin: 0; font-size: 1.5rem; font-weight: 600;">${campaign['spend']:,.2f}</p>
            <p style="margin: 0; font-size: 0.75rem; color: #737373;">Today's Spend</p>
        </div>
        <div style="margin-top: 8px; display: flex; justify-content: space-between;">
            <span style="font-size: 0.875rem;">ROAS: {campaign['roas']:.2f}</span>
            <span style="font-size: 0.875rem; color: {'#22C55E' if campaign['roas_trend'] > 0 else '#EF4444'};">
                {'▲' if campaign['roas_trend'] > 0 else '▼'} {abs(campaign['roas_trend']):.1f}%
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Make card clickable
    if st.button("View Details", key=f"camp_{campaign['id']}", use_container_width=True):
        st.session_state.selected_campaign_id = campaign['id']
        st.session_state.current_page = "campaign_detail"
        st.rerun()


def render_recommendation_preview(rec: dict):
    """Render a recommendation preview card."""
    st.markdown(f"""
    <div class="recommendation-card">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
            <span style="font-size: 1.25rem;">🎯</span>
            <span style="font-weight: 600;">{rec['title']}</span>
        </div>
        <p style="font-size: 0.875rem; color: #737373; margin: 0;">
            {rec['description'][:100]}{'...' if len(rec['description']) > 100 else ''}
        </p>
        <div style="margin-top: 12px; display: flex; gap: 8px;">
            <span style="font-size: 0.75rem; color: #737373;">
                Confidence: {rec['confidence']:.0%}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✓ Approve", key=f"approve_home_{rec['id']}", use_container_width=True):
            DataService().approve_recommendation(rec['id'])
            st.rerun()
    with col2:
        if st.button("✗ Reject", key=f"reject_home_{rec['id']}", use_container_width=True):
            DataService().reject_recommendation(rec['id'])
            st.rerun()


def render_decision_item(decision: dict):
    """Render a decision timeline item."""
    time_str = decision['timestamp'].strftime('%H:%M') if isinstance(decision['timestamp'], datetime) else decision['timestamp']
    
    st.markdown(f"""
    <div style="display: flex; gap: 16px; padding: 12px 0; border-bottom: 1px solid #E5E5E5;">
        <div style="min-width: 60px; color: #737373; font-size: 0.875rem;">{time_str}</div>
        <div style="flex: 1;">
            <p style="margin: 0; font-weight: 500;">{decision['description']}</p>
            <p style="margin: 4px 0 0 0; font-size: 0.875rem; color: #737373;">
                {decision['campaign_name']} • {decision['type']}
            </p>
        </div>
        <div style="color: {'#22C55E' if decision.get('impact', 0) > 0 else '#737373'};">
            {'+' if decision.get('impact', 0) > 0 else ''}{decision.get('impact', 0):.1f}%
        </div>
    </div>
    """, unsafe_allow_html=True)
