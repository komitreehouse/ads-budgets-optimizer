"""
Ask Page - Natural Language Query Interface

Chat-like interface for asking questions about campaigns and optimizer behavior.
"""

import streamlit as st
from datetime import datetime
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from frontend.services.data_service import DataService
from frontend.components.loading import render_loading_spinner, render_error_message, render_empty_state, render_retry_button


def render():
    """Render the Ask (chat) page."""
    data_service = DataService()
    
    # Header
    st.markdown("## 💬 Ask about your campaigns")
    st.markdown("Ask questions in natural language about your campaigns, performance, and optimizer decisions.")
    
    # Campaign filter (optional)
    try:
        campaigns = data_service.get_campaigns()
    except Exception as e:
        render_error_message(e, "loading campaigns")
        campaigns = []
    campaign_options = ["All Campaigns"] + [c['name'] for c in campaigns]
    
    col1, col2 = st.columns([3, 1])
    with col2:
        selected_campaign = st.selectbox(
            "Campaign context",
            campaign_options,
            index=0,
            label_visibility="collapsed"
        )
    
    st.divider()
    
    # Chat container
    chat_container = st.container()
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display chat history
    with chat_container:
        for message in st.session_state.messages:
            render_chat_message(message)
        
        # Show suggested queries if no messages
        if not st.session_state.messages:
            st.markdown("### Suggested Questions")
            
            suggestions = [
                "Why did Google Search budget increase last week?",
                "Show me ROAS trends for the past month",
                "Compare Meta vs Google performance",
                "What's causing the recent drop in conversions?",
                "Explain the latest allocation changes",
                "Which arms are performing best?"
            ]
            
            # Display as clickable chips
            cols = st.columns(2)
            for i, suggestion in enumerate(suggestions):
                with cols[i % 2]:
                    if st.button(f"💡 {suggestion}", key=f"suggest_{i}", use_container_width=True):
                        process_query(suggestion, selected_campaign, data_service)
                        st.rerun()
    
    st.markdown("<br>" * 3, unsafe_allow_html=True)
    
    # Input area (fixed at bottom)
    st.markdown("---")
    
    col1, col2 = st.columns([5, 1])
    
    with col1:
        user_input = st.text_input(
            "Ask a question",
            placeholder="e.g., Why did Google Search budget increase?",
            label_visibility="collapsed",
            key="chat_input"
        )
    
    with col2:
        send_clicked = st.button("Send 📤", type="primary", use_container_width=True)
    
    # Process input
    if send_clicked and user_input:
        process_query(user_input, selected_campaign, data_service)
        st.rerun()
    
    # Clear chat button
    if st.session_state.messages:
        if st.button("🗑 Clear Chat", type="secondary"):
            st.session_state.messages = []
            st.rerun()


def process_query(query: str, campaign_context: str, data_service: DataService):
    """Process a user query and get response."""
    # Add user message
    st.session_state.messages.append({
        "role": "user",
        "content": query,
        "timestamp": datetime.now()
    })
    
    # Get campaign ID if specific campaign selected
    campaign_id = None
    if campaign_context != "All Campaigns":
        try:
            campaigns = data_service.get_campaigns()
            for c in campaigns:
                if c['name'] == campaign_context:
                    campaign_id = c['id']
                    break
        except Exception as e:
            render_error_message(e, "loading campaign information")
            campaign_id = None
    
    # Get response from orchestrator with error handling
    try:
        with st.spinner("Thinking..."):
            response = data_service.query_orchestrator(query, campaign_id)
        
        # Add assistant message
        st.session_state.messages.append({
            "role": "assistant",
            "content": response.get("answer", "I couldn't process that query. Please try again."),
            "timestamp": datetime.now(),
            "metadata": {
                "query_type": response.get("query_type"),
                "model": response.get("model"),
                "tools_used": response.get("tools_used", []),
                "data": response.get("data")
            }
        })
    except Exception as e:
        render_error_message(e, "processing query")
        # Add error message to chat
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"I encountered an error while processing your query: {str(e)}. Please try rephrasing your question or try again later.",
            "timestamp": datetime.now(),
            "metadata": {
                "error": True
            }
        })


def render_chat_message(message: dict):
    """Render a chat message."""
    is_user = message["role"] == "user"
    
    # Use Streamlit's chat message for proper styling
    with st.chat_message("user" if is_user else "assistant"):
        st.markdown(message["content"])
        
        # Show metadata for assistant messages
        if not is_user and message.get("metadata"):
            metadata = message["metadata"]
            
            # Show any data visualizations
            if metadata.get("data"):
                data = metadata["data"]
                
                # If there's chart data, render it
                if data.get("chart_type") == "line":
                    render_inline_chart(data)
                elif data.get("table"):
                    st.dataframe(data["table"], use_container_width=True)
            
            # Show metadata footer
            st.markdown(f"""
            <div style="display: flex; gap: 16px; margin-top: 12px; font-size: 0.75rem; color: #737373;">
                <span>📅 {message['timestamp'].strftime('%H:%M')}</span>
                {f"<span>🤖 {metadata.get('model', 'Unknown')}</span>" if metadata.get('model') else ""}
                {f"<span>🔧 {', '.join(metadata.get('tools_used', []))}</span>" if metadata.get('tools_used') else ""}
            </div>
            """, unsafe_allow_html=True)
            
            # Feedback buttons
            col1, col2, col3 = st.columns([1, 1, 10])
            with col1:
                if st.button("👍", key=f"thumbs_up_{message['timestamp']}"):
                    st.toast("Thanks for the feedback!")
            with col2:
                if st.button("👎", key=f"thumbs_down_{message['timestamp']}"):
                    st.toast("Thanks for the feedback!")


def render_inline_chart(data: dict):
    """Render an inline chart in the chat."""
    import plotly.graph_objects as go
    import pandas as pd
    
    if data.get("chart_type") == "line":
        df = pd.DataFrame(data.get("values", []))
        
        if not df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df.get("x", df.index),
                y=df.get("y", df.iloc[:, 0]),
                mode='lines+markers',
                line=dict(color='#7C3AED', width=2)
            ))
            
            fig.update_layout(
                margin=dict(l=0, r=0, t=20, b=0),
                height=200,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='#E5E5E5'),
                plot_bgcolor='white'
            )
            
            st.plotly_chart(fig, use_container_width=True)
