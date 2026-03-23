"""
IPSA - Budget Optimizer Dashboard

A clean, modern dashboard for the ads budget optimization system.
"""

import streamlit as st
from datetime import datetime

# Page configuration - MUST be first Streamlit command
st.set_page_config(
    page_title="Ipsa | Budget Optimizer",
    page_icon="○",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import pages after config
from pages import home, campaigns, campaign_detail, optimizer, ask, recommendations, onboarding, incrementality, data_sources, planning, mmm_insights
from frontend.components.chat_widget import render_chat_widget

# Custom CSS for IPSA brand styling
def load_custom_css():
    st.markdown("""
    <style>
    /* Import Radley font */
    @import url('https://fonts.googleapis.com/css2?family=Radley:ital@0;1&family=Inter:wght@400;500;600;700&display=swap');
    
    /* IPSA Brand Colors */
    :root {
        --primary: #9b4819;           /* Terracotta */
        --primary-light: #bd8f53;      /* Golden Tan */
        --background: #f4f1e8;         /* Cream/Beige */
        --card-bg: #ffffff;            /* White */
        --muted-bg: #ececf0;           /* Light Gray */
        --muted-fg: #717182;           /* Medium Gray */
        --accent: #e9ebef;             /* Light Blue-Gray */
        --destructive: #d4183d;        /* Red */
        --success: #22C55E;            /* Green */
        --warning: #F59E0B;            /* Amber */
        --foreground: #1a1a1a;         /* Near Black */
        --switch-bg: #cbced4;          /* Gray */
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Global font settings */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: var(--foreground);
    }
    
    /* Ensure all text is dark on light backgrounds */
    p, span, div, label, .stMarkdown, [data-testid="stMarkdownContainer"] {
        color: var(--foreground) !important;
    }
    
    /* Headers should be dark */
    h1, h2, h3, h4, h5, h6 {
        color: var(--foreground) !important;
    }
    
    /* Headings use Radley */
    h1, h2, h3, h4, .greeting, .card-header, .section-header {
        font-family: 'Radley', Georgia, serif !important;
        font-weight: 400 !important;
    }
    
    /* Main app background */
    .stApp {
        background-color: var(--background);
    }
    
    .main .block-container {
        background-color: var(--background);
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: var(--card-bg);
        border-right: 1px solid var(--muted-bg);
    }
    
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        font-size: 14px;
        color: var(--foreground);
    }
    
    /* Logo/Brand text in sidebar */
    .sidebar-brand {
        font-family: 'Radley', Georgia, serif;
        color: var(--primary);
    }
    
    /* Metric cards */
    .metric-card {
        background: var(--card-bg);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        border: 1px solid var(--muted-bg);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 600;
        color: var(--foreground);
        margin: 0;
    }
    
    .metric-label {
        font-size: 0.875rem;
        color: var(--muted-fg);
        margin-bottom: 4px;
    }
    
    .metric-trend-up {
        color: var(--success);
        font-size: 0.875rem;
    }
    
    .metric-trend-down {
        color: var(--destructive);
        font-size: 0.875rem;
    }
    
    /* Status badges */
    .status-active {
        background: #e8f5e9;
        color: #2e7d32;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 500;
    }
    
    .status-paused {
        background: #fff3e0;
        color: #e65100;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 500;
    }
    
    /* Cards */
    .card {
        background: var(--card-bg);
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        border: 1px solid var(--muted-bg);
        margin-bottom: 16px;
    }
    
    .card-header {
        font-family: 'Radley', Georgia, serif;
        font-size: 1.125rem;
        font-weight: 400;
        color: var(--foreground);
        margin-bottom: 16px;
    }
    
    /* Explanation card */
    .explanation-card {
        background: #fdf6f0;
        border-left: 4px solid var(--primary);
        padding: 16px 20px;
        border-radius: 0 8px 8px 0;
        margin: 16px 0;
    }
    
    /* Chat messages */
    .chat-message {
        padding: 16px;
        border-radius: 12px;
        margin-bottom: 12px;
    }
    
    .chat-message-user {
        background: var(--primary);
        color: white !important;
        margin-left: 20%;
    }
    
    .chat-message-user p, .chat-message-user span, .chat-message-user div {
        color: white !important;
    }
    
    .chat-message-assistant {
        background: var(--muted-bg);
        color: var(--foreground);
        margin-right: 20%;
    }
    
    /* Streamlit chat message styling */
    [data-testid="stChatMessage"] {
        background-color: var(--card-bg);
        border: 1px solid var(--muted-bg);
        border-radius: 12px;
    }
    
    [data-testid="stChatMessage"] p {
        color: var(--foreground) !important;
    }
    
    /* Recommendation card */
    .recommendation-card {
        background: var(--card-bg);
        border: 1px solid var(--muted-bg);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    }
    
    .recommendation-card:hover {
        border-color: var(--primary);
        box-shadow: 0 4px 12px rgba(155, 72, 25, 0.1);
    }
    
    /* Buttons - Primary */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        font-family: 'Inter', sans-serif;
        color: var(--foreground);
    }
    
    .stButton > button[kind="primary"], 
    .stButton > button[data-testid="baseButton-primary"] {
        background-color: var(--primary) !important;
        color: white !important;
        border: none !important;
    }
    
    .stButton > button[kind="primary"] p,
    .stButton > button[data-testid="baseButton-primary"] p {
        color: white !important;
    }
    
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {
        background-color: #7d3a14 !important;
    }
    
    /* Buttons - Secondary */
    .stButton > button[kind="secondary"],
    .stButton > button[data-testid="baseButton-secondary"] {
        background-color: var(--card-bg) !important;
        color: var(--foreground) !important;
        border: 1px solid var(--muted-bg) !important;
    }
    
    .stButton > button[kind="secondary"] p,
    .stButton > button[data-testid="baseButton-secondary"] p {
        color: var(--foreground) !important;
    }
    
    .stButton > button[kind="secondary"]:hover,
    .stButton > button[data-testid="baseButton-secondary"]:hover {
        background-color: var(--muted-bg) !important;
    }
    
    /* Default button text color (for tertiary/default buttons) */
    .stButton > button p {
        color: var(--foreground) !important;
    }
    
    /* Navigation styling */
    .nav-link {
        display: flex;
        align-items: center;
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 4px;
        text-decoration: none;
        color: var(--muted-fg);
        transition: all 0.2s;
    }
    
    .nav-link:hover {
        background: var(--muted-bg);
        color: var(--foreground);
    }
    
    .nav-link.active {
        background: #fdf6f0;
        color: var(--primary);
    }
    
    /* Section headers */
    .section-header {
        font-family: 'Radley', Georgia, serif;
        font-size: 1.25rem;
        font-weight: 400;
        color: var(--foreground);
        margin-bottom: 16px;
    }
    
    /* Greeting */
    .greeting {
        font-family: 'Radley', Georgia, serif;
        font-size: 1.875rem;
        font-weight: 400;
        color: var(--foreground);
        margin-bottom: 24px;
    }
    
    /* Platform icons */
    .platform-google { color: #4285F4; }
    .platform-meta { color: #1877F2; }
    .platform-ttd { color: #00A98F; }
    
    /* Progress bars for allocation */
    .allocation-bar {
        height: 8px;
        border-radius: 4px;
        background: var(--muted-bg);
        overflow: hidden;
    }
    
    .allocation-fill {
        height: 100%;
        border-radius: 4px;
        background: linear-gradient(90deg, var(--primary), var(--primary-light));
    }
    
    /* Form inputs */
    .stTextInput > div > div > input,
    .stSelectbox > div > div > div,
    .stNumberInput > div > div > input {
        background-color: var(--card-bg);
        border: 1px solid var(--muted-bg);
        border-radius: 8px;
        color: var(--foreground) !important;
    }
    
    .stTextInput > div > div > input::placeholder {
        color: var(--muted-fg) !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stSelectbox > div > div > div:focus {
        border-color: var(--primary);
        box-shadow: 0 0 0 2px rgba(155, 72, 25, 0.1);
    }
    
    /* Selectbox text */
    .stSelectbox [data-baseweb="select"] span {
        color: var(--foreground) !important;
    }
    
    /* Labels for inputs */
    .stTextInput label, .stSelectbox label, .stNumberInput label {
        color: var(--foreground) !important;
    }
    
    /* File uploader */
    .stFileUploader > div {
        background-color: var(--card-bg);
        border: 2px dashed var(--muted-bg);
        border-radius: 12px;
    }
    
    .stFileUploader > div:hover {
        border-color: var(--primary);
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 8px;
        color: var(--muted-fg);
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: var(--card-bg);
        color: var(--primary);
    }
    
    /* Dataframes */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        color: var(--foreground);
    }
    
    /* Metrics (Streamlit native) */
    [data-testid="stMetricValue"] {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        color: var(--foreground);
    }
    
    [data-testid="stMetricLabel"] {
        color: var(--muted-fg);
    }
    
    /* Progress step indicator */
    .progress-step {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        border-radius: 50%;
        font-weight: 600;
    }
    
    .progress-step-active {
        background: var(--primary);
        color: white !important;
    }
    
    .progress-step-active span, .progress-step-active p {
        color: white !important;
    }
    
    .progress-step-complete {
        background: var(--success);
        color: white !important;
    }
    
    .progress-step-complete span, .progress-step-complete p {
        color: white !important;
    }
    
    .progress-step-pending {
        background: var(--muted-bg);
        color: var(--muted-fg) !important;
    }
    
    /* Slider */
    .stSlider > div > div > div > div {
        background-color: var(--primary);
    }

    /* Toggle */
    .stCheckbox > label > div[data-testid="stCheckbox"] > div {
        background-color: var(--primary);
    }

    /* ================================================================
       DARK MODE OVERRIDE — force all interactive elements to light
       ================================================================ */

    /* Force the entire app background to cream */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        background-color: var(--background) !important;
    }

    /* Sidebar always white */
    [data-testid="stSidebar"] {
        background-color: var(--card-bg) !important;
    }

    /* All block containers: cream background, dark text */
    [data-testid="block-container"], .block-container {
        background-color: var(--background) !important;
        color: var(--foreground) !important;
    }

    /* Native Streamlit metric cards — force white bg, dark text */
    [data-testid="stMetric"],
    [data-testid="metric-container"] {
        background-color: var(--card-bg) !important;
        border: 1px solid var(--muted-bg) !important;
        border-radius: 12px !important;
        padding: 16px !important;
        color: var(--foreground) !important;
    }

    [data-testid="stMetricValue"],
    [data-testid="stMetricLabel"],
    [data-testid="stMetricDelta"] {
        color: var(--foreground) !important;
    }

    /* Selectbox / dropdown — control and popup list */
    [data-baseweb="select"] > div,
    [data-baseweb="select"] [data-baseweb="select"] {
        background-color: var(--card-bg) !important;
        color: var(--foreground) !important;
    }

    /* Dropdown popover / listbox */
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    [role="listbox"],
    [data-baseweb="list"] {
        background-color: var(--card-bg) !important;
        color: var(--foreground) !important;
        border: 1px solid var(--muted-bg) !important;
    }

    /* Individual dropdown options */
    [role="option"],
    [data-baseweb="menu-item"],
    li[role="option"] {
        background-color: var(--card-bg) !important;
        color: var(--foreground) !important;
    }

    [role="option"]:hover,
    [data-baseweb="menu-item"]:hover {
        background-color: var(--muted-bg) !important;
    }

    /* Selected option highlight */
    [aria-selected="true"][role="option"] {
        background-color: #fdf6f0 !important;
        color: var(--primary) !important;
    }

    /* All text inputs */
    input, textarea, [data-baseweb="textarea"] textarea {
        background-color: var(--card-bg) !important;
        color: var(--foreground) !important;
        border-color: var(--muted-bg) !important;
    }

    /* Expanders */
    [data-testid="stExpander"] {
        background-color: var(--card-bg) !important;
        border: 1px solid var(--muted-bg) !important;
        border-radius: 8px !important;
    }

    [data-testid="stExpander"] summary {
        color: var(--foreground) !important;
    }

    /* Tabs */
    [data-baseweb="tab-panel"] {
        background-color: var(--background) !important;
    }

    /* Alert / info / success / warning boxes */
    [data-testid="stAlert"] {
        color: var(--foreground) !important;
    }

    /* Dataframe */
    [data-testid="stDataFrame"] * {
        color: var(--foreground) !important;
    }

    /* Generic catch-all: any element that Streamlit renders with a dark bg */
    .stMarkdown, .stText, .stCaption {
        color: var(--foreground) !important;
    }

    /* Spinner text */
    [data-testid="stSpinner"] {
        color: var(--foreground) !important;
    }

    /* Divider */
    hr {
        border-color: var(--muted-bg) !important;
    }
    </style>
    """, unsafe_allow_html=True)


def get_time_greeting():
    """Return time-based greeting."""
    hour = datetime.now().hour
    if hour < 12:
        return "Good Morning"
    elif hour < 17:
        return "Good Afternoon"
    else:
        return "Good Evening"


def render_sidebar():
    """Render the navigation sidebar."""
    with st.sidebar:
        # Logo / Brand
        st.markdown("""
        <div style="padding: 16px 0 24px 0;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 1.5rem; color: #9b4819;">○</span>
                <h1 style="font-family: 'Radley', Georgia, serif; font-size: 1.5rem; font-weight: 400; color: #9b4819; margin: 0;">
                    Ipsa
                </h1>
            </div>
            <p style="font-size: 0.75rem; color: #717182; margin: 4px 0 0 0;">
                Incremental performance, explained.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # Navigation
        pages = {
            "🏠 Home": "home",
            "🗂 Data Sources": "data_sources",
            "✓ Actions": "recommendations",
            "📈 Planning": "planning",
            "🧮 MMM Insights": "mmm_insights",
            "📊 Campaigns": "campaigns",
            "🧪 Incrementality": "incrementality",
            "💬 Ask": "ask",
        }

        # Get current page from session state
        if "current_page" not in st.session_state:
            st.session_state.current_page = "home"

        # Demo entry — only shown when running on mock/sample data
        from frontend.services.data_service import DataService as _DS
        _demo_svc = _DS()
        if _demo_svc.use_mock:
            if st.button(
                "🎬 Demo",
                key="nav_demo",
                use_container_width=True,
                type="primary" if st.session_state.get("current_page") == "onboarding" else "secondary",
            ):
                st.session_state.current_page = "onboarding"
                st.session_state.onboarding_step = 1
                st.rerun()

        st.divider()

        for label, page_key in pages.items():
            # Add badge for recommendations
            if page_key == "recommendations":
                pending_count = st.session_state.get("pending_recommendations", 0)
                if pending_count > 0:
                    label = f"✓ Actions ({pending_count})"

            if st.button(
                label,
                key=f"nav_{page_key}",
                use_container_width=True,
                type="primary" if st.session_state.current_page == page_key else "secondary"
            ):
                st.session_state.current_page = page_key
                # Clear campaign selection when going to campaigns list
                if page_key == "campaigns":
                    st.session_state.selected_campaign_id = None
                st.rerun()
        
        st.divider()
        
        # Pinned Campaigns
        st.markdown("**📌 Pinned**")
        pinned_campaigns = st.session_state.get("pinned_campaigns", [])
        if pinned_campaigns:
            for camp in pinned_campaigns[:5]:
                if st.button(f"  {camp['name']}", key=f"pinned_{camp['id']}", use_container_width=True):
                    st.session_state.selected_campaign_id = camp['id']
                    st.session_state.current_page = "campaign_detail"
                    st.rerun()
        else:
            st.caption("No pinned campaigns")
        
        st.divider()
        
        # Auto-refresh toggle
        st.markdown("**⚙️ Settings**")
        auto_refresh = st.toggle(
            "Auto-refresh (10s)",
            value=st.session_state.get("auto_refresh", True),
            key="auto_refresh_toggle"
        )
        st.session_state.auto_refresh = auto_refresh
        
        # Last refresh time
        if "last_refresh" in st.session_state:
            st.caption(f"Last: {st.session_state.last_refresh.strftime('%H:%M:%S')}")


def main():
    """Main application entry point."""
    # Load custom CSS
    load_custom_css()
    
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = datetime.now()
    
    # Render sidebar
    render_sidebar()
    
    # Auto-refresh mechanism
    if st.session_state.get("auto_refresh", True):
        # Update last refresh time
        st.session_state.last_refresh = datetime.now()
        
        # Add auto-refresh using st.empty() and time-based rerun
        # This is a placeholder - actual implementation uses st_autorefresh
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=10000, key="datarefresh")  # 10 seconds
        except ImportError:
            # Fallback: manual refresh button
            pass
    
    # Route to appropriate page
    current_page = st.session_state.get("current_page", "home")
    
    # Check if viewing a specific campaign
    if st.session_state.get("selected_campaign_id") and current_page != "campaigns":
        current_page = "campaign_detail"
    
    # Global chat widget (accessible on all pages except onboarding)
    if current_page != "onboarding":
        render_global_chat_widget()
    
    # Render page content
    if current_page == "onboarding":
        onboarding.render()
    elif current_page == "home":
        home.render(get_time_greeting())
    elif current_page == "data_sources":
        data_sources.render()
    elif current_page == "planning":
        planning.render()
    elif current_page == "mmm_insights":
        mmm_insights.render()
    elif current_page == "campaigns":
        campaigns.render()
    elif current_page == "campaign_detail":
        campaign_detail.render(st.session_state.get("selected_campaign_id"))
    elif current_page == "optimizer":
        optimizer.render()
    elif current_page == "incrementality":
        incrementality.render()
    elif current_page == "ask":
        ask.render()
    elif current_page == "recommendations":
        recommendations.render()
    else:
        home.render(get_time_greeting())


def render_global_chat_widget():
    """Render global chat widget accessible on all pages."""
    from frontend.components.chat_widget import render_chat_widget
    
    # Get context based on current page
    current_page = st.session_state.get("current_page", "home")
    campaign_id = st.session_state.get("selected_campaign_id")
    
    context_map = {
        "home": "budget command center",
        "data_sources": "data sources",
        "planning": "planning and forecasting",
        "campaigns": "campaigns list",
        "campaign_detail": f"campaign {campaign_id}",
        "optimizer": "optimizer status",
        "recommendations": "action center",
        "ask": "ask page",
        "incrementality": "incrementality experiments",
    }
    
    context = context_map.get(current_page, "the platform")
    
    # Render as floating button in sidebar or top-right
    with st.sidebar:
        st.markdown("<br>", unsafe_allow_html=True)
        render_chat_widget(campaign_id=campaign_id, context=context)


if __name__ == "__main__":
    main()
