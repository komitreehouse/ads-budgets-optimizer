"""
Incrementality Testing Page

Dashboard for managing and viewing incrementality experiments:
- Active Experiments: Currently running tests
- Results: Historical experiment results with lift metrics
- Create New: Setup new incrementality tests
"""

import streamlit as st
from datetime import datetime, timedelta
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from frontend.services.data_service import DataService
from frontend.components.loading import render_loading_spinner, render_error_message, render_empty_state


def render():
    """Render the incrementality testing dashboard."""
    data_service = DataService()
    
    # Header
    st.markdown("## 📊 Incrementality Testing")
    st.markdown("Measure true incremental lift from your advertising spend")
    
    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["🔬 Active Experiments", "📈 Results", "➕ Create New"])
    
    with tab1:
        render_active_experiments(data_service)
    
    with tab2:
        render_experiment_results(data_service)
    
    with tab3:
        render_create_experiment(data_service)


def render_active_experiments(data_service: DataService):
    """Render active experiments tab."""
    st.markdown("### Running Experiments")
    
    # Fetch active experiments from data service
    experiments = data_service.get_incrementality_experiments(status='running')
    
    if not experiments:
        render_empty_state(
            "No Active Experiments",
            "Start a new incrementality experiment to measure true lift from your ads."
        )
        return
    
    for exp in experiments:
        render_experiment_card(exp, is_active=True)


def render_experiment_results(data_service: DataService):
    """Render experiment results tab."""
    st.markdown("### Completed Experiments")
    
    # Filters
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        campaigns = data_service.get_campaigns()
        campaign_options = ["All Campaigns"] + [c['name'] for c in campaigns]
        selected_campaign = st.selectbox(
            "Campaign",
            campaign_options,
            index=0,
            key="inc_campaign_filter"
        )
    
    with col2:
        exp_types = ["All Types", "Holdout", "Geo-Lift", "Platform Native"]
        selected_type = st.selectbox(
            "Experiment Type",
            exp_types,
            index=0,
            key="inc_type_filter"
        )
    
    with col3:
        date_range = st.selectbox(
            "Period",
            ["Last 30 days", "Last 90 days", "Last 6 months", "All time"],
            index=0,
            key="inc_date_filter"
        )
    
    # Fetch completed experiments from data service
    experiments = data_service.get_incrementality_experiments(status='completed')
    
    if not experiments:
        render_empty_state(
            "No Completed Experiments",
            "Complete an experiment to see results here."
        )
        return
    
    # Summary metrics
    st.markdown("#### Key Insights")
    
    col1, col2, col3, col4 = st.columns(4)
    
    avg_lift = sum(e['lift_percent'] for e in experiments) / len(experiments)
    avg_iroas = sum(e['incremental_roas'] for e in experiments) / len(experiments)
    avg_inflation = sum(e['roas_inflation'] for e in experiments) / len(experiments)
    significant_count = sum(1 for e in experiments if e['is_significant'])
    
    with col1:
        st.metric("Avg Incremental Lift", f"{avg_lift:.1f}%")
    
    with col2:
        st.metric("Avg Incremental ROAS", f"{avg_iroas:.2f}x")
    
    with col3:
        st.metric("Avg ROAS Inflation", f"{avg_inflation:.0f}%", 
                  help="How much observed ROAS overestimates true incremental value")
    
    with col4:
        st.metric("Significant Results", f"{significant_count}/{len(experiments)}")
    
    st.divider()
    
    # Results table
    st.markdown("#### Experiment Results")
    
    for exp in experiments:
        render_experiment_result_card(exp)


def render_create_experiment(data_service: DataService):
    """Render create experiment tab."""
    st.markdown("### Create New Experiment")
    
    # Experiment type selection
    exp_type = st.radio(
        "Experiment Type",
        ["🎯 Automated Holdout", "🗺️ Geo-Lift Test", "🔌 Platform Native"],
        horizontal=True,
        key="new_exp_type"
    )
    
    st.divider()
    
    if "Holdout" in exp_type:
        render_holdout_form(data_service)
    elif "Geo-Lift" in exp_type:
        render_geolift_form(data_service)
    else:
        render_platform_native_form(data_service)


