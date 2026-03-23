"""
MMM Insights Page

Holistic media mix model view across all platforms:
  - Channel efficiency matrix and spend vs ROAS scatter
  - Saturation curves — where diminishing returns set in
  - Optimal budget allocation recommendations
  - One-click "Apply recommendation" to Action Center
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

CHANNEL_COLORS = {
    "Google Search":  "#4285F4",
    "Meta Social":    "#1877F2",
    "Programmatic":   "#00A98F",
    "Video":          "#9b4819",
    "Display":        "#F59E0B",
    "Email":          "#8B5CF6",
    "Affiliate":      "#EF4444",
}
DEFAULT_COLOR = "#717182"


def render():
    """Render the MMM Insights page."""
    data_service = DataService()

    st.markdown("## 🧮 MMM Insights")
    st.markdown(
        "Media Mix Model analysis across all connected channels. "
        "Understand saturation, efficiency, and where incremental budget will drive the most return."
    )

    # Controls
    ctrl1, ctrl2, _ = st.columns([1, 1, 4])
    with ctrl1:
        days = st.selectbox("Lookback", [7, 14, 30, 60, 90], index=2, key="mmm_days",
                            format_func=lambda x: f"Last {x} days")
    with ctrl2:
        total_budget = st.number_input(
            "Optimise for budget ($)",
            min_value=0,
            value=0,
            step=1000,
            key="mmm_budget",
            help="Enter a total budget to see how to optimally allocate it. Leave 0 to use current spend.",
        )

    # Fetch data
    try:
        cross = data_service.get_mmm_cross_platform(days=days)
        channels = cross.get("channels", [])
        insights = cross.get("insights", [])
        total_spend = cross.get("total_spend", 0)
        total_revenue = cross.get("total_revenue", 0)
        blended_roas = cross.get("blended_roas", 0)

        saturation = data_service.get_mmm_saturation_curves(days=days)
        recs = data_service.get_mmm_budget_recommendations(
            total_budget=float(total_budget) if total_budget > 0 else None,
            days=days,
        )
    except Exception as e:
        render_error_message(e, "loading MMM insights")
        return

    # -----------------------------------------------------------------------
    # Section 1 — Portfolio KPIs
    # -----------------------------------------------------------------------
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div class="card" style="text-align:center;">
            <p style="margin:0; font-size:0.875rem; color:#717182;">Total Spend Analysed</p>
            <p style="margin:4px 0 0; font-size:1.8rem; font-weight:600;">${total_spend:,.0f}</p>
        </div>
        """, unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div class="card" style="text-align:center;">
            <p style="margin:0; font-size:0.875rem; color:#717182;">Total Revenue Attributed</p>
            <p style="margin:4px 0 0; font-size:1.8rem; font-weight:600;">${total_revenue:,.0f}</p>
        </div>
        """, unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div class="card" style="text-align:center;">
            <p style="margin:0; font-size:0.875rem; color:#717182;">Blended ROAS</p>
            <p style="margin:4px 0 0; font-size:1.8rem; font-weight:600;">{blended_roas:.2f}x</p>
        </div>
        """, unsafe_allow_html=True)
    with k4:
        uplift = recs.get("roas_uplift_pct", 0)
        color = "#22C55E" if uplift > 0 else "#717182"
        st.markdown(f"""
        <div class="card" style="text-align:center;">
            <p style="margin:0; font-size:0.875rem; color:#717182;">Potential ROAS Uplift</p>
            <p style="margin:4px 0 0; font-size:1.8rem; font-weight:600; color:{color};">+{uplift:.1f}%</p>
            <p style="margin:0; font-size:0.75rem; color:#717182;">via optimal reallocation</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Key insights callout
    if insights:
        with st.container():
            st.markdown("#### 💡 Key Insights")
            for ins in insights:
                st.markdown(f"- {ins}")
        st.markdown("<br>", unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # Section 2 — Channel Efficiency Matrix
    # -----------------------------------------------------------------------
    st.markdown("### Channel Efficiency Matrix")
    st.caption("Spend vs ROAS — bubble size = total revenue. Right of centre = efficient; top = high-ROAS.")

    if channels:
        df = pd.DataFrame(channels)
        avg_roas = df["roas"].mean()
        avg_spend = df["spend"].mean()

        fig = go.Figure()
        for _, row in df.iterrows():
            ch = row["channel"]
            color = CHANNEL_COLORS.get(ch, DEFAULT_COLOR)
            fig.add_trace(go.Scatter(
                x=[row["spend"]],
                y=[row["roas"]],
                mode="markers+text",
                name=ch,
                text=[ch],
                textposition="top center",
                marker=dict(
                    size=max(12, min(50, row["revenue"] / 1000)),
                    color=color,
                    opacity=0.85,
                    line=dict(width=1.5, color="white"),
                ),
                hovertemplate=(
                    f"<b>{ch}</b><br>"
                    f"Spend: $%{{x:,.0f}}<br>"
                    f"ROAS: %{{y:.2f}}x<br>"
                    f"Revenue: ${row['revenue']:,.0f}<br>"
                    f"Saturation: {row['saturation_score']:.0%}<br>"
                    f"<i>{row['recommendation']}</i>"
                    "<extra></extra>"
                ),
            ))

        # Quadrant lines
        fig.add_vline(x=avg_spend, line_dash="dot", line_color="#9CA3AF", line_width=1)
        fig.add_hline(y=avg_roas, line_dash="dot", line_color="#9CA3AF", line_width=1)

        fig.update_layout(
            height=400,
            showlegend=False,
            margin=dict(t=20, b=40, l=20, r=20),
            paper_bgcolor="white",
            plot_bgcolor="white",
            xaxis=dict(title="Total Spend ($)", tickprefix="$", gridcolor="#F0F0F0"),
            yaxis=dict(title="ROAS", ticksuffix="x", gridcolor="#F0F0F0"),
            annotations=[
                dict(x=avg_spend * 0.5, y=avg_roas * 1.05, text="🟡 Low spend, good ROAS",
                     showarrow=False, font=dict(size=10, color="#9CA3AF")),
                dict(x=avg_spend * 1.5, y=avg_roas * 1.05, text="🟢 High spend, good ROAS",
                     showarrow=False, font=dict(size=10, color="#9CA3AF")),
                dict(x=avg_spend * 0.5, y=avg_roas * 0.55, text="🔴 Low spend, low ROAS",
                     showarrow=False, font=dict(size=10, color="#9CA3AF")),
                dict(x=avg_spend * 1.5, y=avg_roas * 0.55, text="🟠 High spend, low ROAS",
                     showarrow=False, font=dict(size=10, color="#9CA3AF")),
            ],
        )
        st.plotly_chart(fig, use_container_width=True)

        # Channel table
        table_df = df[["channel", "spend", "revenue", "roas", "saturation_score",
                        "efficiency_score", "marginal_roas", "recommendation"]].copy()
        table_df.columns = ["Channel", "Spend ($)", "Revenue ($)", "ROAS",
                             "Saturation", "Efficiency", "Marginal ROAS", "Recommendation"]
        table_df["Spend ($)"] = table_df["Spend ($)"].apply(lambda x: f"${x:,.0f}")
        table_df["Revenue ($)"] = table_df["Revenue ($)"].apply(lambda x: f"${x:,.0f}")
        table_df["ROAS"] = table_df["ROAS"].apply(lambda x: f"{x:.2f}x")
        table_df["Saturation"] = table_df["Saturation"].apply(lambda x: f"{x:.0%}")
        table_df["Efficiency"] = table_df["Efficiency"].apply(lambda x: f"{x:.2f}x")
        table_df["Marginal ROAS"] = table_df["Marginal ROAS"].apply(lambda x: f"{x:.2f}x")
        st.dataframe(table_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # -----------------------------------------------------------------------
    # Section 3 — Saturation Curves
    # -----------------------------------------------------------------------
    st.markdown("### Saturation Curves")
    st.caption(
        "Each curve shows projected ROAS at different spend levels. "
        "The ● marker is current spend. The dashed line is the optimal spend point."
    )

    if saturation:
        fig2 = go.Figure()
        for ch, data in saturation.items():
            color = CHANNEL_COLORS.get(ch, DEFAULT_COLOR)
            spend_pts = data.get("spend_points", [])
            roas_pts = data.get("roas_points", [])
            current_spend = data.get("current_spend", 0)
            current_roas = data.get("current_roas", 0)
            optimal_spend = data.get("optimal_spend", 0)

            fig2.add_trace(go.Scatter(
                x=spend_pts, y=roas_pts,
                mode="lines", name=ch,
                line=dict(color=color, width=2),
                hovertemplate=f"<b>{ch}</b><br>Spend: $%{{x:,.0f}}<br>ROAS: %{{y:.2f}}x<extra></extra>",
            ))
            # Current spend marker
            fig2.add_trace(go.Scatter(
                x=[current_spend], y=[current_roas],
                mode="markers", name=f"{ch} (current)",
                marker=dict(size=10, color=color, symbol="circle"),
                showlegend=False,
                hovertemplate=f"<b>{ch} — current</b><br>Spend: ${current_spend:,.0f}<br>ROAS: {current_roas:.2f}x<extra></extra>",
            ))
            # Optimal spend line
            if 0 < optimal_spend <= max(spend_pts, default=1) * 1.05:
                fig2.add_vline(
                    x=optimal_spend,
                    line_dash="dash",
                    line_color=color,
                    line_width=1,
                    opacity=0.4,
                )

        fig2.update_layout(
            height=400,
            margin=dict(t=20, b=40, l=20, r=20),
            paper_bgcolor="white",
            plot_bgcolor="white",
            legend=dict(orientation="h", y=-0.2),
            xaxis=dict(title="Spend ($)", tickprefix="$", gridcolor="#F0F0F0"),
            yaxis=dict(title="ROAS", ticksuffix="x", gridcolor="#F0F0F0"),
        )
        st.plotly_chart(fig2, use_container_width=True)

        # Saturation summary
        sat_cols = st.columns(len(saturation))
        for i, (ch, data) in enumerate(saturation.items()):
            pct = data.get("saturation_pct", 0)
            color = "#EF4444" if pct > 90 else "#F59E0B" if pct > 70 else "#22C55E"
            with sat_cols[i]:
                st.markdown(f"""
                <div style="text-align:center; padding:8px; background:#F9F9F9; border-radius:8px;">
                    <p style="margin:0; font-size:0.75rem; color:#717182;">{ch}</p>
                    <p style="margin:4px 0 0; font-size:1.4rem; font-weight:700; color:{color};">{pct:.0f}%</p>
                    <p style="margin:0; font-size:0.7rem; color:#717182;">saturated</p>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("---")

    # -----------------------------------------------------------------------
    # Section 4 — Budget Recommendations
    # -----------------------------------------------------------------------
    st.markdown("### Optimal Budget Allocation")

    rec_channels = recs.get("channels", {})
    curr_roas = recs.get("current_blended_roas", 0)
    proj_roas = recs.get("projected_blended_roas", 0)
    uplift = recs.get("roas_uplift_pct", 0)

    if rec_channels:
        # Summary bar
        color = "#22C55E" if uplift > 0 else "#717182"
        st.markdown(f"""
        <div style="padding:12px 16px; background:#f0fdf4; border-radius:10px;
                    border-left:4px solid #22C55E; margin-bottom:20px;">
            <span style="font-size:1rem; font-weight:600; color:#22C55E;">
                Reallocation could lift blended ROAS from {curr_roas:.2f}x → {proj_roas:.2f}x
            </span>
            <span style="font-size:0.9rem; color:#717182; margin-left:12px;">
                ({'+' if uplift >= 0 else ''}{uplift:.1f}% improvement)
            </span>
        </div>
        """, unsafe_allow_html=True)

        # Per-channel recommendation cards
        num_ch = len(rec_channels)
        rec_cols = st.columns(min(num_ch, 4))
        for i, (ch, rec) in enumerate(rec_channels.items()):
            change = rec.get("change_pct", 0)
            arrow = "▲" if change > 0 else "▼" if change < 0 else "→"
            c_color = "#22C55E" if change > 5 else "#EF4444" if change < -5 else "#717182"
            ch_color = CHANNEL_COLORS.get(ch, DEFAULT_COLOR)
            with rec_cols[i % 4]:
                st.markdown(f"""
                <div style="padding:12px; border:1px solid #E5E7EB; border-radius:10px;
                            border-top:3px solid {ch_color}; height:100%;">
                    <p style="margin:0; font-size:0.8rem; font-weight:700; color:#1a1a1a;">{ch}</p>
                    <p style="margin:4px 0 0; font-size:0.75rem; color:#717182;">
                        Current: <b>${rec['current_spend']:,.0f}</b>
                    </p>
                    <p style="margin:2px 0 0; font-size:1rem; font-weight:600; color:{c_color};">
                        {arrow} ${rec['recommended_spend']:,.0f}
                        <span style="font-size:0.75rem;">({'+' if change >= 0 else ''}{change:.0f}%)</span>
                    </p>
                    <p style="margin:4px 0 0; font-size:0.7rem; color:#9CA3AF;">{rec.get('rationale', '')}</p>
                    <p style="margin:4px 0 0; font-size:0.72rem; color:#717182;">
                        Projected ROAS: <b>{rec.get('projected_roas', 0):.2f}x</b>
                        (was {rec.get('current_roas', 0):.2f}x)
                    </p>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Apply as recommendation
        apply_col, _ = st.columns([2, 4])
        with apply_col:
            if st.button("✓ Save as Pending Recommendation", type="primary", use_container_width=True):
                # Find a campaign to attach it to
                campaigns = data_service.get_campaigns()
                cid = campaigns[0]["id"] if campaigns else 0
                data_service.create_scenario_recommendation(
                    campaign_id=cid,
                    proposed_budgets={ch: r["recommended_spend"] for ch, r in rec_channels.items()},
                )
                st.success("📋 Saved to Action Center — review it before applying.")

    st.markdown("---")

    # -----------------------------------------------------------------------
    # Section 5 — Future Campaign Budget Template
    # -----------------------------------------------------------------------
    st.markdown("### Future Campaign Budget Template")
    st.caption("Recommended starting budgets for a new campaign based on historical channel efficiency.")

    if rec_channels:
        total_new = st.number_input(
            "New campaign total budget ($)",
            min_value=1000,
            value=int(recs.get("total_budget", 50000)),
            step=5000,
            key="mmm_new_budget",
        )

        rows = []
        proj_total_rev = 0
        for ch, rec in rec_channels.items():
            orig_total = recs.get("total_budget", 1)
            share = rec["recommended_spend"] / orig_total if orig_total > 0 else 0
            new_spend = total_new * share
            proj_rev = new_spend * rec.get("projected_roas", rec.get("current_roas", 1))
            proj_total_rev += proj_rev
            rows.append({
                "Channel": ch,
                "Recommended Budget": f"${new_spend:,.0f}",
                "Share": f"{share:.0%}",
                "Projected ROAS": f"{rec.get('projected_roas', rec.get('current_roas', 1)):.2f}x",
                "Projected Revenue": f"${proj_rev:,.0f}",
            })

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        proj_blended = proj_total_rev / total_new if total_new > 0 else 0
        st.info(f"📊 Projected blended ROAS for new campaign: **{proj_blended:.2f}x** · "
                f"Estimated revenue: **${proj_total_rev:,.0f}**")


def _get_campaigns(data_service: DataService):
    try:
        return data_service.get_campaigns()
    except Exception:
        return []
