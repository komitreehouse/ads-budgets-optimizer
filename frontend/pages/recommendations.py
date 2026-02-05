"""
Recommendations Page

Shows pending, applied, and rejected recommendations with approval workflow.
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
    """Render the recommendations page."""
    data_service = DataService()
    
    # Header
    st.markdown("## ✓ Recommendations")
    st.markdown("Review and approve optimizer recommendations")
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["⏳ Pending", "✅ Applied", "❌ Rejected"])
    
    with tab1:
        render_pending_recommendations(data_service)
    
    with tab2:
        render_applied_recommendations(data_service)
    
    with tab3:
        render_rejected_recommendations(data_service)


def render_pending_recommendations(data_service: DataService):
    """Render pending recommendations with approval actions."""
    try:
        with st.spinner("Loading pending recommendations..."):
            recommendations = data_service.get_recommendations(status="pending")
    except Exception as e:
        render_error_message(e, "loading pending recommendations")
        recommendations = []
    
    # Update session state for sidebar badge
    st.session_state.pending_recommendations = len(recommendations)
    
    if not recommendations:
        st.success("🎉 No pending recommendations! All caught up.")
        return
    
    st.markdown(f"**{len(recommendations)} recommendations** awaiting your review")
    
    # Bulk actions
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("✓ Approve All", type="primary"):
            for rec in recommendations:
                data_service.approve_recommendation(rec['id'])
            st.success("All recommendations approved!")
            st.rerun()
    with col2:
        if st.button("✗ Reject All"):
            for rec in recommendations:
                data_service.reject_recommendation(rec['id'])
            st.info("All recommendations rejected")
            st.rerun()
    
    st.divider()
    
    # Render each recommendation
    for rec in recommendations:
        render_recommendation_card(rec, data_service, show_actions=True)


def render_applied_recommendations(data_service: DataService):
    """Render applied recommendations history."""
    try:
        with st.spinner("Loading applied recommendations..."):
            recommendations = data_service.get_recommendations(status="applied")
    except Exception as e:
        render_error_message(e, "loading applied recommendations")
        recommendations = []
    
    if not recommendations:
        st.info("No applied recommendations yet.")
        return
    
    st.markdown(f"**{len(recommendations)} recommendations** have been applied")
    st.divider()
    
    for rec in recommendations:
        render_recommendation_card(rec, data_service, show_actions=False)


def render_rejected_recommendations(data_service: DataService):
    """Render rejected recommendations history."""
    recommendations = data_service.get_recommendations(status="rejected")
    
    if not recommendations:
        st.info("No rejected recommendations.")
        return
    
    st.markdown(f"**{len(recommendations)} recommendations** were rejected")
    st.divider()
    
    for rec in recommendations:
        render_recommendation_card(rec, data_service, show_actions=False)


def render_recommendation_card(rec: dict, data_service: DataService, show_actions: bool = True):
    """Render a single recommendation card."""
    type_icons = {
        "allocation_change": "📊",
        "budget_adjustment": "💰",
        "campaign_pause": "⏸",
        "campaign_resume": "▶",
        "arm_disable": "🚫",
        "arm_enable": "✅"
    }
    
    icon = type_icons.get(rec.get('type', ''), "🎯")
    confidence = rec.get('confidence', 0)
    confidence_color = "#22C55E" if confidence >= 0.8 else "#F59E0B" if confidence >= 0.5 else "#EF4444"
    
    with st.container():
        st.markdown(f"""
        <div class="recommendation-card">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div style="display: flex; gap: 12px; align-items: start;">
                    <span style="font-size: 1.5rem;">{icon}</span>
                    <div>
                        <h4 style="margin: 0; font-size: 1.125rem; font-weight: 600;">{rec['title']}</h4>
                        <p style="margin: 4px 0 0 0; font-size: 0.875rem; color: #737373;">
                            {rec.get('campaign_name', 'Unknown Campaign')} • {rec.get('created_at', '')}
                        </p>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="background: {confidence_color}20; color: {confidence_color}; padding: 4px 12px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600;">
                        {confidence:.0%} confidence
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Description
        st.markdown(rec.get('description', 'No description available'))
        
        # Impact preview
        if rec.get('current_value') is not None and rec.get('proposed_value') is not None:
            col1, col2, col3 = st.columns([2, 1, 2])
            with col1:
                st.markdown(f"""
                <div style="text-align: center; padding: 12px; background: #F5F5F5; border-radius: 8px;">
                    <p style="margin: 0; font-size: 0.75rem; color: #737373;">Current</p>
                    <p style="margin: 0; font-size: 1.25rem; font-weight: 600;">{rec['current_value']}</p>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown("""
                <div style="text-align: center; padding: 12px;">
                    <span style="font-size: 1.5rem;">→</span>
                </div>
                """, unsafe_allow_html=True)
            with col3:
                st.markdown(f"""
                <div style="text-align: center; padding: 12px; background: #EDE9FE; border-radius: 8px;">
                    <p style="margin: 0; font-size: 0.75rem; color: #7C3AED;">Proposed</p>
                    <p style="margin: 0; font-size: 1.25rem; font-weight: 600; color: #7C3AED;">{rec['proposed_value']}</p>
                </div>
                """, unsafe_allow_html=True)
        
        # Expected impact
        if rec.get('expected_impact'):
            st.markdown(f"**Expected Impact:** {rec['expected_impact']}")
        
        # Explanation
        with st.expander("💡 Why this recommendation?"):
            st.markdown(rec.get('explanation', 'No explanation available'))
        
        # Actions
        if show_actions:
            col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
            
            with col1:
                if st.button("✓ Approve", key=f"approve_{rec['id']}", type="primary", use_container_width=True):
                    try:
                        with st.spinner("Approving recommendation..."):
                            data_service.approve_recommendation(rec['id'])
                        st.success("Recommendation approved!")
                        st.rerun()
                    except Exception as e:
                        render_error_message(e, "approving recommendation")
            
            with col2:
                if st.button("✗ Reject", key=f"reject_{rec['id']}", use_container_width=True):
                    try:
                        with st.spinner("Rejecting recommendation..."):
                            data_service.reject_recommendation(rec['id'])
                        st.info("Recommendation rejected")
                        st.rerun()
                    except Exception as e:
                        render_error_message(e, "rejecting recommendation")
            
            with col3:
                if st.button("✎ Modify", key=f"modify_{rec['id']}", use_container_width=True):
                    st.session_state[f"modifying_{rec['id']}"] = True
                    st.rerun()
            
            # Modification form
            if st.session_state.get(f"modifying_{rec['id']}", False):
                st.markdown("---")
                st.markdown("**Modify Recommendation**")
                
                new_value = st.text_input(
                    "New value",
                    value=str(rec.get('proposed_value', '')),
                    key=f"new_value_{rec['id']}"
                )
                reason = st.text_area(
                    "Reason for modification",
                    placeholder="Explain why you're modifying this recommendation...",
                    key=f"reason_{rec['id']}"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Save & Approve", key=f"save_mod_{rec['id']}", type="primary"):
                        try:
                            with st.spinner("Saving modification..."):
                                data_service.modify_recommendation(rec['id'], new_value, reason)
                                data_service.approve_recommendation(rec['id'])
                            st.session_state[f"modifying_{rec['id']}"] = False
                            st.success("Recommendation modified and approved!")
                            st.rerun()
                        except Exception as e:
                            render_error_message(e, "modifying recommendation")
                        st.success("Recommendation modified and approved!")
                        st.rerun()
                with col2:
                    if st.button("Cancel", key=f"cancel_mod_{rec['id']}"):
                        st.session_state[f"modifying_{rec['id']}"] = False
                        st.rerun()
        
        st.divider()
