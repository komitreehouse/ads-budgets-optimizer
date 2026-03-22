"""
Action Center — Pending Recommendations

Decision-first view: each action shows estimated impact and confidence
before the user decides to apply, dismiss, or investigate further.
"""

import streamlit as st
from datetime import datetime
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from frontend.services.data_service import DataService
from frontend.components.loading import render_error_message, render_empty_state


TYPE_ICONS = {
    "allocation_change": "📊",
    "budget_adjustment": "💰",
    "campaign_pause": "⏸",
    "campaign_resume": "▶",
    "arm_disable": "🚫",
    "arm_enable": "✅",
    "increase_budget": "📈",
    "decrease_budget": "📉",
    "reallocation": "🔄",
    "pause": "⏸️",
    "creative_refresh": "🎨",
}


def render():
    """Render the Action Center page."""
    data_service = DataService()

    st.markdown("## ✓ Action Center")

    tab_pending, tab_applied, tab_rejected = st.tabs(["⏳ Pending", "✅ Applied", "❌ Rejected"])

    with tab_pending:
        _render_pending(data_service)

    with tab_applied:
        _render_applied(data_service)

    with tab_rejected:
        _render_rejected(data_service)


# ---------------------------------------------------------------------------
# Tab renderers
# ---------------------------------------------------------------------------

def _render_pending(data_service: DataService):
    try:
        recs = data_service.get_recommendations(status="pending")
    except Exception as e:
        render_error_message(e, "loading pending actions")
        recs = []

    st.session_state.pending_recommendations = len(recs)

    if not recs:
        st.success("🎉 No pending actions — you're all caught up!")
        return

    # Sort by confidence (highest first — proxy for estimated impact)
    recs_sorted = sorted(recs, key=lambda r: r.get("confidence", 0), reverse=True)

    # Aggregate estimated impact
    total_roas_impact = sum(_parse_impact_pct(r.get("expected_impact", "")) for r in recs_sorted)

    # Header summary
    impact_str = f"+{total_roas_impact:.0f}% ROAS" if total_roas_impact > 0 else "varies"
    st.markdown(f"""
    <div style="padding: 12px 16px; background: #fdf6f0; border-radius: 10px;
                border-left: 4px solid #9b4819; margin-bottom: 20px;">
        <span style="font-size:1rem; font-weight:600; color:#9b4819;">
            {len(recs_sorted)} action{'s' if len(recs_sorted) != 1 else ''} waiting
        </span>
        <span style="font-size:0.9rem; color:#717182; margin-left:12px;">
            Estimated combined impact if all applied: {impact_str}
        </span>
    </div>
    """, unsafe_allow_html=True)

    # Bulk actions row
    ba_col1, ba_col2, _ = st.columns([1, 1, 4])
    with ba_col1:
        if st.button("✓ Apply All", type="primary", use_container_width=True, key="apply_all"):
            for rec in recs_sorted:
                data_service.approve_recommendation(rec["id"])
            st.success("All actions applied!")
            st.rerun()
    with ba_col2:
        if st.button("✗ Dismiss All", use_container_width=True, key="dismiss_all"):
            for rec in recs_sorted:
                data_service.reject_recommendation(rec["id"])
            st.info("All actions dismissed")
            st.rerun()

    st.divider()

    for rec in recs_sorted:
        _render_action_card(rec, data_service, show_actions=True)


def _render_applied(data_service: DataService):
    try:
        recs = data_service.get_recommendations(status="applied")
    except Exception as e:
        render_error_message(e, "loading applied actions")
        recs = []

    if not recs:
        st.info("No actions have been applied yet.")
        return

    st.markdown(f"**{len(recs)} actions** applied")
    st.divider()

    for rec in recs:
        _render_action_card(rec, data_service, show_actions=False, compact=True)


def _render_rejected(data_service: DataService):
    try:
        recs = data_service.get_recommendations(status="rejected")
    except Exception as e:
        render_error_message(e, "loading rejected actions")
        recs = []

    if not recs:
        st.info("No rejected actions.")
        return

    st.markdown(f"**{len(recs)} actions** were dismissed")
    st.divider()

    for rec in recs:
        _render_action_card(rec, data_service, show_actions=False, compact=True)


# ---------------------------------------------------------------------------
# Card renderer
# ---------------------------------------------------------------------------

