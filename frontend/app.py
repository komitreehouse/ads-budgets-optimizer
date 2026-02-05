"""
Ads Budget Optimizer Dashboard - Streamlit MVP

A clean, modern dashboard for the ads budget optimization system.
Inspired by Mixpanel's design aesthetic.
"""

import streamlit as st
from datetime import datetime

# Page configuration - MUST be first Streamlit command
st.set_page_config(
    page_title="Ads Budget Optimizer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import pages after config
from pages import home, campaigns, campaign_detail, optimizer, ask, recommendations, onboarding
from frontend.components.chat_widget import render_chat_widget

# Custom CSS for Mixpanel-like styling
def load_custom_css():
    st.markdown("""
    <style>
    /* Main colors */
    :root {
        --primary: #7C3AED;
        --primary-light: #EDE9FE;
        --success: #22C55E;
        --warning: #F59E0B;
        --error: #EF4444;
        --gray-50: #FAFAFA;
        --gray-100: #F5F5F5;
        --gray-200: #E5E5E5;
        --gray-500: #737373;
        --gray-900: #171717;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: white;
        border-right: 1px solid #E5E5E5;
    }
    
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        font-size: 14px;
    }
    
    /* Main content area */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }
    
    /* Metric cards */
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #E5E5E5;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 600;
        color: #171717;
        margin: 0;
    }
    
    .metric-label {
        font-size: 0.875rem;
        color: #737373;
        margin-bottom: 4px;
    }
    
    .metric-trend-up {
        color: #22C55E;
        font-size: 0.875rem;
    }
    
    .metric-trend-down {
        color: #EF4444;
        font-size: 0.875rem;
    }
    
    /* Status badges */
    .status-active {
        background: #DCFCE7;
        color: #166534;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 500;
    }
    
    .status-paused {
        background: #FEF3C7;
        color: #92400E;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 500;
    }
    
    /* Cards */
    .card {
        background: white;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #E5E5E5;
        margin-bottom: 16px;
    }
    
    .card-header {
        font-size: 1.125rem;
        font-weight: 600;
        color: #171717;
        margin-bottom: 16px;
    }
    
    /* Explanation card */
    .explanation-card {
        background: #F5F3FF;
        border-left: 4px solid #7C3AED;
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
        background: #7C3AED;
        color: white;
        margin-left: 20%;
    }
    
    .chat-message-assistant {
        background: #F5F5F5;
        color: #171717;
        margin-right: 20%;
    }
    
    /* Recommendation card */
    .recommendation-card {
        background: white;
        border: 1px solid #E5E5E5;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    }
    
    .recommendation-card:hover {
        border-color: #7C3AED;
        box-shadow: 0 4px 12px rgba(124, 58, 237, 0.1);
    }
    
    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
    }
    
    .stButton > button[kind="primary"] {
        background-color: #7C3AED;
        color: white;
    }
    
    /* Navigation styling */
    .nav-link {
        display: flex;
        align-items: center;
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 4px;
        text-decoration: none;
        color: #737373;
        transition: all 0.2s;
    }
    
    .nav-link:hover {
        background: #F5F5F5;
        color: #171717;
    }
    
    .nav-link.active {
        background: #EDE9FE;
        color: #7C3AED;
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.25rem;
        font-weight: 600;
        color: #171717;
        margin-bottom: 16px;
    }
    
    /* Greeting */
    .greeting {
        font-size: 1.875rem;
        font-weight: 600;
        color: #171717;
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
        background: #E5E5E5;
        overflow: hidden;
    }
    
    .allocation-fill {
        height: 100%;
        border-radius: 4px;
        background: linear-gradient(90deg, #7C3AED, #A78BFA);
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
            <h1 style="font-size: 1.25rem; font-weight: 700; color: #7C3AED; margin: 0;">
                📊 Ads Optimizer
            </h1>
            <p style="font-size: 0.75rem; color: #737373; margin: 4px 0 0 0;">
                Budget Optimization Dashboard
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # Navigation
        pages = {
            "🏠 Home": "home",
            "📊 Campaigns": "campaigns",
            "🤖 Optimizer": "optimizer",
            "💬 Ask": "ask",
            "✓ Recommendations": "recommendations",
        }
        
        # Get current page from session state
        if "current_page" not in st.session_state:
            # Check if onboarding is complete, if not start with onboarding
            if not st.session_state.get("onboarding_complete", False):
                st.session_state.current_page = "onboarding"
            else:
                st.session_state.current_page = "home"
        
        # Onboarding / Data Upload button
        onboarding_complete = st.session_state.get("onboarding_complete", False)
        btn_label = "📤 Upload Data" if onboarding_complete else "🚀 Get Started"
        btn_type = "secondary" if onboarding_complete else "primary"
        
        if st.button(
            btn_label,
            key="nav_onboarding",
            use_container_width=True,
            type=btn_type
        ):
            st.session_state.current_page = "onboarding"
            # Reset onboarding state if re-entering
            if onboarding_complete:
                st.session_state.onboarding_step = 1
            st.rerun()
        
        st.divider()
        
        for label, page_key in pages.items():
            # Add badge for recommendations
            if page_key == "recommendations":
                pending_count = st.session_state.get("pending_recommendations", 0)
                if pending_count > 0:
                    label = f"{label} ({pending_count})"
            
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
    elif current_page == "campaigns":
        campaigns.render()
    elif current_page == "campaign_detail":
        campaign_detail.render(st.session_state.get("selected_campaign_id"))
    elif current_page == "optimizer":
        optimizer.render()
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
        "home": "dashboard overview",
        "campaigns": "campaigns list",
        "campaign_detail": f"campaign {campaign_id}",
        "optimizer": "optimizer status",
        "recommendations": "recommendations",
        "ask": "ask page"
    }
    
    context = context_map.get(current_page, "the platform")
    
    # Render as floating button in sidebar or top-right
    with st.sidebar:
        st.markdown("<br>", unsafe_allow_html=True)
        render_chat_widget(campaign_id=campaign_id, context=context)


if __name__ == "__main__":
    main()