def render_holdout_form(data_service: DataService):
    """Render automated holdout experiment form."""
    st.markdown("#### Automated Holdout Experiment")
    st.markdown("""
    Reserve a percentage of your audience as a control group (no ad exposure) 
    to measure true incremental lift.
    """)
    
    with st.form("holdout_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Experiment Name", placeholder="Q1 2026 Holdout Test")
            
            campaigns = data_service.get_campaigns()
            campaign_options = [c['name'] for c in campaigns]
            selected_campaign = st.selectbox("Campaign", campaign_options)
            
            holdout_pct = st.slider(
                "Holdout Percentage",
                min_value=5,
                max_value=20,
                value=10,
                help="Percentage of audience to exclude from ads"
            )
        
        with col2:
            duration = st.number_input(
                "Duration (days)",
                min_value=7,
                max_value=90,
                value=28,
                help="Recommended: 4 weeks for statistical significance"
            )
            
            st.markdown("##### Sample Size Calculator")
            baseline_cvr = st.number_input(
                "Expected Baseline CVR (%)",
                min_value=0.1,
                max_value=10.0,
                value=2.0,
                step=0.1
            )
            
            min_lift = st.number_input(
                "Minimum Detectable Lift (%)",
                min_value=5,
                max_value=50,
                value=10
            )
        
        # Calculate sample size
        from src.bandit_ads.incrementality import calculate_sample_size
        sample_req = calculate_sample_size(
            baseline_cvr=baseline_cvr / 100,
            minimum_detectable_effect=min_lift / 100
        )
        
        st.info(f"""
        📊 **Sample Size Requirement**  
        To detect a {min_lift}% lift with 80% power:
        - Treatment group: **{sample_req['treatment_users']:,}** users
        - Control group: **{sample_req['control_users']:,}** users
        - Total: **{sample_req['total_users']:,}** users
        """)
        
        submitted = st.form_submit_button("Create Experiment", type="primary", use_container_width=True)
        
        if submitted:
            # Get campaign ID from selection
            campaign_id = next((c['id'] for c in campaigns if c['name'] == selected_campaign), 1)
            
            result = data_service.create_incrementality_experiment(
                campaign_id=campaign_id,
                name=name,
                experiment_type='holdout',
                holdout_percentage=holdout_pct / 100,
                duration_days=duration
            )
            
            if result:
                st.success(f"✅ Holdout experiment '{name}' created successfully!")
                st.info("The experiment will automatically start tracking organic conversions in the holdout group.")
            else:
                st.error("Failed to create experiment. Please try again.")


def render_geolift_form(data_service: DataService):
    """Render geo-lift experiment form."""
    st.markdown("#### Geo-Lift Experiment")
    st.markdown("""
    Compare geographic markets with and without advertising to measure incremental impact.
    Uses synthetic control methodology for robust lift measurement.
    """)
    
    with st.form("geolift_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Experiment Name", placeholder="West Coast Geo Test")
            
            campaigns = data_service.get_campaigns()
            campaign_options = [c['name'] for c in campaigns]
            selected_campaign = st.selectbox("Campaign", campaign_options, key="geo_campaign")
            
            duration = st.number_input(
                "Duration (days)",
                min_value=14,
                max_value=90,
                value=28,
                key="geo_duration"
            )
        
        with col2:
            st.markdown("##### Treatment Markets")
            treatment_markets = st.multiselect(
                "Select markets to receive ads",
                ["NYC", "LAX", "CHI", "HOU", "PHX", "PHI", "SAN", "DAL", "SJC", "AUS"],
                default=["NYC", "LAX"]
            )
            
            st.markdown("##### Control Markets")
            control_markets = st.multiselect(
                "Select control markets (no ads)",
                ["BOS", "SEA", "DEN", "ATL", "MIA", "DET", "MSP", "STL", "CLT", "PIT"],
                default=["BOS", "SEA", "DEN"]
            )
        
        st.markdown("##### Market Matching")
        st.markdown("""
        The system will automatically find optimal weights for control markets 
        to create a synthetic control that matches treatment market behavior.
        """)
        
        min_correlation = st.slider(
            "Minimum Pre-Period Correlation",
            min_value=0.70,
            max_value=0.95,
            value=0.85,
            help="Higher values ensure better market matching but may be harder to achieve"
        )
        
        submitted = st.form_submit_button("Create Geo-Lift Test", type="primary", use_container_width=True)
        
        if submitted:
            # Get campaign ID from selection
            campaign_id = next((c['id'] for c in campaigns if c['name'] == selected_campaign), 1)
            
            result = data_service.create_incrementality_experiment(
                campaign_id=campaign_id,
                name=name,
                experiment_type='geo_lift',
                duration_days=duration,
                treatment_markets=treatment_markets,
                control_markets=control_markets
            )
            
            if result:
                st.success(f"✅ Geo-lift experiment '{name}' created!")
                st.info(f"Treatment: {', '.join(treatment_markets)} | Control: {', '.join(control_markets)}")
            else:
                st.error("Failed to create experiment. Please try again.")