def _render_action_card(rec: dict, data_service: DataService, show_actions: bool, compact: bool = False):
    """Render a single recommendation/action card."""
    icon = TYPE_ICONS.get(rec.get("type", ""), "🎯")
    confidence = rec.get("confidence", 0)
    conf_color = "#22C55E" if confidence >= 0.8 else "#F59E0B" if confidence >= 0.5 else "#EF4444"
    impact_str = rec.get("expected_impact", "")
    campaign_name = rec.get("campaign_name", "Unknown campaign")
    created_at = rec.get("created_at", "")

    with st.container():
        # Card header
        st.markdown(f"""
        <div class="recommendation-card">
            <div style="display:flex; justify-content:space-between; align-items:start; gap:12px;">
                <div style="display:flex; gap:12px; align-items:start; flex:1;">
                    <span style="font-size:1.5rem; line-height:1;">{icon}</span>
                    <div style="flex:1;">
                        <h4 style="margin:0; font-size:1.05rem; font-weight:600;">{rec['title']}</h4>
                        <p style="margin:3px 0 0 0; font-size:0.82rem; color:#717182;">
                            {campaign_name} · {created_at}
                        </p>
                    </div>
                </div>
                <div style="text-align:right; min-width:110px;">
                    <div style="background:{conf_color}20; color:{conf_color}; padding:3px 10px;
                                border-radius:9999px; font-size:0.75rem; font-weight:600; display:inline-block;">
                        {confidence:.0%} confidence
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if not compact:
            # Impact line
            if impact_str:
                st.markdown(f"""
                <div style="display:flex; align-items:center; gap:16px; padding: 8px 0;">
                    <span style="font-size:0.9rem; font-weight:600; color:#22C55E;">{impact_str}</span>
                    <span style="font-size:0.85rem; color:#717182;">{rec.get('description', '')[:120]}{'...' if len(rec.get('description','')) > 120 else ''}</span>
                </div>
                """, unsafe_allow_html=True)

            # Confidence bar
            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:8px; margin:4px 0 8px 0;">
                <span style="font-size:0.75rem; color:#717182; min-width:80px;">Confidence</span>
                <div style="flex:1; height:6px; background:#E5E5E5; border-radius:3px;">
                    <div style="height:100%; width:{confidence*100:.0f}%; background:{conf_color}; border-radius:3px;"></div>
                </div>
                <span style="font-size:0.75rem; color:{conf_color}; min-width:36px;">{confidence:.0%}</span>
            </div>
            """, unsafe_allow_html=True)

            # Current → Proposed
            if rec.get("current_value") is not None and rec.get("proposed_value") is not None:
                cv_col, arrow_col, pv_col = st.columns([2, 1, 2])
                with cv_col:
                    st.markdown(f"""
                    <div style="text-align:center; padding:10px 12px; background:#F5F5F5; border-radius:8px;">
                        <p style="margin:0; font-size:0.72rem; color:#717182;">Current</p>
                        <p style="margin:0; font-size:1.15rem; font-weight:600;">{rec['current_value']}</p>
                    </div>
                    """, unsafe_allow_html=True)
                with arrow_col:
                    st.markdown('<div style="text-align:center; padding:10px 0; font-size:1.4rem;">→</div>', unsafe_allow_html=True)
                with pv_col:
                    st.markdown(f"""
                    <div style="text-align:center; padding:10px 12px; background:#EDE9FE; border-radius:8px;">
                        <p style="margin:0; font-size:0.72rem; color:#7C3AED;">Proposed</p>
                        <p style="margin:0; font-size:1.15rem; font-weight:600; color:#7C3AED;">{rec['proposed_value']}</p>
                    </div>
                    """, unsafe_allow_html=True)

            # Explanation expander
            with st.expander("💡 Why this action?"):
                st.markdown(rec.get("explanation", "No explanation available."))

        if show_actions:
            a1, a2, a3, _ = st.columns([1, 1, 1, 3])
            with a1:
                if st.button("✓ Apply", key=f"apply_{rec['id']}", type="primary", use_container_width=True):
                    try:
                        data_service.approve_recommendation(rec["id"])
                        st.success("Applied!")
                        st.rerun()
                    except Exception as e:
                        render_error_message(e, "applying action")
            with a2:
                if st.button("✗ Dismiss", key=f"dismiss_{rec['id']}", use_container_width=True):
                    try:
                        data_service.reject_recommendation(rec["id"])
                        st.rerun()
                    except Exception as e:
                        render_error_message(e, "dismissing action")
            with a3:
                if st.button("✎ Modify", key=f"modify_{rec['id']}", use_container_width=True):
                    st.session_state[f"modifying_{rec['id']}"] = not st.session_state.get(f"modifying_{rec['id']}", False)
                    st.rerun()

            if st.session_state.get(f"modifying_{rec['id']}", False):
                with st.container():
                    new_value = st.text_input(
                        "Modified value",
                        value=str(rec.get("proposed_value", "")),
                        key=f"new_val_{rec['id']}",
                    )
                    reason = st.text_area(
                        "Reason for modification",
                        placeholder="Why are you changing this recommendation?",
                        key=f"reason_{rec['id']}",
                    )
                    sc1, sc2 = st.columns(2)
                    with sc1:
                        if st.button("Save & Apply", key=f"save_mod_{rec['id']}", type="primary"):
                            try:
                                data_service.modify_recommendation(rec["id"], new_value, reason)
                                data_service.approve_recommendation(rec["id"])
                                st.session_state[f"modifying_{rec['id']}"] = False
                                st.success("Modified and applied!")
                                st.rerun()
                            except Exception as e:
                                render_error_message(e, "saving modification")
                    with sc2:
                        if st.button("Cancel", key=f"cancel_mod_{rec['id']}"):
                            st.session_state[f"modifying_{rec['id']}"] = False
                            st.rerun()

        st.divider()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _parse_impact_pct(impact_str: str) -> float:
    """Extract a percentage number from an impact string like '+12% ROAS'."""
    import re
    match = re.search(r"[+-]?(\d+(?:\.\d+)?)\s*%", impact_str)
    if match:
        sign = -1 if impact_str.strip().startswith("-") else 1
        return sign * float(match.group(1))
    return 0.0
