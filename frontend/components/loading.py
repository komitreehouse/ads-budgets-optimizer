"""
Loading and error handling components.
"""

import streamlit as st
from typing import Optional, Callable, Any
import time


def render_loading_spinner(message: str = "Loading..."):
    """Render a loading spinner."""
    return st.spinner(message)


def render_error_message(error: Exception, context: str = ""):
    """Render an error message with helpful context."""
    error_msg = str(error)
    
    st.error(f"""
    **Error {context if context else ''}**
    
    {error_msg}
    
    Please try refreshing the page or contact support if the issue persists.
    """)


def with_loading_state(func: Callable, *args, **kwargs) -> Any:
    """
    Wrapper to add loading state to a function call.
    
    Usage:
        result = with_loading_state(data_service.get_campaigns)
    """
    with st.spinner("Loading..."):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            render_error_message(e, f"in {func.__name__}")
            return None


def render_retry_button(on_retry: Callable, label: str = "Retry"):
    """Render a retry button."""
    if st.button(label, type="primary"):
        on_retry()
        st.rerun()


def render_empty_state(
    message: str,
    icon: str = "📊",
    action_label: Optional[str] = None,
    on_action: Optional[Callable] = None
):
    """
    Render an empty state message.
    
    Args:
        message: Message to display
        icon: Icon emoji
        action_label: Optional action button label
        on_action: Optional callback for action button
    """
    st.markdown(f"""
    <div style="text-align: center; padding: 60px 20px;">
        <div style="font-size: 4rem; margin-bottom: 16px;">{icon}</div>
        <p style="font-size: 1.125rem; color: #737373; margin: 0;">{message}</p>
    </div>
    """, unsafe_allow_html=True)
    
    if action_label and on_action:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button(action_label, use_container_width=True):
                on_action()
                st.rerun()