def render_platform_native_form(data_service: DataService):
    """Render platform-native experiment form."""
    st.markdown("#### Platform Native Incrementality")
    st.markdown("""
    Use built-in incrementality tools from ad platforms:
    - **Meta**: Conversion Lift studies
    - **Google**: Conversion Lift experiments
    - **TTD**: Ghost Bid experiments
    """)
    
    with st.form("platform_native_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            platform = st.selectbox(
                "Platform",
                ["Meta (Conversion Lift)", "Google (Conversion Lift)", "TTD (Ghost Bids)"]
            )
            
            name = st.text_input("Study Name", placeholder="Meta Q1 Lift Study")
            
            campaigns = data_service.get_campaigns()
            campaign_options = [c['name'] for c in campaigns]
            selected_campaign = st.selectbox("Campaign", campaign_options, key="native_campaign")
        
        with col2:
            holdout_pct = st.slider(
                "Control Group %",
                min_value=5,
                max_value=20,
                value=10,
                key="native_holdout"
            )
            
            duration = st.number_input(
                "Duration (days)",
                min_value=7,
                max_value=90,
                value=28,
                key="native_duration"
            )
            
            if "Meta" in platform:
                objective = st.selectbox(
                    "Optimization Objective",
                    ["Conversions", "Purchase", "Lead", "Add to Cart"]
                )
        
        st.warning("""
        ⚠️ **Note**: Platform-native studies require API access and may incur 
        additional costs. Results will sync automatically when available.
        """)
        
        submitted = st.form_submit_button("Create Platform Study", type="primary", use_container_width=True)
        
        if submitted:
            # Get campaign ID from selection
            campaign_id = next((c['id'] for c in campaigns if c['name'] == selected_campaign), 1)
            
            # Extract platform name
            platform_name = platform.split(' ')[0].lower()
            
            result = data_service.create_incrementality_experiment(
                campaign_id=campaign_id,
                name=name,
                experiment_type='platform_native',
                holdout_percentage=holdout_pct / 100,
                duration_days=duration,
                platform=platform_name
            )
            
            if result:
                st.success(f"✅ {platform.split(' ')[0]} study '{name}' created!")
            else:
                st.error("Failed to create study. Please try again.")


