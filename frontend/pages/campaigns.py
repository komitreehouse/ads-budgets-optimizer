"""
Campaigns Page - List all campaigns

Shows all campaigns in a table/card view with key metrics.
Allows navigation to individual campaign details.
"""

import streamlit as st
from datetime import datetime
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from frontend.services.data_service import DataService
from frontend.components.loading import render_loading_spinner, render_error_message, render_empty_state, render_retry_button


def render():
    """Render the campaigns list page."""
    data_service = DataService()
    
    # Header
    st.markdown("## 📊 Campaigns")
    st.markdown("Manage and monitor all your optimization campaigns")
    
    # Filters row
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        search = st.text_input("🔍 Search campaigns", placeholder="Search by name...")
    
    with col2:
        status_filter = st.selectbox(
            "Status",
            ["All", "Active", "Paused", "Completed"],
            index=0
        )
    
    with col3:
        sort_by = st.selectbox(
            "Sort by",
            ["Name", "Spend", "ROAS", "Last Updated"],
            index=0
        )
    
    with col4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("+ New Campaign", type="primary", use_container_width=True):
            st.info("Campaign creation coming soon!")
    
    st.divider()
    
    # Fetch campaigns with error handling
    try:
        with st.spinner("Loading campaigns..."):
            campaigns = data_service.get_campaigns()
    except Exception as e:
        render_error_message(e, "loading campaigns")
        render_retry_button(lambda: st.rerun(), "Retry")
        campaigns = []
        st.stop()
    
    # Apply filters
    if search:
        campaigns = [c for c in campaigns if search.lower() in c['name'].lower()]
    
    if status_filter != "All":
        campaigns = [c for c in campaigns if c['status'].lower() == status_filter.lower()]
    
    # Sort
    sort_keys = {
        "Name": "name",
        "Spend": "spend",
        "ROAS": "roas",
        "Last Updated": "updated_at"
    }
    campaigns = sorted(
        campaigns,
        key=lambda x: x.get(sort_keys[sort_by], 0),
        reverse=sort_by in ["Spend", "ROAS", "Last Updated"]
    )
    
    # Display campaigns
    if not campaigns:
        render_empty_state(
            message="No campaigns found",
            icon="📊",
            action_label="+ Create Campaign",
            on_action=lambda: st.info("Campaign creation coming soon!")
        )
        return
    
    if campaigns:
        # Summary stats
        active_count = len([c for c in campaigns if c['status'] == 'active'])
        total_spend = sum(c['spend'] for c in campaigns)
        avg_roas = sum(c['roas'] for c in campaigns) / len(campaigns) if campaigns else 0
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Campaigns", len(campaigns))
        col2.metric("Total Spend", f"${total_spend:,.2f}")
        col3.metric("Avg ROAS", f"{avg_roas:.2f}")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Campaign table
        for campaign in campaigns:
            render_campaign_row(campaign)
    else:
        st.info("No campaigns found matching your criteria.")


def render_campaign_row(campaign: dict):
    """Render a campaign as a clickable row."""
    status_color = "#22C55E" if campaign['status'] == 'active' else "#F59E0B"
    status_emoji = "🟢" if campaign['status'] == 'active' else "🟡"
    
    with st.container():
        col1, col2, col3, col4, col5, col6 = st.columns([3, 1, 1, 1, 1, 1])
        
        with col1:
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 12px;">
                <div>
                    <p style="margin: 0; font-weight: 600; font-size: 1rem;">{campaign['name']}</p>
                    <p style="margin: 0; font-size: 0.75rem; color: #737373;">
                        {campaign.get('arms_count', 0)} arms • Updated {campaign.get('updated_at', 'recently')}
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style="text-align: center;">
                <span style="color: {status_color};">{status_emoji}</span>
                <p style="margin: 0; font-size: 0.75rem; color: #737373;">Status</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div style="text-align: center;">
                <p style="margin: 0; font-weight: 600;">${campaign['spend']:,.0f}</p>
                <p style="margin: 0; font-size: 0.75rem; color: #737373;">Spend</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            roas_color = "#22C55E" if campaign['roas'] >= 2.0 else "#F59E0B" if campaign['roas'] >= 1.0 else "#EF4444"
            st.markdown(f"""
            <div style="text-align: center;">
                <p style="margin: 0; font-weight: 600; color: {roas_color};">{campaign['roas']:.2f}</p>
                <p style="margin: 0; font-size: 0.75rem; color: #737373;">ROAS</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col5:
            trend_color = "#22C55E" if campaign['roas_trend'] > 0 else "#EF4444"
            trend_arrow = "▲" if campaign['roas_trend'] > 0 else "▼"
            st.markdown(f"""
            <div style="text-align: center;">
                <p style="margin: 0; font-weight: 600; color: {trend_color};">
                    {trend_arrow} {abs(campaign['roas_trend']):.1f}%
                </p>
                <p style="margin: 0; font-size: 0.75rem; color: #737373;">Trend</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col6:
            if st.button("View →", key=f"view_{campaign['id']}", use_container_width=True):
                st.session_state.selected_campaign_id = campaign['id']
                st.session_state.current_page = "campaign_detail"
                st.rerun()
        
        st.divider()
