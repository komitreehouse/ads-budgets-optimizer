"""
Home Page — Budget Command Center

Answers: "How is my budget being spent right now?"

Four KPI tiles → channel allocation bar → pacing alerts → recent changes.
"""

import streamlit as st
from datetime import datetime, timedelta
import sys
from pathlib import Path
import plotly.graph_objects as go

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from frontend.components.metrics import render_metric_card
from frontend.components.loading import render_error_message, render_retry_button
from frontend.services.data_service import DataService


def render(greeting: str):
    """Render the Budget Command Center home page."""
    data_service = DataService()

    # -----------------------------------------------------------------------
    # Greeting
    # -----------------------------------------------------------------------
    st.markdown(f'<h1 class="greeting">{greeting} 👋</h1>', unsafe_allow_html=True)
    st.caption("Budget Command Center · Real-time ML optimization · Explainable decisions · Causal MMM")

    # Time range picker (compact, top-right feel)
    col_title, col_range = st.columns([3, 1])
    with col_range:
        time_range = st.selectbox(
            "Period",
            options=["MTD", "QTD", "YTD", "FY"],
            format_func=lambda x: {"MTD": "Month to Date", "QTD": "Quarter to Date",
                                    "YTD": "Year to Date", "FY": "Fiscal Year"}.get(x, x),
            key="home_time_range",
            label_visibility="collapsed",
        )

    # -----------------------------------------------------------------------
    # Demo banner — shown when running on mock data (no real campaigns)
    # -----------------------------------------------------------------------
    if data_service.use_mock and not st.session_state.get("demo_banner_dismissed", False):
        banner_col, btn_col, close_col = st.columns([6, 2, 1])
        with banner_col:
            st.markdown("""
            <div style="padding: 10px 0;">
                <span style="font-size: 0.95rem; font-weight: 600; color: #9b4819;">🎬 Demo mode</span>
                <span style="font-size: 0.88rem; color: #717182; margin-left: 8px;">
                    No live campaigns connected — explore a sample dataset to see IPSA in action.
                </span>
            </div>
            """, unsafe_allow_html=True)
        with btn_col:
            if st.button("▶ Run Demo", key="home_run_demo", type="primary", use_container_width=True):
                st.session_state.current_page = "onboarding"
                st.session_state.onboarding_step = 1
                st.rerun()
        with close_col:
            if st.button("✕", key="home_dismiss_demo", use_container_width=True):
                st.session_state.demo_banner_dismissed = True
                st.rerun()
        st.divider()

    # -----------------------------------------------------------------------
    # Fetch data
    # -----------------------------------------------------------------------
    try:
        budget_data = data_service.get_brand_budget_overview(time_range)
        channel_data = data_service.get_channel_splits(time_range)
        summary = data_service.get_dashboard_summary()
        decisions = data_service.get_recent_decisions(limit=3)
        optimizer_status = data_service.get_optimizer_status()
    except Exception as e:
        render_error_message(e, "loading dashboard data")
        render_retry_button(lambda: st.rerun(), "Retry")
        st.stop()

    # -----------------------------------------------------------------------
    # KPI Strip — 4 tiles
    # -----------------------------------------------------------------------
    spent = budget_data["spent"]
    total = budget_data["total_budget"]
    pacing = budget_data["pacing_percent"]

    # Pacing label
    if pacing < 0.9:
        pace_label, pace_color = "underpacing", "#F59E0B"
    elif pacing > 1.1:
        pace_label, pace_color = "overpacing", "#EF4444"
    else:
        pace_label, pace_color = "on pace", "#22C55E"

    # Optimizer status
    opt_status = optimizer_status.get("status", "unknown")
    last_run = optimizer_status.get("last_run", "—")
    active_camps = optimizer_status.get("active_campaigns", 0)
    opt_icon = "🟢" if opt_status == "running" else "🟡"

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        pct_used = pacing * 100
        st.markdown(f"""
        <div class="card">
            <p class="metric-label">Total Spend / Budget</p>
            <p class="metric-value">${spent:,.0f}</p>
            <p style="margin:2px 0 0 0; font-size:0.85rem; color:#717182;">
                of ${total:,.0f} · {pct_used:.0f}% used
            </p>
            <p style="margin:6px 0 0 0; font-size:0.8rem; font-weight:600; color:{pace_color};">
                {pace_label}
            </p>
        </div>
        """, unsafe_allow_html=True)

    with kpi2:
        roas = summary.get("avg_roas", 0)
        roas_trend = summary.get("roas_trend", 0)
        trend_arrow = "▲" if roas_trend >= 0 else "▼"
        trend_color = "#22C55E" if roas_trend >= 0 else "#EF4444"
        st.markdown(f"""
        <div class="card">
            <p class="metric-label">Blended ROAS</p>
            <p class="metric-value">{roas:.2f}x</p>
            <p style="margin:2px 0 0 0; font-size:0.85rem; color:{trend_color}; font-weight:600;">
                {trend_arrow} {abs(roas_trend):.1f}% vs last week
            </p>
        </div>
        """, unsafe_allow_html=True)

    with kpi3:
        inc_revenue = spent * roas * 0.28  # rough incremental revenue estimate
        st.markdown(f"""
        <div class="card">
            <p class="metric-label">Est. Incremental Revenue</p>
            <p class="metric-value">${inc_revenue:,.0f}</p>
            <p style="margin:2px 0 0 0; font-size:0.85rem; color:#717182;">
                28% of total revenue
            </p>
        </div>
        """, unsafe_allow_html=True)

    with kpi4:
        st.markdown(f"""
        <div class="card">
            <p class="metric-label">Optimizer Status</p>
            <p class="metric-value" style="font-size:1.2rem;">{opt_icon} {opt_status.capitalize()}</p>
            <p style="margin:2px 0 0 0; font-size:0.8rem; color:#717182;">
                Last run: {last_run}
            </p>
            <p style="margin:2px 0 0 0; font-size:0.8rem; color:#717182;">
                {active_camps} active campaign{'s' if active_camps != 1 else ''}
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # Budget Allocation — horizontal stacked bar + per-channel table
    # -----------------------------------------------------------------------
    st.markdown("### 💰 Budget Allocation by Channel")

    alloc_col, table_col = st.columns([2, 1])

    with alloc_col:
        # Stacked bar: actual spend vs allocated budget per channel
        fig = go.Figure()

        channels_sorted = sorted(channel_data, key=lambda c: c["budget"], reverse=True)
        names = [c["name"] for c in channels_sorted]
        spends = [c["spent"] for c in channels_sorted]
        remainders = [max(0, c["budget"] - c["spent"]) for c in channels_sorted]
        colors = [c["color"] for c in channels_sorted]

        for i, ch in enumerate(channels_sorted):
            fig.add_trace(go.Bar(
                name=ch["name"] + " (spent)",
                y=[ch["name"]],
                x=[ch["spent"]],
                orientation="h",
                marker_color=ch["color"],
                showlegend=False,
                hovertemplate=f"<b>{ch['name']}</b><br>Spent: $%{{x:,.0f}}<extra></extra>",
            ))
            remaining = max(0, ch["budget"] - ch["spent"])
            fig.add_trace(go.Bar(
                name=ch["name"] + " (remaining)",
                y=[ch["name"]],
                x=[remaining],
                orientation="h",
                marker_color=ch["color"],
                marker_opacity=0.25,
                showlegend=False,
                hovertemplate=f"<b>{ch['name']}</b><br>Remaining: $%{{x:,.0f}}<extra></extra>",
            ))

        fig.update_layout(
            barmode="stack",
            height=max(200, len(channels_sorted) * 52 + 40),
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(color="#1a1a1a"),
            yaxis=dict(autorange="reversed"),
            xaxis=dict(tickprefix="$", gridcolor="#F0F0F0"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with table_col:
        st.markdown("##### Channel KPIs")
        for ch in channels_sorted:
            trend_color = "#22C55E" if ch["roas_trend"] >= 0 else "#EF4444"
            trend_arrow = "▲" if ch["roas_trend"] >= 0 else "▼"
            pacing_pct = (ch["spent"] / ch["budget"] * 100) if ch["budget"] > 0 else 0
            pace_color = "#EF4444" if pacing_pct > 110 else "#F59E0B" if pacing_pct < 80 else "#22C55E"

            name_col, pace_col = st.columns([3, 1])
            with name_col:
                st.markdown(f"**{ch['icon']} {ch['name']}**")
            with pace_col:
                st.markdown(
                    f"<div style='text-align:right; font-size:0.75rem; color:{pace_color};'>{pacing_pct:.0f}% pacing</div>",
                    unsafe_allow_html=True,
                )
            spent_col, roas_col = st.columns([2, 2])
            with spent_col:
                st.markdown(f"<span style='font-size:0.8rem; color:#717182;'>${ch['spent']:,.0f} spent</span>", unsafe_allow_html=True)
            with roas_col:
                st.markdown(
                    f"<div style='text-align:right; font-size:0.8rem; color:#717182;'>ROAS {ch['roas']:.2f}x <span style='color:{trend_color};'>{trend_arrow}{abs(ch['roas_trend']):.1f}%</span></div>",
                    unsafe_allow_html=True,
                )
            st.markdown("<hr style='margin:4px 0; border-color:#F0F0F0;'>", unsafe_allow_html=True)

        # View all channels
        if st.button("View campaign details →", key="home_view_campaigns", use_container_width=True):
            st.session_state.current_page = "campaigns"
            st.rerun()

    st.markdown("---")

    # -----------------------------------------------------------------------
    # Two-column: Pacing alerts  |  Recent changes
    # -----------------------------------------------------------------------
    alert_col, changes_col = st.columns([1, 1])

    with alert_col:
        st.markdown("### ⚡ Pacing Alerts")
        _render_pacing_alerts(channel_data, data_service)

    with changes_col:
        st.markdown("### 🔄 What's Changed")
        _render_recent_changes(decisions)

    st.markdown("---")

    # -----------------------------------------------------------------------
    # Pending recommendations preview
    # -----------------------------------------------------------------------
    recs = []
    try:
        recs = data_service.get_pending_recommendations()
    except Exception:
        pass

    if recs:
        pending_count = len(recs)
        st.markdown(f"### ✓ Actions Waiting ({pending_count})")

        rec_cols = st.columns(min(pending_count, 3))
        for i, rec in enumerate(recs[:3]):
            with rec_cols[i % 3]:
                confidence = rec.get("confidence", 0)
                conf_color = "#22C55E" if confidence >= 0.8 else "#F59E0B" if confidence >= 0.6 else "#9CA3AF"
                st.markdown(f"""
                <div class="recommendation-card">
                    <p style="margin:0; font-size:0.85rem; font-weight:600;">{rec['title']}</p>
                    <p style="margin:4px 0 0 0; font-size:0.8rem; color:#717182;">
                        {rec.get('expected_impact', '')}
                    </p>
                    <p style="margin:6px 0 0 0; font-size:0.75rem; color:{conf_color}; font-weight:600;">
                        ⚡ {confidence:.0%} confidence
                    </p>
                </div>
                """, unsafe_allow_html=True)

        if st.button(f"Review {pending_count} pending action{'s' if pending_count != 1 else ''} →",
                     key="home_view_recs", type="primary"):
            st.session_state.current_page = "recommendations"
            st.rerun()


# ---------------------------------------------------------------------------
# Sub-components
# ---------------------------------------------------------------------------

def _render_pacing_alerts(channel_data: list, data_service: DataService) -> None:
    """Show channels that are over/under pacing by >15%."""
    alerts = []
    for ch in channel_data:
        pacing_pct = (ch["spent"] / ch["budget"]) if ch["budget"] > 0 else 0
        if pacing_pct > 1.15:
            alerts.append({"channel": ch, "type": "over", "pacing": pacing_pct})
        elif pacing_pct < 0.75:
            alerts.append({"channel": ch, "type": "under", "pacing": pacing_pct})

    if not alerts:
        st.success("✓ All channels pacing normally")
    else:
        for alert in alerts:
            ch = alert["channel"]
            pct = alert["pacing"] * 100
            if alert["type"] == "over":
                icon, msg, color = "🔴", f"overpacing at {pct:.0f}%", "#EF4444"
            else:
                icon, msg, color = "🟡", f"underpacing at {pct:.0f}%", "#F59E0B"

            name_col, msg_col = st.columns([2, 2])
            with name_col:
                st.markdown(f"<span style='font-weight:600; font-size:0.9rem;'>{icon} {ch['name']}</span>", unsafe_allow_html=True)
            with msg_col:
                st.markdown(f"<div style='text-align:right; font-size:0.8rem; color:{color}; font-weight:600;'>{msg}</div>", unsafe_allow_html=True)
            st.markdown(f"<p style='margin:0 0 8px 0; font-size:0.8rem; color:#717182; border-left:3px solid {color}; padding-left:8px; background:{color}10;'>Spent ${ch['spent']:,.0f} of ${ch['budget']:,.0f}</p>", unsafe_allow_html=True)

        if st.button("Adjust pacing →", key="home_adjust_pacing", use_container_width=True):
            st.session_state.current_page = "recommendations"
            st.rerun()


def _render_recent_changes(decisions: list) -> None:
    """Render optimizer changes from the last 24 hours."""
    if not decisions:
        st.info("No changes in the last 24 hours.")
        return

    for d in decisions:
        ts = d.get("timestamp")
        if isinstance(ts, datetime):
            time_str = ts.strftime("%H:%M")
        else:
            time_str = str(ts)[:16] if ts else "—"

        impact = d.get("impact", 0)
        impact_color = "#22C55E" if impact > 0 else "#EF4444" if impact < 0 else "#717182"
        impact_str = f"{'+' if impact >= 0 else ''}{impact:.1f}%"

        explanation = d.get("explanation") or ""
        short_exp = explanation.split(".")[0] + "." if explanation else ""

        left_col, right_col = st.columns([5, 1])
        with left_col:
            st.markdown(
                f"**{d.get('description', '—')}**  \n"
                f"<span style='font-size:0.75rem; color:#717182;'>"
                f"{d.get('campaign_name', '')} · {time_str}</span>"
                + (f"  \n<span style='font-size:0.75rem; color:#717182;'>{short_exp}</span>" if short_exp else ""),
                unsafe_allow_html=True,
            )
        with right_col:
            st.markdown(
                f"<div style='text-align:right; font-weight:600; color:{impact_color}; font-size:0.85rem;'>{impact_str}</div>",
                unsafe_allow_html=True,
            )
        st.divider()
