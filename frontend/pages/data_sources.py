"""
Data Sources Page

Central hub for managing data inputs: connected ad platforms and
uploaded historical performance files. Replaces the one-time onboarding
upload with a persistent management view.
"""

import streamlit as st
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from frontend.services.data_service import DataService
from frontend.components.loading import render_error_message


PLATFORM_META = {
    "google_ads":      {"name": "Google Ads",       "icon": "🔍", "color": "#4285F4"},
    "meta_ads":        {"name": "Meta Ads",          "icon": "👥", "color": "#1877F2"},
    "the_trade_desk":  {"name": "The Trade Desk",    "icon": "🎯", "color": "#00A98F"},
}


def render():
    """Render the Data Sources management page."""
    data_service = DataService()

    st.markdown("## 🗂 Data Sources")
    st.markdown("Manage your connected ad platforms and uploaded historical data files.")

    # -----------------------------------------------------------------------
    # Section 1 — Connected Platforms
    # -----------------------------------------------------------------------
    st.markdown("### Connected Platforms")

    platform_data = _get_platform_data(data_service)

    cols = st.columns(3)
    for idx, (platform_id, meta) in enumerate(PLATFORM_META.items()):
        info = platform_data.get(platform_id, {})
        connected = info.get("connected", False)
        last_sync = info.get("last_sync")
        error = info.get("error")

        with cols[idx]:
            badge_color = "#22C55E" if connected else "#9CA3AF"
            badge_label = "Connected" if connected else "Not connected"
            sync_line = (
                f"Last sync: {last_sync[:10] if last_sync else '—'}"
                if connected
                else (error or "Configure credentials to connect")
            )

            name_col, badge_col = st.columns([2, 1])
            with name_col:
                st.markdown(f"<span style='font-size:1.5rem;'>{meta['icon']}</span> **{meta['name']}**", unsafe_allow_html=True)
            with badge_col:
                st.markdown(f"<div style='text-align:right;'><span style='background:{badge_color}20; color:{badge_color}; padding:2px 10px; border-radius:9999px; font-size:0.75rem; font-weight:600;'>{badge_label}</span></div>", unsafe_allow_html=True)
            st.markdown(f"<p style='margin:4px 0 8px 0; font-size:0.8rem; color:#717182; border-top:3px solid {meta['color']}; padding-top:6px;'>{sync_line}</p>", unsafe_allow_html=True)

            btn_label = "🔄 Refresh" if connected else "🔗 Connect"
            btn_type = "secondary" if connected else "primary"
            if st.button(btn_label, key=f"connect_{platform_id}", use_container_width=True, type=btn_type):
                st.session_state.current_page = "onboarding"
                st.session_state.onboarding_step = 1
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # Section 2 — Upload Historical Files
    # -----------------------------------------------------------------------
    st.markdown("### Upload Historical Data")
    st.markdown(
        "Upload CSV or JSON files exported from your ad platforms. "
        "IPSA uses this data to initialise the bandit agent priors and MMM coefficients."
    )

    with st.expander("📋 Expected file format", expanded=False):
        st.markdown("""
        **CSV columns (required):** `date`, `channel`, `spend`, `impressions`, `clicks`, `conversions`

        **Optional columns:** `revenue`, `cpa`, `roas`, `campaign_name`

        **Date format:** `YYYY-MM-DD`

        **Example:**
        ```
        date,channel,spend,impressions,clicks,conversions,revenue
        2025-01-01,Google Search,1200.00,45000,980,42,3600.00
        2025-01-01,Meta Social,800.00,32000,620,28,1960.00
        ```
        """)

    uploaded_files = st.file_uploader(
        "Drag and drop files here",
        type=["csv", "json"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="data_source_uploader",
    )

    if uploaded_files:
        for uf in uploaded_files:
            result = data_service.upload_data_file(uf)
            if result and result.get("success"):
                st.success(
                    f"✓ **{uf.name}** — {result['rows']:,} rows"
                    + (f", {result['date_range']}" if result.get('date_range') else "")
                )
            else:
                st.error(f"✗ Could not process {uf.name}: {result.get('detail', 'unknown error')}")

    # Demo shortcut
    st.markdown("""
    <p style="text-align: center; margin: 12px 0 4px 0; font-size: 0.85rem; color: #717182;">
        — or —
    </p>
    """, unsafe_allow_html=True)
    demo_col1, demo_col2, demo_col3 = st.columns([2, 3, 2])
    with demo_col2:
        if st.button("🎬 Load sample dataset for demo", use_container_width=True, key="ds_load_sample"):
            st.session_state.current_page = "onboarding"
            st.session_state.onboarding_step = 1
            st.session_state.demo_banner_dismissed = False
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # Section 3 — Uploaded Files Table
    # -----------------------------------------------------------------------
    st.markdown("### Uploaded Files")
    existing = data_service.get_uploaded_files()

    if not existing:
        st.info("No files uploaded yet. Use the uploader above to add historical data.")
    else:
        # Header row
        hcols = st.columns([3, 1, 2, 2, 1])
        for col, label in zip(hcols, ["Filename", "Rows", "Date Range", "Uploaded", ""]):
            col.markdown(f"**{label}**")
        st.divider()

        for rec in existing:
            rcols = st.columns([3, 1, 2, 2, 1])
            rcols[0].markdown(f"📄 {rec['filename']}")
            rcols[1].markdown(f"{rec['rows']:,}")
            rcols[2].markdown(rec.get("date_range") or "—")
            upload_time = rec.get("upload_time", "")[:10]
            rcols[3].markdown(upload_time)
            if rcols[4].button("🗑", key=f"del_{rec['filename']}", help="Remove"):
                data_service.delete_uploaded_file(rec["filename"])
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # Section 4 — Data Health
    # -----------------------------------------------------------------------
    st.markdown("### Data Health")
    _render_data_health(existing, platform_data)


def _get_platform_data(data_service: DataService) -> dict:
    """Fetch platform connection statuses."""
    try:
        sources = data_service.get_data_sources()
        return {p["platform"]: p for p in sources.get("platforms", [])}
    except Exception:
        return {}


def _render_data_health(uploaded_files: list, platform_data: dict) -> None:
    """Render a simple data health summary."""
    connected_count = sum(1 for p in platform_data.values() if p.get("connected"))
    total_platforms = len(PLATFORM_META)
    file_count = len(uploaded_files)
    total_rows = sum(f.get("rows", 0) for f in uploaded_files)

    col1, col2, col3 = st.columns(3)
    with col1:
        color = "#22C55E" if connected_count > 0 else "#F59E0B"
        st.markdown(f"""
        <div class="card" style="text-align: center;">
            <p style="margin: 0; font-size: 0.875rem; color: #717182;">Platforms connected</p>
            <p style="margin: 4px 0 0 0; font-size: 2rem; font-weight: 600; color: {color};">
                {connected_count}/{total_platforms}
            </p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        color = "#22C55E" if file_count > 0 else "#9CA3AF"
        st.markdown(f"""
        <div class="card" style="text-align: center;">
            <p style="margin: 0; font-size: 0.875rem; color: #717182;">Historical files</p>
            <p style="margin: 4px 0 0 0; font-size: 2rem; font-weight: 600; color: {color};">
                {file_count}
            </p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        color = "#22C55E" if total_rows > 1000 else "#F59E0B" if total_rows > 0 else "#9CA3AF"
        st.markdown(f"""
        <div class="card" style="text-align: center;">
            <p style="margin: 0; font-size: 0.875rem; color: #717182;">Total rows ingested</p>
            <p style="margin: 4px 0 0 0; font-size: 2rem; font-weight: 600; color: {color};">
                {total_rows:,}
            </p>
        </div>
        """, unsafe_allow_html=True)

    if connected_count == 0 and file_count == 0:
        st.warning(
            "⚠️ No data sources connected. Connect a platform or upload a historical file "
            "to start optimising your budgets."
        )
    elif connected_count == 0:
        st.info("💡 Connect an ad platform to enable live data sync and real-time optimisation.")
    elif total_rows < 100 and file_count > 0:
        st.warning("⚠️ Very few rows uploaded — consider uploading at least 30 days of data for accurate priors.")
    else:
        st.success("✓ Data sources look healthy.")
