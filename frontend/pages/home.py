"""
Home Page — Budget Command Center
"""

import streamlit as st
from datetime import datetime, timedelta
import sys
from pathlib import Path
import plotly.graph_objects as go

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from frontend.components.loading import render_error_message, render_retry_button
from frontend.services.data_service import DataService

# Soft palette — terracotta family + warm neutrals
CHANNEL_PALETTE = ["#9b4819", "#bd8f53", "#6B7280", "#C4A882", "#D97757", "#A8B5C2"]

# Alert accent colours (left border)
ACCENT_COLORS = {
    "action needed": "#F59E0B",   # amber
    "opportunity":   "#22C55E",   # green
    "watch":         "#D97706",   # muted amber
    "info":          "#3B82F6",   # blue
}
# Badge pill bg + text (using background only — text colour via opacity)
BADGE_BG = {
    "action needed": "#FEF3C7",
    "opportunity":   "#DCFCE7",
    "watch":         "#FEF9C3",
    "info":          "#DBEAFE",
}


def _badge(label: str, css: str) -> str:
    return (
        f"<span style='{css} padding:2px 8px; border-radius:9999px; "
        f"font-size:0.68rem; font-weight:600;'>{label}</span>"
    )


def _section_label(text: str) -> None:
    st.markdown(
        f"<p style='margin:0 0 14px; font-size:0.72rem; font-weight:700; color:#9b4819; "
        f"text-transform:uppercase; letter-spacing:0.08em;'>{text}</p>",
        unsafe_allow_html=True,
    )


def _kpi_card(label, value, target_label, target_val, badge_label, badge_css, delta, delta_color, progress):
    bar_w   = min(100, max(0, progress * 100))
    bar_col = {"#166534": "#4ADE80", "#991B1B": "#F87171",
               "#1E40AF": "#60A5FA", "#6B7280": "#D1D5DB"}.get(delta_color, "#9b4819")
    badge_html = _badge(badge_label, badge_css)
    return f"""
<div style="background:white; border:1px solid #E5E7EB; border-radius:12px;
            padding:16px 18px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <p style="margin:0; font-size:0.75rem; color:#6B7280; font-weight:500;">{label}</p>
        {badge_html}
    </div>
    <p style="margin:0; font-size:2.1rem; font-weight:700; color:#111827; line-height:1.1;">{value}</p>
    <div style="background:#F3F4F6; border-radius:9999px; height:3px; margin:8px 0 0;">
        <div style="background:{bar_col}; width:{bar_w:.0f}%; height:3px; border-radius:9999px;"></div>
    </div>
    <hr style="border:none; border-top:1px solid #F3F4F6; margin:10px 0;">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size:0.74rem; color:#9CA3AF;">{target_label} {target_val}</span>
        <span style="font-size:0.74rem; color:{delta_color}; font-weight:600;">{delta}</span>
    </div>
</div>"""


