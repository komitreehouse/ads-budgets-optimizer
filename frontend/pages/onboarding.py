"""
Onboarding Page - Data Upload and Campaign Setup

Allows users to upload historical data (JSON/CSV) and configure
campaign optimization settings to see live bandit optimization.
"""

import streamlit as st
from datetime import datetime
import sys
from pathlib import Path
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from frontend.services.data_service import DataService


def render():
    """Render the onboarding page."""
    
    # Initialize session state for onboarding
    if 'onboarding_step' not in st.session_state:
        st.session_state.onboarding_step = 1
    if 'uploaded_data' not in st.session_state:
        st.session_state.uploaded_data = None
    if 'campaign_config' not in st.session_state:
        st.session_state.campaign_config = None
    if 'optimization_running' not in st.session_state:
        st.session_state.optimization_running = False
    
    # Header
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <h1 style="font-family: 'Radley', Georgia, serif; font-weight: 400; margin: 0; color: #1a1a1a;">
            🚀 Get Started with Budget Optimizer
        </h1>
        <p style="color: #717182; margin-top: 8px;">
            Upload your historical data to see the AI-powered budget optimization in action
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Progress indicator
    render_progress_indicator(st.session_state.onboarding_step)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Render current step
    if st.session_state.onboarding_step == 1:
        render_step_1_upload()
    elif st.session_state.onboarding_step == 2:
        render_step_2_preview()
    elif st.session_state.onboarding_step == 3:
        render_step_3_configure()
    elif st.session_state.onboarding_step == 4:
        render_step_4_optimize()


