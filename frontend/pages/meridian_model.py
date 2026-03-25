"""
Meridian Model Management Page

Monitor, train, and compare Meridian Bayesian MMM models:
  - Model status per campaign (trained / data ready / insufficient)
  - One-click training trigger
  - Side-by-side comparison: rule-based vs Meridian
  - Data health dashboard
"""

import streamlit as st
import sys
from pathlib import Path
import plotly.graph_objects as go
import pandas as pd

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from frontend.services.data_service import DataService

CHANNEL_COLORS = {
    "Google Search": "#4285F4",
    "Meta Social": "#1877F2",
    "Google Display": "#F59E0B",
    "Meta Display": "#8B5CF6",
    "The Trade Desk Display": "#00A98F",
    "Programmatic": "#00A98F",
    "Video": "#9b4819",
    "Email": "#8B5CF6",
    "Affiliate": "#EF4444",
}
DEFAULT_COLOR = "#717182"


def render():
    """Render the Meridian Model Management page."""
    data_service = DataService()

    st.markdown("## Meridian Model Management")
    st.markdown(
        "Monitor Meridian Bayesian MMM training, compare with rule-based estimates, "
        "and inspect the data feeding the model."
    )

    # -----------------------------------------------------------------
    # Section 1 — Model Status
    # -----------------------------------------------------------------
    st.markdown("### Model Status")

    campaigns = _get_campaigns(data_service)
    campaign_items = [{"id": None, "name": "Cross-Campaign (all data)"}] + campaigns

    status_cols = st.columns(min(len(campaign_items), 4))
    for i, camp in enumerate(campaign_items):
        cid = camp.get("id")
        status = _get_training_status(cid)
        data_weeks = _get_data_weeks(cid)

        trained = status.get("trained", False)
        if trained:
            color, badge, icon = "#065F46", "#ECFDF5", "checkmark"
            label = "Trained"
            detail = f"Last: {status.get('trained_at', 'unknown')[:10]}"
            diag = status.get("diagnostics", {})
            if diag:
                detail += f" · R-hat: {diag.get('max_rhat', '?')}"
        elif data_weeks >= 12:
            color, badge, icon = "#92400E", "#FEF3C7", "hourglass"
            label = "Ready to Train"
            detail = f"{data_weeks} weeks available"
        else:
            color, badge, icon = "#6B7280", "#F3F4F6", "cross"
            label = "Insufficient Data"
            detail = f"{data_weeks}/12 weeks"

        with status_cols[i % len(status_cols)]:
            st.markdown(f"""
            <div style="padding:14px; border:1px solid #E5E7EB; border-radius:10px;
                        border-left:4px solid {color}; background:{badge};">
                <p style="margin:0; font-size:0.8rem; font-weight:700; color:#1a1a1a;">
                    {camp['name'][:25]}
                </p>
                <p style="margin:4px 0 0; font-size:1rem; font-weight:600; color:{color};">
                    {label}
                </p>
                <p style="margin:2px 0 0; font-size:0.72rem; color:#717182;">{detail}</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # -----------------------------------------------------------------
    # Section 2 — Train Model
    # -----------------------------------------------------------------
    st.markdown("### Train Model")

    train_col1, train_col2, _ = st.columns([2, 2, 4])
    with train_col1:
        options = {f"{c['name']}": c.get("id") for c in campaign_items}
        selected_name = st.selectbox("Campaign", list(options.keys()), key="meridian_train_select")
        selected_cid = options[selected_name]

    with train_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Train Now", type="primary", key="meridian_train_btn"):
            with st.spinner("Training Meridian model (this may take several minutes)..."):
                result = _trigger_training(selected_cid)
                if result.get("success"):
                    st.success(
                        f"Model trained successfully. "
                        f"R-hat: {result.get('diagnostics', {}).get('max_rhat', 'N/A')}"
                    )
                else:
                    error = result.get("error", "Unknown error")
                    if "not installed" in error.lower():
                        st.warning(
                            "google-meridian is not installed. "
                            "Install with: `pip install google-meridian`"
                        )
                    elif "Insufficient" in error:
                        st.info(f"Not enough data: {error}")
                    else:
                        st.error(f"Training failed: {error}")

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 3 — Model Comparison
    # -----------------------------------------------------------------
    st.markdown("### Rule-Based vs Meridian Comparison")
    st.caption("Compare channel-level estimates from both engines side by side.")

    compare_cid = selected_cid
    rule_based = _get_rule_based_summary(compare_cid, data_service)
    meridian = _get_meridian_summary(compare_cid)

    if rule_based and meridian and meridian.get("model_source") == "meridian":
        _render_comparison(rule_based, meridian)
    elif rule_based:
        st.info(
            "No Meridian model available yet. Train a model above to see the comparison. "
            "Showing rule-based results only."
        )
        _render_single_summary(rule_based, "Rule-Based")
    else:
        st.info("No data available for comparison.")

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 4 — Data Health
    # -----------------------------------------------------------------
    st.markdown("### Data Health")
    st.caption("Weekly aggregated spend and revenue that feeds into Meridian training.")

    df = _load_meridian_data(compare_cid)
    if df is not None and not df.empty:
        _render_data_health(df)
    else:
        st.info("No metric data available. Run `python scripts/create_sample_data.py` to generate sample data.")


# =====================================================================
# Helpers
# =====================================================================


def _get_campaigns(data_service):
    try:
        return data_service.get_campaigns() or []
    except Exception:
        return []


def _get_training_status(campaign_id):
    try:
        from src.bandit_ads.meridian_trainer import MeridianTrainer
        return MeridianTrainer().get_training_status(campaign_id)
    except Exception:
        return {"trained": False}


def _get_data_weeks(campaign_id):
    try:
        from src.bandit_ads.meridian_data import extract_meridian_dataset
        df = extract_meridian_dataset(campaign_id=campaign_id, min_weeks=1)
        return len(df) if df is not None else 0
    except Exception:
        return 0


def _trigger_training(campaign_id):
    try:
        from src.bandit_ads.meridian_trainer import MeridianTrainer
        trainer = MeridianTrainer()
        result = trainer.train(campaign_id=campaign_id)
        return result.to_dict()
    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_rule_based_summary(campaign_id, data_service):
    try:
        from src.bandit_ads.mmm_insights import MMMInsightsEngine
        engine = MMMInsightsEngine()
        return engine.get_cross_platform_summary(days=200)
    except Exception:
        return None


def _get_meridian_summary(campaign_id):
    try:
        from src.bandit_ads.meridian_insights import MeridianInsightsEngine
        engine = MeridianInsightsEngine(campaign_id=campaign_id)
        if engine.model_status == "meridian":
            return engine.get_cross_platform_summary(days=200)
        return None
    except Exception:
        return None


def _load_meridian_data(campaign_id):
    try:
        from src.bandit_ads.meridian_data import extract_meridian_dataset
        return extract_meridian_dataset(campaign_id=campaign_id, min_weeks=1)
    except Exception:
        return None


def _render_comparison(rule_based, meridian):
    """Render side-by-side comparison table."""
    rb_channels = {c["channel"]: c for c in rule_based.get("channels", [])}
    m_channels = {c["channel"]: c for c in meridian.get("channels", [])}
    all_channels = sorted(set(list(rb_channels.keys()) + list(m_channels.keys())))

    rows = []
    for ch in all_channels:
        rb = rb_channels.get(ch, {})
        m = m_channels.get(ch, {})
        row = {
            "Channel": ch,
            "Rule-Based ROAS": f"{rb.get('roas', 0):.2f}x" if rb else "—",
            "Meridian ROAS": f"{m.get('roas', 0):.2f}x" if m else "—",
        }
        if m.get("roas_lower") and m.get("roas_upper"):
            row["Meridian 95% CI"] = f"{m['roas_lower']:.2f}–{m['roas_upper']:.2f}x"
        else:
            row["Meridian 95% CI"] = "—"
        row["Rule-Based Saturation"] = f"{rb.get('saturation_score', 0):.0%}" if rb else "—"
        row["Meridian Saturation"] = f"{m.get('saturation_score', 0):.0%}" if m else "—"
        rows.append(row)

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Blended ROAS comparison
    rb_roas = rule_based.get("blended_roas", 0)
    m_roas = meridian.get("blended_roas", 0)
    diff = m_roas - rb_roas
    color = "#22C55E" if abs(diff) < 0.5 else "#F59E0B"
    st.markdown(f"""
    <div style="padding:10px 16px; background:#f9f9f9; border-radius:8px; margin-top:12px;">
        Blended ROAS — Rule-Based: <b>{rb_roas:.2f}x</b> · Meridian: <b>{m_roas:.2f}x</b>
        <span style="color:{color}; margin-left:8px;">
            (diff: {'+' if diff >= 0 else ''}{diff:.2f}x)
        </span>
    </div>
    """, unsafe_allow_html=True)


def _render_single_summary(data, label):
    """Render a single engine's channel summary."""
    channels = data.get("channels", [])
    if not channels:
        return

    rows = []
    for c in channels:
        rows.append({
            "Channel": c["channel"],
            f"{label} ROAS": f"{c.get('roas', 0):.2f}x",
            "Spend": f"${c.get('spend', 0):,.0f}",
            "Revenue": f"${c.get('revenue', 0):,.0f}",
            "Saturation": f"{c.get('saturation_score', 0):.0%}",
            "Recommendation": c.get("recommendation", ""),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_data_health(df):
    """Render data health charts."""
    # Data sufficiency indicator
    n_weeks = len(df)
    spend_cols = [c for c in df.columns if c.startswith("spend_")]
    n_channels = len(spend_cols)
    total_spend = sum(df[c].sum() for c in spend_cols)

    s1, s2, s3 = st.columns(3)
    with s1:
        color = "#22C55E" if n_weeks >= 12 else "#F59E0B" if n_weeks >= 8 else "#EF4444"
        st.markdown(f"""
        <div class="card" style="text-align:center;">
            <p style="margin:0; font-size:0.8rem; color:#717182;">Weeks of Data</p>
            <p style="margin:4px 0 0; font-size:1.6rem; font-weight:600; color:{color};">{n_weeks}</p>
            <p style="margin:0; font-size:0.7rem; color:#717182;">{'Sufficient' if n_weeks >= 12 else f'Need {12 - n_weeks} more'}</p>
        </div>
        """, unsafe_allow_html=True)
    with s2:
        st.markdown(f"""
        <div class="card" style="text-align:center;">
            <p style="margin:0; font-size:0.8rem; color:#717182;">Active Channels</p>
            <p style="margin:4px 0 0; font-size:1.6rem; font-weight:600;">{n_channels}</p>
        </div>
        """, unsafe_allow_html=True)
    with s3:
        st.markdown(f"""
        <div class="card" style="text-align:center;">
            <p style="margin:0; font-size:0.8rem; color:#717182;">Total Spend</p>
            <p style="margin:4px 0 0; font-size:1.6rem; font-weight:600;">${total_spend:,.0f}</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Weekly spend time series
    st.markdown("#### Weekly Spend by Channel")
    fig = go.Figure()
    for col in spend_cols:
        ch_name = col.replace("spend_", "").replace("_", " ").title()
        color = CHANNEL_COLORS.get(ch_name, DEFAULT_COLOR)
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[col],
            mode="lines", name=ch_name,
            line=dict(color=color, width=2),
            stackgroup="one",
        ))
    fig.update_layout(
        height=350,
        margin=dict(t=20, b=40, l=20, r=20),
        paper_bgcolor="white", plot_bgcolor="white",
        legend=dict(orientation="h", y=-0.2),
        xaxis=dict(title="Week", gridcolor="#F0F0F0"),
        yaxis=dict(title="Spend ($)", tickprefix="$", gridcolor="#F0F0F0"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Weekly revenue
    st.markdown("#### Weekly Revenue (KPI)")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=df["date"], y=df["revenue"],
        mode="lines+markers", name="Revenue",
        line=dict(color="#9b4819", width=2),
        marker=dict(size=4),
    ))
    fig2.update_layout(
        height=250,
        margin=dict(t=20, b=40, l=20, r=20),
        paper_bgcolor="white", plot_bgcolor="white",
        showlegend=False,
        xaxis=dict(title="Week", gridcolor="#F0F0F0"),
        yaxis=dict(title="Revenue ($)", tickprefix="$", gridcolor="#F0F0F0"),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Raw data expander
    with st.expander("View raw weekly data"):
        display_df = df.copy()
        display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