def render(greeting: str):
    data_service = DataService()
    now = datetime.now()


    # ── Period picker ────────────────────────────────────────────────────────
    hdr_col, rng_col = st.columns([3, 1])
    with rng_col:
        time_range = st.selectbox(
            "Period",
            ["MTD", "QTD", "YTD", "FY"],
            format_func=lambda x: {"MTD": "Month to Date", "QTD": "Quarter to Date",
                                   "YTD": "Year to Date", "FY": "Fiscal Year"}.get(x, x),
            key="home_time_range", label_visibility="collapsed",
        )
    period_labels = {"MTD": "Month to Date", "QTD": "Quarter to Date",
                     "YTD": "Year to Date",  "FY": "Fiscal Year"}
    with hdr_col:
        st.markdown(
            f"<p style='margin:6px 0 0; font-size:0.72rem; font-weight:700; color:#9b4819; "
            f"text-transform:uppercase; letter-spacing:0.08em;'>"
            f"KPI GOALS · {period_labels.get(time_range, time_range)}</p>",
            unsafe_allow_html=True,
        )

    # ── Demo banner ──────────────────────────────────────────────────────────
    if data_service.use_mock and not st.session_state.get("demo_banner_dismissed", False):
        bc, btc, cc = st.columns([6, 2, 1])
        with bc:
            st.markdown(
                "<div style='padding:8px 0;'>"
                "<span style='font-size:0.9rem; font-weight:600; color:#9b4819;'>🎬 Demo mode</span>"
                "<span style='font-size:0.85rem; color:#6B7280; margin-left:8px;'>"
                "No live campaigns — explore a sample dataset.</span></div>",
                unsafe_allow_html=True,
            )
        with btc:
            if st.button("▶ Run Demo", key="home_run_demo", type="primary", use_container_width=True):
                st.session_state.current_page = "onboarding"
                st.session_state.onboarding_step = 1
                st.rerun()
        with cc:
            if st.button("✕", key="home_dismiss_demo", use_container_width=True):
                st.session_state.demo_banner_dismissed = True
                st.rerun()
        st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)

    # ── Fetch data ───────────────────────────────────────────────────────────
    try:
        budget_data      = data_service.get_brand_budget_overview(time_range)
        channel_data     = data_service.get_channel_splits(time_range)
        summary          = data_service.get_dashboard_summary()
        decisions        = data_service.get_recent_decisions(limit=5)
        optimizer_status = data_service.get_optimizer_status()
    except Exception as e:
        render_error_message(e, "loading dashboard data")
        render_retry_button(lambda: st.rerun(), "Retry")
        st.stop()

    spent        = budget_data["spent"]
    total        = budget_data["total_budget"]
    pacing       = budget_data["pacing_percent"]
    roas         = summary.get("avg_roas", 0)
    roas_trend   = summary.get("roas_trend", 0)
    inc_rev      = spent * roas * 0.28
    opt_status   = optimizer_status.get("status", "unknown")
    active_camps = optimizer_status.get("active_campaigns", 0)
    last_run     = optimizer_status.get("last_run", "—")

    # ── Model health bar ─────────────────────────────────────────────────────
    model_color  = "#22C55E" if opt_status == "running" else "#F59E0B"
    model_label  = "Model active" if opt_status == "running" else "Model idle"
    next_run_str = "in ~2 hrs" if opt_status == "running" else "pending"
    st.markdown(
        f"<div style='background:white; border:1px solid #E5E7EB; border-radius:10px; "
        f"padding:9px 16px; margin-bottom:16px; display:flex; align-items:center; gap:12px;'>"
        f"<span style='width:8px; height:8px; border-radius:50%; background:{model_color}; "
        f"display:inline-block; flex-shrink:0;'></span>"
        f"<span style='font-size:0.78rem; color:#374151; font-weight:500;'>{model_label}</span>"
        f"<span style='font-size:0.76rem; color:#9CA3AF; margin-left:4px;'>· Last run: {last_run} · Next: {next_run_str}</span>"
        f"<span style='margin-left:auto; font-size:0.76rem; color:#6B7280;'>"
        f"{active_camps} active campaign{'s' if active_camps != 1 else ''}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── KPI Cards ────────────────────────────────────────────────────────────
    # Spend
    if pacing > 1.1:
        sp_badge, sp_css = "Overpacing", "background:#FEF2F2; color:#991B1B;"
        sp_delta_c = "#991B1B"
    elif pacing < 0.85:
        sp_badge, sp_css = "Underpacing", "background:#FFF7ED; color:#92400E;"
        sp_delta_c = "#92400E"
    else:
        sp_badge, sp_css = "On track", "background:#F0FDF4; color:#166534;"
        sp_delta_c = "#166534"

    # ROAS
    roas_target = max(roas * 1.15, 3.0)
    if roas_trend >= 2:
        ro_badge, ro_css, ro_dc = "On track", "background:#F0FDF4; color:#166534;", "#166534"
    elif roas_trend >= 0:
        ro_badge, ro_css, ro_dc = "Building", "background:#EFF6FF; color:#1E40AF;", "#1E40AF"
    else:
        ro_badge, ro_css, ro_dc = "At risk",  "background:#FEF2F2; color:#991B1B;", "#991B1B"

    # Incremental rev
    inc_target = inc_rev * 1.2
    ir_badge, ir_css = ("On track", "background:#F0FDF4; color:#166534;") if inc_rev >= inc_target * 0.85 \
                  else ("Building",  "background:#EFF6FF; color:#1E40AF;")

    # Optimizer
    op_badge, op_css = ("Running", "background:#F0FDF4; color:#166534;") if opt_status == "running" \
                  else ("Idle",    "background:#F9FAFB; color:#6B7280;")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(_kpi_card(
            "Total Spend", f"${spent:,.0f}",
            "Budget", f"${total:,.0f}",
            sp_badge, sp_css,
            f"{'↑' if pacing >= 1 else '↓'} {pacing*100:.0f}% of budget used",
            sp_delta_c, pacing,
        ), unsafe_allow_html=True)
    with k2:
        t_arr = "↑" if roas_trend >= 0 else "↓"
        st.markdown(_kpi_card(
            "Blended ROAS", f"{roas:.2f}×",
            "Target", f"{roas_target:.1f}×",
            ro_badge, ro_css,
            f"{t_arr} {abs(roas_trend):.1f}% vs last week",
            ro_dc, min(1.0, roas / roas_target),
        ), unsafe_allow_html=True)
    with k3:
        st.markdown(_kpi_card(
            "Est. Incremental Revenue", f"${inc_rev:,.0f}",
            "Target", f"${inc_target:,.0f}",
            ir_badge, ir_css,
            "28% incremental fraction",
            "#6B7280", min(1.0, inc_rev / inc_target) if inc_target > 0 else 0.7,
        ), unsafe_allow_html=True)
    with k4:
        st.markdown(_kpi_card(
            "Optimizer", f"{active_camps} campaign{'s' if active_camps != 1 else ''}",
            "Mode", "Always-on",
            op_badge, op_css,
            f"Last run: {last_run}",
            "#6B7280", 1.0 if opt_status == "running" else 0.4,
        ), unsafe_allow_html=True)

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ── Budget Allocation ────────────────────────────────────────────────────
    _section_label("Budget Allocation by Channel")

    alloc_col, table_col = st.columns([2, 1])
    channels_sorted = sorted(channel_data, key=lambda c: c["budget"], reverse=True)

    with alloc_col:
        fig = go.Figure()
        for i, ch in enumerate(channels_sorted):
            col = CHANNEL_PALETTE[i % len(CHANNEL_PALETTE)]
            fig.add_trace(go.Bar(
                y=[ch["name"]], x=[ch["spent"]], orientation="h",
                marker_color=col, showlegend=False,
                hovertemplate=f"<b>{ch['name']}</b><br>Spent: $%{{x:,.0f}}<extra></extra>",
            ))
            fig.add_trace(go.Bar(
                y=[ch["name"]], x=[max(0, ch["budget"] - ch["spent"])],
                orientation="h", marker_color=col, marker_opacity=0.15,
                showlegend=False,
                hovertemplate=f"<b>{ch['name']}</b><br>Remaining: $%{{x:,.0f}}<extra></extra>",
            ))
        fig.update_layout(
            barmode="stack",
            height=max(160, len(channels_sorted) * 46 + 32),
            margin=dict(t=6, b=6, l=6, r=6),
            paper_bgcolor="white", plot_bgcolor="white",
            font=dict(color="#374151", size=11),
            yaxis=dict(autorange="reversed", tickfont=dict(size=11)),
            xaxis=dict(tickprefix="$", gridcolor="#F3F4F6", tickfont=dict(size=10)),
        )
        st.plotly_chart(fig, use_container_width=True)

    with table_col:
        st.markdown("<p style='font-size:0.72rem; font-weight:700; color:#6B7280; "
                    "text-transform:uppercase; letter-spacing:0.06em; margin:0 0 10px;'>"
                    "CHANNEL KPIs</p>", unsafe_allow_html=True)
        for i, ch in enumerate(channels_sorted):
            dot       = CHANNEL_PALETTE[i % len(CHANNEL_PALETTE)]
            tc        = "#166534" if ch["roas_trend"] >= 0 else "#991B1B"
            ta        = "↑" if ch["roas_trend"] >= 0 else "↓"
            pp        = (ch["spent"] / ch["budget"] * 100) if ch["budget"] > 0 else 0
            pc        = "#991B1B" if pp > 110 else "#92400E" if pp < 80 else "#166534"
            nc, pcc   = st.columns([3, 1])
            with nc:
                st.markdown(
                    f"<span style='font-size:0.81rem; font-weight:600; color:#111827;'>"
                    f"<span style='color:{dot};'>●</span> {ch['name']}</span>",
                    unsafe_allow_html=True)
            with pcc:
                st.markdown(
                    f"<div style='text-align:right; font-size:0.71rem; color:{pc}; "
                    f"font-weight:600;'>{pp:.0f}%</div>", unsafe_allow_html=True)
            sc, rc = st.columns([2, 2])
            with sc:
                st.markdown(f"<span style='font-size:0.75rem; color:#6B7280;'>"
                            f"${ch['spent']:,.0f}</span>", unsafe_allow_html=True)
            with rc:
                st.markdown(
                    f"<div style='text-align:right; font-size:0.75rem; color:#6B7280;'>"
                    f"ROAS {ch['roas']:.2f}× "
                    f"<span style='color:{tc};'>{ta}{abs(ch['roas_trend']):.1f}%</span></div>",
                    unsafe_allow_html=True)
            st.markdown("<hr style='margin:5px 0; border:none; border-top:1px solid #F3F4F6;'>",
                        unsafe_allow_html=True)
        if st.button("View campaign details →", key="home_view_campaigns", use_container_width=True):
            st.session_state.current_page = "campaigns"
            st.rerun()

    st.markdown("<hr style='border:none; border-top:1px solid #E5E7EB; margin:20px 0;'>",
                unsafe_allow_html=True)

    # ── Alerts & Anomalies ───────────────────────────────────────────────────
    _section_label("Alerts &amp; Anomalies")

    alerts = _build_alerts(channel_data, decisions, now)
    for a in alerts:
        _render_alert_tile(a, data_service)

    # ── Pending actions preview ──────────────────────────────────────────────
    recs = []
    try:
        recs = data_service.get_pending_recommendations()
    except Exception:
        pass

    if recs:
        st.markdown("<hr style='border:none; border-top:1px solid #E5E7EB; margin:20px 0;'>",
                    unsafe_allow_html=True)
        _section_label(f"Actions Waiting ({len(recs)})")
        rc = st.columns(min(len(recs), 3))
        for i, rec in enumerate(recs[:3]):
            conf      = rec.get("confidence", 0)
            conf_col  = "#166534" if conf >= 0.8 else "#92400E" if conf >= 0.6 else "#6B7280"
            with rc[i % 3]:
                st.markdown(f"""
                <div style="background:white; border:1px solid #E5E7EB; border-radius:10px;
                            padding:14px 16px; border-left:3px solid #9b4819;">
                    <p style="margin:0; font-size:0.84rem; font-weight:600; color:#111827;">{rec['title']}</p>
                    <p style="margin:6px 0 0; font-size:0.77rem; color:#6B7280;">{rec.get('expected_impact','')}</p>
                    <p style="margin:6px 0 0; font-size:0.73rem; color:{conf_col}; font-weight:600;">
                        {conf:.0%} confidence</p>
                </div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        if st.button(f"Review {len(recs)} pending action{'s' if len(recs)!=1 else ''} →",
                     key="home_view_recs", type="primary"):
            st.session_state.current_page = "recommendations"
            st.rerun()


# ── Alert helpers ────────────────────────────────────────────────────────────

def _ts(dt: datetime, now: datetime) -> str:
    delta = now - dt
    if delta.days == 0:
        return f"Today · {dt.strftime('%-I:%M %p')}"
    if delta.days == 1:
        return f"Yesterday"
    return dt.strftime("%b %-d")


def _build_alerts(channel_data: list, decisions: list, now: datetime) -> list:
    items = []
    ts_today = f"Today · {now.strftime('%-I:%M %p')}"

    for ch in channel_data:
        pacing = (ch["spent"] / ch["budget"]) if ch["budget"] > 0 else 0
        if pacing > 1.15:
            items.append({
                "tag": "action needed",
                "title": f"{ch['name']} is {pacing*100:.0f}% through budget — saturation risk",
                "body": (
                    f"${ch['spent']:,.0f} spent of ${ch['budget']:,.0f} allocated. "
                    f"Incremental return per additional dollar is declining. "
                    f"Consider pausing or reallocating to an under-spent channel."
                ),
                "cta": "Get a reallocation recommendation ↗",
                "cta_page": "recommendations",
                "ts_str": ts_today,
            })
        elif pacing < 0.75:
            items.append({
                "tag": "opportunity",
                "title": f"{ch['name']} has room to scale — saturation not yet reached",
                "body": (
                    f"Returning {ch.get('roas', 0):.2f}× ROAS on ${ch['spent']:,.0f} spend. "
                    f"Model shows headroom — saturation ceiling not yet reached."
                ),
                "cta": "View saturation curve ↗",
                "cta_page": "mmm_insights",
                "ts_str": ts_today,
            })

    for d in (decisions or []):
        ts     = d.get("timestamp")
        ts_str = _ts(ts, now) if isinstance(ts, datetime) else ts_today
        exp    = d.get("explanation") or d.get("description") or ""
        body   = exp[:180] + ("…" if len(exp) > 180 else "")
        impact = d.get("impact", 0)
        desc   = (d.get("description") or "").lower()

        if "saturation" in desc:
            tag, cta, cta_page = "watch",         "Explore reallocation options ↗", "mmm_insights"
        elif impact > 2:
            tag, cta, cta_page = "opportunity",   "View saturation curve ↗",        "mmm_insights"
        elif impact < -1:
            tag, cta, cta_page = "action needed", "Get a reallocation recommendation ↗", "recommendations"
        else:
            tag, cta, cta_page = "info",          None,                              None

        items.append({
            "tag": tag,
            "title": d.get("description", "Optimizer update"),
            "body": body,
            "cta": cta,
            "cta_page": cta_page,
            "ts_str": ts_str,
        })

    if not items:
        items.append({
            "tag": "info",
            "title": "Model refreshed — all sources synced",
            "body": "All data sources synced successfully. Next scheduled refresh in 5 days.",
            "cta": None,
            "cta_page": None,
            "ts_str": ts_today,
        })

    return items


def _render_alert_tile(item: dict, data_service: DataService) -> None:
    tag    = item.get("tag", "info")
    accent = ACCENT_COLORS.get(tag, "#D1D5DB")
    bg     = BADGE_BG.get(tag, "#F3F4F6")
    body_html = (
        f"<p style='margin:6px 0 12px; font-size:0.8rem; line-height:1.55; opacity:0.65;'>"
        f"{item['body']}</p>"
    ) if item.get("body") else "<div style='margin-bottom:10px;'></div>"

    # Tile header — rendered as one cohesive block
    st.markdown(f"""
<div style="border-left:3px solid {accent}; background:white;
            padding:14px 16px 0 16px; margin-bottom:0;">
    <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">
        <p style="margin:0; font-size:0.875rem; font-weight:500; line-height:1.4; flex:1;">{item['title']}</p>
        <p style="margin:0; font-size:0.72rem; opacity:0.45; white-space:nowrap; padding-top:2px;">{item['ts_str']}</p>
    </div>
    {body_html}
</div>""", unsafe_allow_html=True)

    # Button + badge row — directly follows the tile header
    has_cta = bool(item.get("cta") and item.get("cta_page"))
    safe_key = f"al_{tag[:3]}_{item['title'][:22].replace(' ','_').replace('/','')}"

    if has_cta:
        btn_col, badge_col = st.columns([4, 1])
        with btn_col:
            st.markdown(
                "<div style='background:white; border-left:3px solid "
                f"{accent}; padding:0 16px 14px 16px;'>",
                unsafe_allow_html=True,
            )
            if st.button(item["cta"], key=safe_key, use_container_width=True):
                st.session_state.current_page = item["cta_page"]
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with badge_col:
            st.markdown(
                f"<div style='background:white; height:100%; padding:0 4px 14px 0; "
                f"display:flex; align-items:flex-end; justify-content:flex-end;'>"
                f"<span style='background:{bg}; padding:2px 9px; border-radius:9999px; "
                f"font-size:0.68rem; font-weight:600; opacity:0.9;'>{tag}</span></div>",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            f"<div style='background:white; border-left:3px solid {accent}; "
            f"padding:0 16px 14px; display:flex; justify-content:flex-end;'>"
            f"<span style='background:{bg}; padding:2px 9px; border-radius:9999px; "
            f"font-size:0.68rem; font-weight:600; opacity:0.9;'>{tag}</span></div>",
            unsafe_allow_html=True,
        )

    # Bottom divider
    st.markdown(
        "<hr style='border:none; border-top:1px solid #F0ECE6; margin:0 0 4px;'>",
        unsafe_allow_html=True,
    )