def render_progress_indicator(current_step: int):
    """Render the progress steps indicator."""
    steps = [
        ("1", "Upload Data", "📤"),
        ("2", "Preview", "👁️"),
        ("3", "Configure", "⚙️"),
        ("4", "Optimize", "🎯")
    ]
    
    cols = st.columns(len(steps))
    
    for i, (num, label, icon) in enumerate(steps):
        step_num = i + 1
        with cols[i]:
            if step_num < current_step:
                # Completed
                st.markdown(f"""
                <div style="text-align: center;">
                    <div style="width: 40px; height: 40px; border-radius: 50%; background: #22C55E; 
                         color: white; display: inline-flex; align-items: center; justify-content: center;
                         font-weight: 600;">✓</div>
                    <p style="margin: 8px 0 0 0; font-size: 0.875rem; color: #22C55E;">{label}</p>
                </div>
                """, unsafe_allow_html=True)
            elif step_num == current_step:
                # Current - Use IPSA terracotta
                st.markdown(f"""
                <div style="text-align: center;">
                    <div style="width: 40px; height: 40px; border-radius: 50%; background: #9b4819; 
                         color: white; display: inline-flex; align-items: center; justify-content: center;
                         font-weight: 600;">{icon}</div>
                    <p style="margin: 8px 0 0 0; font-size: 0.875rem; color: #9b4819; font-weight: 600;">{label}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Future
                st.markdown(f"""
                <div style="text-align: center;">
                    <div style="width: 40px; height: 40px; border-radius: 50%; background: #ececf0; 
                         color: #717182; display: inline-flex; align-items: center; justify-content: center;
                         font-weight: 600;">{num}</div>
                    <p style="margin: 8px 0 0 0; font-size: 0.875rem; color: #717182;">{label}</p>
                </div>
                """, unsafe_allow_html=True)


def render_step_1_upload():
    """Step 1: Upload historical data file."""
    
    st.markdown("### 📤 Upload Your Historical Data")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        Upload your historical advertising performance data to initialize the budget optimizer.
        The optimizer will learn from your historical patterns and make intelligent allocation decisions.
        """)
        
        # File upload
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=['json', 'csv'],
            help="Upload JSON or CSV file with historical performance data"
        )
        
        if uploaded_file is not None:
            try:
                # Process the uploaded file
                if uploaded_file.name.endswith('.json'):
                    data = json.load(uploaded_file)
                    st.session_state.uploaded_data = {
                        'type': 'json',
                        'filename': uploaded_file.name,
                        'data': data,
                        'raw_content': None
                    }
                elif uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                    st.session_state.uploaded_data = {
                        'type': 'csv',
                        'filename': uploaded_file.name,
                        'data': df.to_dict('records'),
                        'dataframe': df,
                        'raw_content': None
                    }
                
                st.success(f"✅ Successfully loaded: {uploaded_file.name}")
                
                # Show quick preview
                st.markdown("#### Quick Preview")
                if st.session_state.uploaded_data['type'] == 'json':
                    data = st.session_state.uploaded_data['data']
                    if 'historical_performance' in data:
                        num_entries = len(data['historical_performance'])
                        st.info(f"📊 Found **{num_entries}** platform/channel combinations")
                    elif 'platform_channel_combinations' in data:
                        num_entries = len(data['platform_channel_combinations'])
                        st.info(f"📊 Found **{num_entries}** platform/channel combinations")
                else:
                    df = st.session_state.uploaded_data['dataframe']
                    st.info(f"📊 Found **{len(df)}** rows of historical data")
                    platforms = df['platform'].unique() if 'platform' in df.columns else []
                    channels = df['channel'].unique() if 'channel' in df.columns else []
                    st.write(f"Platforms: {', '.join(platforms)}")
                    st.write(f"Channels: {', '.join(channels)}")
                
            except Exception as e:
                st.error(f"❌ Error reading file: {str(e)}")
                st.session_state.uploaded_data = None
    
    with col2:
        # Format guide - using Streamlit native components for better rendering
        with st.container():
            st.markdown("#### 📋 Supported Formats")
            
            st.markdown("**JSON Format:**")
            st.markdown("""
            - `historical_performance`
            - `seasonal_multipliers`
            - Platform/channel metrics
            """)
            
            st.markdown("**CSV Format:**")
            st.markdown("""
            - `platform`, `channel` columns
            - `ctr`, `cvr`, `roas` metrics
            - `impressions`, `clicks`, etc.
            """)
        
        # Sample data option
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Or use sample data:**")
        if st.button("📥 Load Sample Data", use_container_width=True):
            # Load the mock data
            sample_path = project_root / "data" / "mock_historical_data.json"
            if sample_path.exists():
                with open(sample_path, 'r') as f:
                    data = json.load(f)
                st.session_state.uploaded_data = {
                    'type': 'json',
                    'filename': 'mock_historical_data.json',
                    'data': data,
                    'raw_content': None
                }
                st.success("✅ Loaded sample data!")
                st.rerun()
            else:
                # Create sample data
                data_service = DataService()
                sample_data = data_service.create_sample_historical_data()
                st.session_state.uploaded_data = {
                    'type': 'json',
                    'filename': 'sample_data.json',
                    'data': sample_data,
                    'raw_content': None
                }
                st.success("✅ Generated sample data!")
                st.rerun()
    
    # Navigation
    st.markdown("<br>", unsafe_allow_html=True)
    col_skip, col_spacer, col_next = st.columns([1, 2, 1])
    
    with col_skip:
        if st.button("Skip for now →", use_container_width=True):
            # Use sample data and skip to dashboard
            data_service = DataService()
            sample_data = data_service.create_sample_historical_data()
            st.session_state.uploaded_data = {
                'type': 'json',
                'filename': 'sample_data.json',
                'data': sample_data,
                'raw_content': None
            }
            st.session_state.onboarding_step = 3  # Skip to configure
            st.rerun()
    
    with col_next:
        if st.session_state.uploaded_data:
            if st.button("Continue →", type="primary", use_container_width=True):
                st.session_state.onboarding_step = 2
                st.rerun()


