"""
Chat widget component for explanations and queries.
Accessible on all pages.
"""

import streamlit as st
from typing import Optional


def render_chat_widget(campaign_id: Optional[int] = None, context: str = ""):
    """
    Render a chat widget for asking questions and getting explanations.
    Accessible on all pages.
    
    Args:
        campaign_id: Optional campaign ID for context
        context: Additional context string
    """
    # Initialize chat state
    if 'chat_open' not in st.session_state:
        st.session_state.chat_open = False
    
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    
    # Context-aware title
    if campaign_id:
        title = f"💬 Ask about Campaign {campaign_id}"
    elif context:
        title = f"💬 Ask about {context}"
    else:
        title = "💬 Ask a Question"
    
    # Chat button
    if not st.session_state.chat_open:
        if st.button("💬 Ask", use_container_width=True, key="chat_toggle"):
            st.session_state.chat_open = True
            st.rerun()
    else:
        # Chat panel
        st.markdown(f"### {title}")
        
        # Display messages
        if st.session_state.chat_messages:
            st.markdown("**Conversation:**")
            for msg in st.session_state.chat_messages[-5:]:  # Show last 5
                role = msg.get('role', 'assistant')
                content = msg.get('content', '')
                
                if role == 'user':
                    st.markdown(f"**You:** {content}")
                else:
                    st.markdown(f"**Assistant:** {content}")
        else:
            st.info("Start a conversation by asking a question below.")
        
        # Suggested questions
        if not st.session_state.chat_messages:
            st.markdown("**Suggested questions:**")
            suggestions = [
                "What's the current performance?",
                "Why did ROAS change?",
                "Show me top performing channels",
                "What are the recent optimizations?"
            ]
            
            for suggestion in suggestions:
                if st.button(f"💡 {suggestion}", key=f"suggest_{suggestion}", use_container_width=True):
                    st.session_state.chat_messages.append({
                        'role': 'user',
                        'content': suggestion
                    })
                    # TODO: Call orchestrator API
                    st.session_state.chat_messages.append({
                        'role': 'assistant',
                        'content': f"Based on {context}, I can help explain that. (Orchestrator integration pending)"
                    })
                    st.rerun()
        
        st.divider()
        
        # Input
        query = st.text_input(
            "Ask a question...",
            key="chat_input",
            placeholder="e.g., Why did ROAS drop last week?"
        )
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Send", use_container_width=True, key="chat_send"):
                if query:
                    # Add user message
                    st.session_state.chat_messages.append({
                        'role': 'user',
                        'content': query
                    })
                    
                    # TODO: Call orchestrator API
                    # For now, show placeholder response
                    st.session_state.chat_messages.append({
                        'role': 'assistant',
                        'content': f"Based on {context}, I can help explain that. (Orchestrator integration pending)"
                    })
                    st.rerun()
        
        with col2:
            if st.button("Close", use_container_width=True, key="chat_close"):
                st.session_state.chat_open = False
                st.rerun()
