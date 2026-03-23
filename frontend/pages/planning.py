"""
Planning & Forecasting Page

Two sections:
  A. Budget Scenario Planner — interactive sliders to test what-if reallocations
  B. ROAS Forecasting — historical + projected ROAS with confidence bands
"""

import streamlit as st
import sys
from pathlib import Path
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from frontend.services.data_service import DataService
from frontend.components.loading import render_error_message


IPSA_COLORS = ["#9b4819", "#bd8f53", "#4285F4", "#1877F2", "#00A98F", "#22C55E"]


def render():
    """Render the Planning & Forecasting page."""
    data_service = DataService()

    st.markdown("## 📈 Planning & Forecasting")
    st.markdown(
        "Simulate budget reallocation scenarios with causal MMM projections, "
        "and forecast ROAS forward using Thompson Sampling posterior uncertainty bounds."
    )

    # -----------------------------------------------------------------------
    # Campaign selector + horizon
    # -----------------------------------------------------------------------
    campaigns = _get_campaigns(data_service)
    if not campaigns:
        st.info("No active campaigns found. Create a campaign to use the planner.")
        return

    top_col1, top_col2, top_col3 = st.columns([2, 1, 3])
    with top_col1:
        campaign_names = [c["name"] for c in campaigns]
        selected_name = st.selectbox("Campaign", campaign_names, key="plan_campaign")
        selected = next(c for c in campaigns if c["name"] == selected_name)
        campaign_id = selected["id"]

    with top_col2:
        horizon = st.selectbox(
            "Horizon",
            options=[7, 14, 30, 60, 90],
            index=2,
            format_func=lambda x: f"{x} days",
            key="plan_horizon",
        )

    st.markdown("---")

    # -----------------------------------------------------------------------
    # Section A — Budget Scenario Planner
    # -----------------------------------------------------------------------
    st.markdown("### A. Budget Scenario Planner")
    st.markdown(
        "Adjust the daily budget per channel using the sliders. "
        "IPSA will instantly project the impact on ROAS and revenue."
    )

    forecast_data = data_service.get_forecast(campaign_id, horizon)
    channels_forecast = forecast_data.get("channels", {})
    channels = list(channels_forecast.keys())

    if not channels:
        st.warning("No channel data available for this campaign.")
    else:
        # Build current spend from forecast (first day's projected spend as baseline)
        current_budgets: dict = {}
        for ch, data in channels_forecast.items():
            spends = data.get("spend_projected", [1000])
            current_budgets[ch] = round(spends[0] if spends else 1000, 0)

        st.markdown("#### Daily Budget per Channel")
        slider_cols = st.columns(min(len(channels), 3))
        proposed_budgets: dict = {}

        for i, ch in enumerate(channels):
            current = current_budgets[ch]
            col = slider_cols[i % len(slider_cols)]
            with col:
                new_val = st.slider(
                    ch,
                    min_value=0,
                    max_value=int(current * 3) or 3000,
                    value=int(current),
                    step=100,
                    key=f"slider_{ch}",
                    format="$%d",
                )
                proposed_budgets[ch] = float(new_val)
                # Show change indicator
                delta_pct = ((new_val - current) / current * 100) if current > 0 else 0
                color = "#22C55E" if delta_pct > 0 else "#EF4444" if delta_pct < 0 else "#717182"
                sign = "+" if delta_pct > 0 else ""
                st.markdown(
                    f"<p style='text-align:center; font-size:0.8rem; color:{color}; margin:0;'>"
                    f"{sign}{delta_pct:.0f}% vs current</p>",
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)

        # Simulate
        simulation = data_service.simulate_scenario(campaign_id, proposed_budgets, horizon)

        current_plan = simulation.get("current", {})
        proposed_plan = simulation.get("proposed", {})
        delta = simulation.get("delta", {})

        # Side-by-side comparison
        st.markdown("#### Projected Outcome")
        c1, c2, c3 = st.columns(3)

        with c1:
            _compare_metric(
                "Total Spend",
                f"${current_plan.get('total_spend', 0):,.0f}",
                f"${proposed_plan.get('total_spend', 0):,.0f}",
                delta.get("total_spend", 0),
                prefix="$",
            )
        with c2:
            _compare_metric(
                "Total Revenue",
                f"${current_plan.get('total_revenue', 0):,.0f}",
                f"${proposed_plan.get('total_revenue', 0):,.0f}",
                delta.get("total_revenue", 0),
                prefix="$",
            )
        with c3:
            _compare_metric(
                "Blended ROAS",
                f"{current_plan.get('blended_roas', 0):.2f}x",
                f"{proposed_plan.get('blended_roas', 0):.2f}x",
                delta.get("roas_change_pct", 0),
                suffix="%",
                is_pct=True,
            )

        # Per-channel table
        current_chs = current_plan.get("channels", {})
        proposed_chs = proposed_plan.get("channels", {})

        if current_chs and proposed_chs:
            st.markdown("##### Channel Breakdown")
            rows = []
            for ch in channels:
                cur = current_chs.get(ch, {})
                prop = proposed_chs.get(ch, {})
                rows.append({
                    "Channel": ch,
                    "Current spend": f"${cur.get('total_spend', 0):,.0f}",
                    "Proposed spend": f"${prop.get('total_spend', 0):,.0f}",
                    "Current ROAS": f"{cur.get('avg_roas', 0):.2f}x",
                    "Projected ROAS": f"{prop.get('avg_roas', 0):.2f}x",
                    "Revenue delta": f"${prop.get('total_revenue', 0) - cur.get('total_revenue', 0):+,.0f}",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Apply as recommendation
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✓ Apply this plan as a Recommendation", type="primary"):
            data_service.create_scenario_recommendation(campaign_id, proposed_budgets, horizon)
            st.success(
                "📋 Plan saved as a pending recommendation. "
                "Review it in the Actions page before applying."
            )
            if st.button("→ Go to Action Center", key="plan_goto_actions"):
                st.session_state.current_page = "recommendations"
                st.rerun()

    st.markdown("---")

    # -----------------------------------------------------------------------
    # Section B — ROAS Forecast Chart
    # -----------------------------------------------------------------------
    st.markdown("### B. ROAS Forecast")
    st.markdown(
        "Solid lines = historical ROAS · Dashed lines = projected · "
        "Shaded bands = 95% confidence interval"
    )

    fig = _build_forecast_chart(forecast_data)
    st.plotly_chart(fig, use_container_width=True)

    # Seasonality note
    note = forecast_data.get("mmm_seasonality_note")
    if note:
        st.caption(f"ℹ️ {note}")

    # Per-channel ROAS summary
    if channels_forecast:
        st.markdown("##### Channel forecast summary")
        summary_rows = []
        for ch, data in channels_forecast.items():
            means = data.get("roas_mean", [])
            if means:
                summary_rows.append({
                    "Channel": ch,
                    f"Avg projected ROAS ({horizon}d)": f"{sum(means)/len(means):.2f}x",
                    "Projected high": f"{max(means):.2f}x",
                    "Projected low": f"{min(means):.2f}x",
                })
        if summary_rows:
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    st.markdown("---")

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------
    st.markdown("### ⬇ Export Campaign Reports")
    exp_col1, exp_col2, exp_col3 = st.columns(3)
    with exp_col1:
        if st.button("📊 Download Metrics CSV", use_container_width=True, key="plan_exp_metrics"):
            raw = data_service.export_csv(campaign_id, export_type="metrics")
            if raw:
                st.download_button(
                    "Save Metrics CSV",
                    data=raw,
                    file_name=f"campaign_{campaign_id}_metrics.csv",
                    mime="text/csv",
                    key="plan_dl_metrics",
                )
            else:
                st.error("Export failed — is the API running?")
    with exp_col2:
        if st.button("📋 Download Allocation CSV", use_container_width=True, key="plan_exp_alloc"):
            raw = data_service.export_csv(campaign_id, export_type="allocation")
            if raw:
                st.download_button(
                    "Save Allocation CSV",
                    data=raw,
                    file_name=f"campaign_{campaign_id}_allocation.csv",
                    mime="text/csv",
                    key="plan_dl_alloc",
                )
            else:
                st.error("Export failed — is the API running?")
    with exp_col3:
        if st.button("📄 Download PDF Report", use_container_width=True, key="plan_exp_pdf"):
            with st.spinner("Generating PDF..."):
                raw = data_service.export_pdf(campaign_id)
            if raw:
                st.download_button(
                    "Save PDF Report",
                    data=raw,
                    file_name=f"ipsa_campaign_{campaign_id}.pdf",
                    mime="application/pdf",
                    key="plan_dl_pdf",
                )
            else:
                st.error("PDF export failed — is the API running?")


# ---------------------------------------------------------------------------
# Helper components
# ---------------------------------------------------------------------------

def _compare_metric(
    label: str,
    current_val: str,
    proposed_val: str,
    delta: float,
    prefix: str = "",
    suffix: str = "",
    is_pct: bool = False,
) -> None:
    """Render a side-by-side metric comparison card."""
    if is_pct:
        delta_str = f"{'+' if delta >= 0 else ''}{delta:.1f}{suffix}"
    else:
        delta_str = f"{'+' if delta >= 0 else ''}${abs(delta):,.0f}"

    color = "#22C55E" if delta > 0 else "#EF4444" if delta < 0 else "#717182"

    st.markdown(f"""
    <div class="card" style="text-align: center;">
        <p style="margin: 0; font-size: 0.8rem; color: #717182;">{label}</p>
        <div style="display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 8px;">
            <div>
                <p style="margin: 0; font-size: 0.75rem; color: #717182;">Current</p>
                <p style="margin: 0; font-size: 1.1rem; font-weight: 500;">{current_val}</p>
            </div>
            <span style="font-size: 1.2rem; color: #717182;">→</span>
            <div>
                <p style="margin: 0; font-size: 0.75rem; color: #717182;">Proposed</p>
                <p style="margin: 0; font-size: 1.1rem; font-weight: 700; color: {color};">{proposed_val}</p>
            </div>
        </div>
        <p style="margin: 6px 0 0 0; font-size: 0.85rem; font-weight: 600; color: {color};">
            {delta_str}
        </p>
    </div>
    """, unsafe_allow_html=True)


def _build_forecast_chart(forecast_data: dict) -> go.Figure:
    """Build a Plotly figure showing historical + projected ROAS per channel."""
    fig = go.Figure()

    history = forecast_data.get("history", {})
    channels_fcast = forecast_data.get("channels", {})

    all_channels = list(set(list(history.keys()) + list(channels_fcast.keys())))

    for i, ch in enumerate(all_channels):
        color = IPSA_COLORS[i % len(IPSA_COLORS)]

        # Historical (solid)
        hist = history.get(ch, {})
        if hist.get("dates") and hist.get("roas"):
            fig.add_trace(go.Scatter(
                x=hist["dates"],
                y=hist["roas"],
                mode="lines",
                name=f"{ch} (hist)",
                line=dict(color=color, width=2),
                showlegend=True,
            ))

        # Forecast (dashed + confidence band)
        fcast = channels_fcast.get(ch, {})
        if fcast.get("dates") and fcast.get("roas_mean"):
            dates = fcast["dates"]
            mean = fcast["roas_mean"]
            lower = fcast.get("roas_lower", mean)
            upper = fcast.get("roas_upper", mean)

            # Confidence band
            fig.add_trace(go.Scatter(
                x=dates + dates[::-1],
                y=upper + lower[::-1],
                fill="toself",
                fillcolor=f"rgba({_hex_to_rgb(color)},0.12)",
                line=dict(color="rgba(0,0,0,0)"),
                showlegend=False,
                hoverinfo="skip",
            ))

            # Projected mean
            fig.add_trace(go.Scatter(
                x=dates,
                y=mean,
                mode="lines",
                name=f"{ch} (forecast)",
                line=dict(color=color, width=2, dash="dash"),
                showlegend=True,
            ))

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="ROAS",
        height=420,
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#1a1a1a"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, font=dict(color="#1a1a1a")),
        margin=dict(t=20, b=80, l=40, r=20),
        yaxis=dict(gridcolor="#F0F0F0"),
        xaxis=dict(gridcolor="#F0F0F0"),
    )

    return fig


def _hex_to_rgb(hex_color: str) -> str:
    """Convert #RRGGBB to 'R,G,B' string for rgba()."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "100,100,100"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b}"


def _get_campaigns(data_service: DataService) -> list:
    try:
        return data_service.get_campaigns() or []
    except Exception:
        return []
