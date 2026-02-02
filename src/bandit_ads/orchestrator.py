"""
Central Orchestrator Agent

Coordinates multiple agents and tools to handle user queries.
Routes queries to appropriate LLM, manages tool calls, and synthesizes responses.
"""

import json
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from src.bandit_ads.llm_router import get_llm_router, QueryType
from src.bandit_ads.mcp_server import get_mcp_server
from src.bandit_ads.vector_store import get_vector_store
from src.bandit_ads.research_tools import get_research_tools
from src.bandit_ads.auth import get_auth_manager
from src.bandit_ads.explanation_generator import get_explanation_generator
from src.bandit_ads.utils import get_logger, ConfigManager

logger = get_logger('orchestrator')


class OrchestratorAgent:
    """
    Central orchestrator that coordinates LLM agents and tools.
    
    Responsibilities:
    - Query understanding and routing
    - LLM selection (Claude vs GPT-4)
    - Tool orchestration (MCP, RAG, Research)
    - Response synthesis
    - Context management
    """
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize orchestrator."""
        self.config_manager = config_manager or ConfigManager()
        self.llm_router = get_llm_router()
        self.mcp_server = get_mcp_server(config_manager)
        
        # Vector store is optional - may not be installed
        try:
            self.vector_store = get_vector_store()
        except ImportError:
            logger.warning("Vector store not available - RAG context will be disabled")
            self.vector_store = None
        
        self.research_tools = get_research_tools()
        self.auth_manager = get_auth_manager()
        self.explanation_generator = get_explanation_generator(config_manager)
        
        # LLM clients
        self.claude_client = None
        self.openai_client = None
        self._init_llm_clients()
        
        logger.info("Orchestrator agent initialized")
    
    def _init_llm_clients(self):
        """Initialize LLM API clients."""
        try:
            import anthropic
            claude_key = os.getenv("ANTHROPIC_API_KEY") or self.config_manager.get("interpretability.llm.claude_api_key")
            if claude_key:
                self.claude_client = anthropic.Anthropic(api_key=claude_key)
                logger.info("Claude client initialized")
        except ImportError:
            logger.warning("anthropic library not installed")
        except Exception as e:
            logger.warning(f"Failed to initialize Claude client: {str(e)}")
        
        try:
            import openai
            openai_key = os.getenv("OPENAI_API_KEY") or self.config_manager.get("interpretability.llm.openai_api_key")
            if openai_key:
                self.openai_client = openai.OpenAI(api_key=openai_key)
                logger.info("OpenAI client initialized")
        except ImportError:
            logger.warning("openai library not installed")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI client: {str(e)}")
    
    async def process_query(
        self,
        query: str,
        user_token: Optional[str] = None,
        campaign_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a user query end-to-end.
        
        Args:
            query: User query string
            user_token: User authentication token
            campaign_id: Optional campaign ID for context
            context: Additional context
        
        Returns:
            Response dictionary with answer and metadata
        """
        start_time = datetime.now()
        
        try:
            # 1. Authenticate user (if token provided)
            user = None
            if user_token:
                user = self.auth_manager.get_user_from_token(user_token)
                if not user:
                    return {
                        "error": "Authentication failed",
                        "answer": None
                    }
            
            # 2. Check access (if campaign_id provided)
            if user and campaign_id:
                has_access = self.auth_manager.check_access(user, campaign_id, operation="read")
                if not has_access:
                    return {
                        "error": "Access denied",
                        "answer": None
                    }
            
            # 3. Classify query and select LLM
            query_type = self.llm_router.classify_query(query)
            model = self.llm_router.select_model(query)
            
            logger.info(f"Query classified as: {query_type.value}, using model: {model}")
            
            # 4. Check if should use direct API (fast path)
            if self.llm_router.should_use_direct_api(query):
                return await self._process_direct_query(query, campaign_id)
            
            # 5. Retrieve relevant context from RAG
            rag_context = None
            if query_type in [QueryType.EXPLANATION, QueryType.ANALYSIS] and self.vector_store:
                try:
                    rag_results = self.vector_store.search_similar_decisions(
                        query, campaign_id=campaign_id, top_k=3
                    )
                except Exception as e:
                    logger.debug(f"Could not retrieve RAG context: {e}")
                    rag_results = None
            else:
                rag_results = None
                if rag_results:
                    rag_context = self._format_rag_context(rag_results)
            
            # 6. Build tool context (available MCP tools)
            tool_context = self._build_tool_context()
            
            # 7. Call appropriate LLM with context
            if "claude" in model.lower():
                response = await self._call_claude(query, tool_context, rag_context, campaign_id)
            elif "gpt" in model.lower():
                response = await self._call_gpt4(query, tool_context, rag_context, campaign_id)
            else:
                response = {"error": f"Unknown model: {model}"}
            
            # 8. Process tool calls if LLM requested them
            if response.get("tool_calls"):
                tool_results = await self._execute_tool_calls(
                    response["tool_calls"],
                    user_id=user.id if user else None
                )
                # Synthesize final response with tool results
                final_response = await self._synthesize_response(
                    query, response, tool_results, model
                )
            else:
                final_response = response
            
            # 9. Return response
            duration = (datetime.now() - start_time).total_seconds()
            
            return {
                "answer": final_response.get("answer", ""),
                "query_type": query_type.value,
                "model_used": model,
                "tool_calls": response.get("tool_calls", []),
                "rag_context_used": rag_context is not None,
                "duration_seconds": duration,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}", exc_info=True)
            return {
                "error": str(e),
                "answer": None
            }
    
    async def _process_direct_query(
        self,
        query: str,
        campaign_id: Optional[int]
    ) -> Dict[str, Any]:
        """Process simple queries using direct API (bypass LLM)."""
        # Extract metric name from query
        import re
        metric_match = re.search(r"(roas|ctr|cvr|revenue|cost|impressions|clicks|conversions)", query.lower())
        if metric_match and campaign_id:
            metric = metric_match.group(1)
            # Use MCP tool directly
            result = await self.mcp_server.operations.query_metrics(
                campaign_id=campaign_id,
                metric=metric,
                time_range="7d"
            )
            return {
                "answer": result[0].get("text", ""),
                "query_type": "metric_query",
                "model_used": "direct_api",
                "tool_calls": [],
                "rag_context_used": False
            }
        return {"error": "Could not process direct query"}
    
    def _format_rag_context(self, rag_results: List[Dict[str, Any]]) -> str:
        """Format RAG results as context string."""
        context_parts = ["**Relevant Past Decisions:**\n"]
        for i, result in enumerate(rag_results, 1):
            context_parts.append(f"{i}. {result.get('text', '')[:200]}...")
        return "\n".join(context_parts)
    
    def _build_tool_context(self) -> str:
        """Build description of available tools."""
        return """
Available Tools (via MCP):
- get_campaign_status(campaign_id): Get campaign status
- get_allocation_history(campaign_id, days): Get allocation changes
- get_arm_performance(arm_id, start_date, end_date): Get arm metrics
- query_metrics(campaign_id, metric, time_range): Query specific metrics
- explain_allocation_change(change_id): Explain why allocation changed
- explain_performance(campaign_id, arm_id, time_range): Explain performance
- suggest_allocation_override(campaign_id, arm_id, new_allocation, justification): Suggest override
- pause_campaign(campaign_id, reason): Pause campaign
- resume_campaign(campaign_id, reason): Resume campaign
- web_search(query, max_results): Search the web
- analyze_trend(keyword, timeframe, geo): Analyze Google Trends
"""
    
    async def _call_claude(
        self,
        query: str,
        tool_context: str,
        rag_context: Optional[str],
        campaign_id: Optional[int]
    ) -> Dict[str, Any]:
        """Call Claude API."""
        if not self.claude_client:
            return {"error": "Claude client not initialized"}
        
        # Build system message
        system_parts = [
            "You are an expert advertising optimization analyst assistant.",
            "You help analysts understand and interact with the budget optimizer system.",
            tool_context
        ]
        
        if rag_context:
            system_parts.append("\n" + rag_context)
        
        if campaign_id:
            system_parts.append(f"\nCurrent campaign context: Campaign ID {campaign_id}")
        
        system_message = "\n".join(system_parts)
        
        # Build user message
        user_message = query
        
        try:
            response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                system=system_message,
                messages=[{"role": "user", "content": user_message}]
            )
            
            answer = response.content[0].text if response.content else ""
            
            return {
                "answer": answer,
                "tool_calls": []  # Claude doesn't support tool calling in this version
            }
        except Exception as e:
            logger.error(f"Error calling Claude: {str(e)}")
            return {"error": str(e)}
    
    async def _call_gpt4(
        self,
        query: str,
        tool_context: str,
        rag_context: Optional[str],
        campaign_id: Optional[int]
    ) -> Dict[str, Any]:
        """Call GPT-4 API."""
        if not self.openai_client:
            return {"error": "OpenAI client not initialized"}
        
        # Build system message
        system_parts = [
            "You are an expert advertising optimization analyst assistant.",
            "You help analysts understand and optimize budget allocation.",
            tool_context
        ]
        
        if rag_context:
            system_parts.append("\n" + rag_context)
        
        system_message = "\n".join(system_parts)
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": query}
                ],
                temperature=0.7
            )
            
            answer = response.choices[0].message.content if response.choices else ""
            
            return {
                "answer": answer,
                "tool_calls": []  # Would parse function calls here
            }
        except Exception as e:
            logger.error(f"Error calling GPT-4: {str(e)}")
            return {"error": str(e)}
    
    async def _execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Execute tool calls requested by LLM."""
        results = []
        for tool_call in tool_calls:
            try:
                tool_name = tool_call.get("name")
                arguments = tool_call.get("arguments", {})
                
                # Add user_id to arguments if available
                if user_id and "user_id" not in arguments:
                    arguments["user_id"] = user_id
                
                # Call MCP tool
                result = await self.mcp_server.operations.__getattribute__(f"_{tool_name}")(**arguments)
                results.append({
                    "tool": tool_name,
                    "result": result
                })
            except Exception as e:
                logger.error(f"Error executing tool {tool_call.get('name')}: {str(e)}")
                results.append({
                    "tool": tool_call.get("name"),
                    "error": str(e)
                })
        return results
    
    async def _synthesize_response(
        self,
        query: str,
        initial_response: Dict[str, Any],
        tool_results: List[Dict[str, Any]],
        model: str
    ) -> Dict[str, Any]:
        """Synthesize final response using tool results."""
        # For now, just combine results
        # In production, would call LLM again with tool results
        answer_parts = [initial_response.get("answer", "")]
        
        if tool_results:
            answer_parts.append("\n\n**Tool Results:**")
            for result in tool_results:
                if "error" not in result:
                    answer_parts.append(f"- {result['tool']}: {result.get('result', '')}")
        
        return {
            "answer": "\n".join(answer_parts)
        }


# Global orchestrator instance
_orchestrator_instance: Optional[OrchestratorAgent] = None


def get_orchestrator(config_manager: Optional[ConfigManager] = None) -> OrchestratorAgent:
    """Get or create global orchestrator instance."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = OrchestratorAgent(config_manager)
    return _orchestrator_instance