def render_step_2_preview():
    """Step 2: Preview and validate uploaded data."""
    
    st.markdown("### 👁️ Data Preview & Validation")
    
    if not st.session_state.uploaded_data:
        st.warning("No data uploaded. Please go back and upload a file.")
        if st.button("← Back to Upload"):
            st.session_state.onboarding_step = 1
            st.rerun()
        return
    
    data = st.session_state.uploaded_data['data']
    data_type = st.session_state.uploaded_data['type']
    
    # Validation status
    validation = validate_data(data, data_type)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Show validation results
        if validation['valid']:
            st.success("✅ Data validation passed!")
        else:
            st.error("❌ Data validation failed")
            for error in validation['errors']:
                st.warning(f"⚠️ {error}")
        
        # Data preview
        st.markdown("#### Data Summary")
        
        if data_type == 'json':
            # JSON preview
            if 'historical_performance' in data:
                perf_data = data['historical_performance']
                
                # Convert to dataframe for display
                rows = []
                for key, metrics in perf_data.items():
                    parts = key.split('_')
                    rows.append({
                        'Platform': parts[0] if len(parts) > 0 else 'Unknown',
                        'Channel': parts[1] if len(parts) > 1 else 'Unknown',
                        'Creative': parts[2] if len(parts) > 2 else 'N/A',
                        'CTR': f"{metrics.get('historical_ctr', 0):.2%}",
                        'CVR': f"{metrics.get('historical_cvr', 0):.2%}",
                        'ROAS': f"{metrics.get('historical_roas', 0):.2f}",
                        'Spend': f"${metrics.get('spend_baseline', 0):,.0f}"
                    })
                
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True)
                
            elif 'platform_channel_combinations' in data:
                perf_data = data['platform_channel_combinations']
                rows = []
                for key, metrics in perf_data.items():
                    parts = key.split('_')
                    rows.append({
                        'Platform': parts[0] if len(parts) > 0 else 'Unknown',
                        'Channel': parts[1] if len(parts) > 1 else 'Unknown',
                        'CTR': f"{metrics.get('historical_ctr', 0):.2%}",
                        'CVR': f"{metrics.get('historical_cvr', 0):.2%}",
                        'ROAS': f"{metrics.get('historical_roas', 0):.2f}",
                        'Spend': f"${metrics.get('spend_baseline', 0):,.0f}"
                    })
                
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True)
        
        else:
            # CSV preview
            df = st.session_state.uploaded_data['dataframe']
            st.dataframe(df.head(10), use_container_width=True, hide_index=True)
            if len(df) > 10:
                st.caption(f"Showing 10 of {len(df)} rows")
    
    with col2:
        # Data insights - using Streamlit native components
        st.markdown("#### 📈 Data Insights")
        
        insights = extract_data_insights(data, data_type)
        
        for insight in insights:
            st.markdown(f"- {insight}")
        
        # Visualization
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Performance by Platform")
        
        chart_data = get_platform_performance(data, data_type)
        if chart_data:
            fig = px.bar(
                chart_data,
                x='platform',
                y='roas',
                color='platform',
                title=None
            )
            fig.update_layout(
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                height=200
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Navigation
    st.markdown("<br>", unsafe_allow_html=True)
    col_back, col_spacer, col_next = st.columns([1, 2, 1])
    
    with col_back:
        if st.button("← Back", use_container_width=True):
            st.session_state.onboarding_step = 1
            st.rerun()
    
    with col_next:
        if validation['valid']:
            if st.button("Continue →", type="primary", use_container_width=True):
                st.session_state.onboarding_step = 3
                st.rerun()


def render_step_3_configure():
    """Step 3: Configure campaign settings."""
    
    st.markdown("### ⚙️ Configure Campaign")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### Campaign Settings")
        
        campaign_name = st.text_input(
            "Campaign Name",
            value="My First Campaign",
            help="Give your campaign a descriptive name"
        )
        
        total_budget = st.number_input(
            "Total Budget ($)",
            min_value=100,
            max_value=10000000,
            value=10000,
            step=1000,
            help="Total budget for the optimization period"
        )
        
        optimization_goal = st.selectbox(
            "Optimization Goal",
            options=["ROAS", "Conversions", "CTR", "Revenue"],
            help="Primary metric to optimize for"
        )
        
        risk_tolerance = st.slider(
            "Risk Tolerance",
            min_value=0.0,
            max_value=1.0,
            value=0.3,
            step=0.1,
            help="Higher values allow more exploration, lower values favor known performers"
        )
    
    with col2:
        st.markdown("#### Advanced Settings")
        
        min_allocation = st.slider(
            "Minimum Allocation per Arm (%)",
            min_value=1,
            max_value=20,
            value=5,
            help="Minimum budget percentage for any arm"
        )
        
        use_contextual = st.checkbox(
            "Enable Contextual Optimization",
            value=True,
            help="Use contextual features like time-of-day, day-of-week for smarter allocation"
        )
        
        use_mmm = st.checkbox(
            "Enable MMM Factors",
            value=True,
            help="Apply Marketing Mix Model factors (seasonality, carryover effects)"
        )
        
        simulation_steps = st.number_input(
            "Simulation Steps",
            min_value=10,
            max_value=1000,
            value=100,
            step=10,
            help="Number of optimization cycles to run"
        )
    
    # Store configuration
    st.session_state.campaign_config = {
        'name': campaign_name,
        'total_budget': total_budget,
        'optimization_goal': optimization_goal.lower(),
        'risk_tolerance': risk_tolerance,
        'min_allocation': min_allocation / 100.0,
        'use_contextual': use_contextual,
        'use_mmm': use_mmm,
        'simulation_steps': simulation_steps
    }
    
    # Preview arms that will be created
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Arms Preview")
    st.caption("These ad variations will be created based on your uploaded data:")
    
    if st.session_state.uploaded_data:
        arms = extract_arms_from_data(st.session_state.uploaded_data['data'], 
                                       st.session_state.uploaded_data['type'])
        
        cols = st.columns(4)
        for i, arm in enumerate(arms[:8]):
            with cols[i % 4]:
                with st.container(border=True):
                    st.markdown(f"**{arm['name']}**")
                    st.caption(f"{arm['platform']} • {arm['channel']}")
        
        if len(arms) > 8:
            st.caption(f"... and {len(arms) - 8} more arms")
    
    # Navigation
    st.markdown("<br>", unsafe_allow_html=True)
    col_back, col_spacer, col_next = st.columns([1, 2, 1])
    
    with col_back:
        if st.button("← Back", use_container_width=True):
            st.session_state.onboarding_step = 2
            st.rerun()
    
    with col_next:
        if st.button("🚀 Start Optimization", type="primary", use_container_width=True):
            st.session_state.onboarding_step = 4
            st.session_state.optimization_running = True
            st.rerun()


def render_step_4_optimize():
    """Step 4: Run optimization and show results."""
    
    st.markdown("### 🎯 Optimization Results")
    
    data_service = DataService()
    
    # Run optimization if just started
    if st.session_state.optimization_running:
        with st.spinner("Running optimization..."):
            results = data_service.run_optimization(
                historical_data=st.session_state.uploaded_data['data'],
                data_type=st.session_state.uploaded_data['type'],
                config=st.session_state.campaign_config
            )
            st.session_state.optimization_results = results
            st.session_state.optimization_running = False
    
    results = st.session_state.get('optimization_results', {})
    
    if not results:
        st.warning("No optimization results. Please configure and run optimization.")
        if st.button("← Back to Configure"):
            st.session_state.onboarding_step = 3
            st.rerun()
        return
    
    # Success message
    st.success(f"✅ Optimization complete! Ran {results.get('steps', 0)} optimization cycles.")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Final ROAS",
            f"{results.get('final_roas', 0):.2f}",
            f"+{results.get('roas_improvement', 0):.1f}%"
        )
    
    with col2:
        st.metric(
            "Total Revenue",
            f"${results.get('total_revenue', 0):,.0f}",
            None
        )
    
    with col3:
        st.metric(
            "Total Spend",
            f"${results.get('total_spend', 0):,.0f}",
            None
        )
    
    with col4:
        st.metric(
            "Conversions",
            f"{results.get('total_conversions', 0):,}",
            None
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Arms performance and allocation
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.markdown("#### Arm Allocations")
        
        arm_results = results.get('arm_results', [])
        if arm_results:
            # Allocation pie chart
            fig = go.Figure(data=[go.Pie(
                labels=[a['name'] for a in arm_results],
                values=[a['final_allocation'] * 100 for a in arm_results],
                hole=0.4,
                textinfo='percent+label',
                textposition='outside'
            )])
            fig.update_layout(
                showlegend=False,
                margin=dict(t=20, b=20, l=20, r=20),
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Arm details table
            st.markdown("#### Arm Performance Details")
            
            arm_df = pd.DataFrame([
                {
                    'Arm': a['name'],
                    'Allocation': f"{a['final_allocation']*100:.1f}%",
                    'ROAS': f"{a['roas']:.2f}",
                    'Spend': f"${a['spend']:,.0f}",
                    'Revenue': f"${a['revenue']:,.0f}",
                    'Conv.': a['conversions']
                }
                for a in arm_results
            ])
            st.dataframe(arm_df, use_container_width=True, hide_index=True)
    
    with col_right:
        st.markdown("#### 🎯 Recommendations")
        
        recommendations = results.get('recommendations', [])
        
        if recommendations:
            for rec in recommendations:
                rec_type_icons = {
                    'increase': '📈',
                    'decrease': '📉',
                    'maintain': '✓',
                    'watch': '👁️'
                }
                icon = rec_type_icons.get(rec.get('type', 'maintain'), '💡')
                
                with st.container(border=True):
                    st.markdown(f"**{icon} {rec['title']}**")
                    st.caption(rec['description'])
                    st.markdown(f"*Expected Impact: {rec.get('impact', 'N/A')}*")
        else:
            st.info("No specific recommendations at this time.")
        
        # ROAS over time chart
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### ROAS Over Time")
        
        roas_history = results.get('roas_history', [])
        if roas_history:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=list(range(len(roas_history))),
                y=roas_history,
                mode='lines',
                line=dict(color='#9b4819', width=2),
                fill='tozeroy',
                fillcolor='rgba(155, 72, 25, 0.1)'
            ))
            fig.update_layout(
                margin=dict(t=10, b=30, l=40, r=10),
                height=200,
                xaxis_title="Step",
                yaxis_title="ROAS"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Navigation
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("🔄 Run Again", use_container_width=True):
            st.session_state.optimization_running = True
            st.rerun()
    
    with col2:
        if st.button("⚙️ Modify Settings", use_container_width=True):
            st.session_state.onboarding_step = 3
            st.rerun()
    
    with col3:
        if st.button("📊 Go to Dashboard", type="primary", use_container_width=True):
            # Save results and go to main dashboard
            st.session_state.current_page = "home"
            st.session_state.onboarding_complete = True
            st.rerun()


# ============================================================================
# Helper Functions
# ============================================================================

def validate_data(data: dict, data_type: str) -> dict:
    """Validate uploaded data."""
    errors = []
    
    if data_type == 'json':
        # Check for required keys
        if 'historical_performance' not in data and 'platform_channel_combinations' not in data:
            errors.append("Missing 'historical_performance' or 'platform_channel_combinations' key")
        
        # Check for metrics in entries
        perf_key = 'historical_performance' if 'historical_performance' in data else 'platform_channel_combinations'
        if perf_key in data:
            for key, metrics in data[perf_key].items():
                if 'historical_ctr' not in metrics and 'ctr' not in metrics:
                    errors.append(f"Missing CTR data for {key}")
                    break
    else:
        # CSV validation
        required_cols = ['platform', 'channel']
        if isinstance(data, list) and len(data) > 0:
            first_row = data[0]
            for col in required_cols:
                if col not in first_row:
                    errors.append(f"Missing required column: {col}")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


def extract_data_insights(data: dict, data_type: str) -> list:
    """Extract key insights from the data."""
    insights = []
    
    if data_type == 'json':
        perf_key = 'historical_performance' if 'historical_performance' in data else 'platform_channel_combinations'
        if perf_key in data:
            perf_data = data[perf_key]
            
            # Count entries
            insights.append(f"**{len(perf_data)}** ad variations found")
            
            # Calculate average ROAS
            roas_values = [m.get('historical_roas', 0) for m in perf_data.values()]
            if roas_values:
                avg_roas = sum(roas_values) / len(roas_values)
                insights.append(f"Average ROAS: **{avg_roas:.2f}**")
                
                # Best performer
                best_key = max(perf_data.keys(), key=lambda k: perf_data[k].get('historical_roas', 0))
                best_roas = perf_data[best_key].get('historical_roas', 0)
                insights.append(f"Best performer: **{best_key.split('_')[0]}** (ROAS: {best_roas:.2f})")
        
        # Seasonal data
        if 'seasonal_multipliers' in data:
            insights.append("✓ Seasonal patterns included")
    
    return insights


def get_platform_performance(data: dict, data_type: str) -> list:
    """Get platform performance for charting."""
    from collections import defaultdict
    
    platform_metrics = defaultdict(list)
    
    if data_type == 'json':
        perf_key = 'historical_performance' if 'historical_performance' in data else 'platform_channel_combinations'
        if perf_key in data:
            for key, metrics in data[perf_key].items():
                platform = key.split('_')[0]
                roas = metrics.get('historical_roas', 0)
                platform_metrics[platform].append(roas)
    
    # Calculate averages
    result = []
    for platform, roas_list in platform_metrics.items():
        result.append({
            'platform': platform,
            'roas': sum(roas_list) / len(roas_list) if roas_list else 0
        })
    
    return result


def extract_arms_from_data(data: dict, data_type: str) -> list:
    """Extract arm definitions from uploaded data."""
    arms = []
    
    if data_type == 'json':
        perf_key = 'historical_performance' if 'historical_performance' in data else 'platform_channel_combinations'
        if perf_key in data:
            for key, metrics in data[perf_key].items():
                parts = key.split('_')
                arms.append({
                    'name': key.replace('_', ' '),
                    'platform': parts[0] if len(parts) > 0 else 'Unknown',
                    'channel': parts[1] if len(parts) > 1 else 'Unknown',
                    'creative': parts[2] if len(parts) > 2 else 'Default',
                    'historical_roas': metrics.get('historical_roas', 1.0)
                })
    else:
        # CSV - extract unique combinations
        seen = set()
        for row in data:
            platform = row.get('platform', 'Unknown')
            channel = row.get('channel', 'Unknown')
            creative = row.get('creative', 'Default')
            key = f"{platform}_{channel}_{creative}"
            
            if key not in seen:
                seen.add(key)
                arms.append({
                    'name': key.replace('_', ' '),
                    'platform': platform,
                    'channel': channel,
                    'creative': creative,
                    'historical_roas': float(row.get('roas', 1.0)) if row.get('roas') else 1.0
                })
    
    return arms