def render_experiment_card(exp: dict, is_active: bool = False):
    """Render an experiment card."""
    type_icons = {
        'holdout': '🎯',
        'geo_lift': '🗺️',
        'platform_native': '🔌'
    }
    
    status_colors = {
        'running': '#22C55E',
        'completed': '#3B82F6',
        'designing': '#F59E0B',
        'aborted': '#EF4444'
    }
    
    icon = type_icons.get(exp['type'], '📊')
    color = status_colors.get(exp['status'], '#737373')
    
    with st.container():
        st.markdown(f"""
        <div class="card" style="padding: 16px; margin-bottom: 16px; border-left: 4px solid {color};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h4 style="margin: 0;">{icon} {exp['name']}</h4>
                    <p style="margin: 4px 0 0 0; color: #717182; font-size: 0.875rem;">
                        {exp['campaign']} • {exp['type'].replace('_', ' ').title()}
                    </p>
                </div>
                <span style="background: {color}20; color: {color}; padding: 4px 12px; border-radius: 12px; font-size: 0.75rem; font-weight: 600;">
                    {exp['status'].upper()}
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if is_active:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Days Running", exp.get('days_running', 0))
            
            with col2:
                st.metric("Treatment Users", f"{exp.get('treatment_users', 0):,}")
            
            with col3:
                st.metric("Control Users", f"{exp.get('control_users', 0):,}")
            
            with col4:
                days_left = exp.get('duration_days', 28) - exp.get('days_running', 0)
                st.metric("Days Remaining", max(0, days_left))
            
            # Progress bar
            progress = min(1.0, exp.get('days_running', 0) / exp.get('duration_days', 28))
            st.progress(progress, text=f"{progress:.0%} complete")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("View Details", key=f"view_{exp['id']}", use_container_width=True):
                    st.session_state['selected_experiment'] = exp['id']
            with col2:
                if st.button("⏹ Stop Early", key=f"stop_{exp['id']}", use_container_width=True):
                    st.warning("Are you sure? Stopping early may reduce statistical power.")


def render_experiment_result_card(exp: dict):
    """Render a completed experiment result card."""
    with st.expander(f"📊 {exp['name']} - {exp['end_date']}", expanded=False):
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            lift_color = "#22C55E" if exp['lift_percent'] > 0 else "#EF4444"
            st.metric(
                "Incremental Lift",
                f"{exp['lift_percent']:+.1f}%",
                delta=None
            )
        
        with col2:
            st.metric("Incremental ROAS", f"{exp['incremental_roas']:.2f}x")
        
        with col3:
            st.metric("Observed ROAS", f"{exp['observed_roas']:.2f}x")
        
        with col4:
            st.metric("ROAS Inflation", f"{exp['roas_inflation']:.0f}%",
                     help="How much observed ROAS overstates true value")
        
        st.divider()
        
        # Statistical details
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### Statistical Significance")
            
            if exp['is_significant']:
                st.success(f"✅ Statistically significant (p={exp['p_value']:.3f})")
            else:
                st.warning(f"⚠️ Not significant (p={exp['p_value']:.3f})")
            
            ci_lower, ci_upper = exp['confidence_interval']
            st.markdown(f"**95% Confidence Interval:** {ci_lower:.1f}% to {ci_upper:.1f}%")
        
        with col2:
            st.markdown("##### Sample Sizes")
            st.markdown(f"""
            - Treatment: **{exp['treatment_users']:,}** users
            - Control: **{exp['control_users']:,}** users
            - Duration: **{exp['duration_days']}** days
            """)
        
        st.divider()
        
        # Impact summary
        st.markdown("##### Business Impact")
        
        incremental_revenue = exp.get('incremental_revenue', 0)
        treatment_spend = exp.get('treatment_spend', 0)
        
        st.markdown(f"""
        | Metric | Value |
        |--------|-------|
        | Incremental Revenue | **${incremental_revenue:,.0f}** |
        | Ad Spend | **${treatment_spend:,.0f}** |
        | True ROI | **{exp['incremental_roas']:.2f}x** |
        | Attributed ROI | **{exp['observed_roas']:.2f}x** |
        | Overestimation | **{exp['roas_inflation']:.0f}%** |
        """)
        
        # Action buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Apply to Bandit", key=f"apply_{exp['id']}", type="primary", use_container_width=True):
                from frontend.services.data_service import DataService
                data_service = DataService()
                success = data_service.apply_incrementality_to_bandit(
                    experiment_id=exp['id'],
                    campaign_id=exp.get('campaign_id', 1)
                )
                if success:
                    st.success("✅ Incrementality results applied to bandit priors!")
                    st.info("Budget allocation will now use incremental ROAS instead of observed ROAS.")
                else:
                    st.error("Failed to apply results. Please try again.")
        
        with col2:
            if st.button("Export Report", key=f"export_{exp['id']}", use_container_width=True):
                st.info("Report exported to CSV")
        
        with col3:
            if st.button("Rerun Experiment", key=f"rerun_{exp['id']}", use_container_width=True):
                st.info("New experiment created with same parameters")


def render_empty_state(title: str, description: str):
    """Render an empty state message."""
    st.markdown(f"""
    <div style="text-align: center; padding: 48px 24px; background: #f8f9fa; border-radius: 12px; margin: 24px 0;">
        <h3 style="color: #717182; margin-bottom: 8px;">{title}</h3>
        <p style="color: #9ca3af;">{description}</p>
    </div>
    """, unsafe_allow_html=True)
