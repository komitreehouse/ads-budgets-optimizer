"""
MCP Server for Human Interpretability Layer

Provides structured, type-safe access to optimizer operations via Model Context Protocol.
Supports read/write operations, explanations, and analyst feedback.
"""

import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum

# MCP SDK imports (will need to install)
try:
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.types import (
        Tool, TextContent, ImageContent, EmbeddedResource,
        LoggingLevel
    )
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    # Fallback classes for development when MCP SDK not installed
    print("Warning: MCP SDK not installed. Install with: pip install mcp")
    
    class Tool:
        """Mock Tool class."""
        def __init__(self, name: str, description: str, inputSchema: dict):
            self.name = name
            self.description = description
            self.inputSchema = inputSchema
    
    class TextContent:
        """Mock TextContent class."""
        def __init__(self, type: str = "text", text: str = ""):
            self.type = type
            self.text = text
    
    class Server:
        """Mock Server class."""
        def __init__(self, name: str):
            self.name = name
            self._tools = []
        
        def list_tools(self):
            def decorator(func):
                return func
            return decorator
        
        def call_tool(self):
            def decorator(func):
                return func
            return decorator
        
        def register_tools(self, tools):
            self._tools = tools
    
    class InitializationOptions:
        """Mock InitializationOptions class."""
        pass

from src.bandit_ads.optimization_service import get_optimization_service
from src.bandit_ads.database import get_db_manager
from src.bandit_ads.db_helpers import (
    get_campaign, get_arms_by_campaign,
    get_metrics_by_arm, get_agent_state
)
from src.bandit_ads.change_tracker import get_change_tracker
from src.bandit_ads.recommendations import get_recommendation_manager
from src.bandit_ads.research_tools import get_research_tools
from src.bandit_ads.auth import get_auth_manager
from src.bandit_ads.mcp_server_operations import MCPOperations
from src.bandit_ads.utils import get_logger, ConfigManager

logger = get_logger('mcp_server')


class QueryType(Enum):
    """Query type classification for LLM routing."""
    EXPLANATION = "explanation"  # Use Claude
    OPTIMIZATION = "optimization"  # Use GPT-4 Turbo
    ANALYSIS = "analysis"  # Use Claude
    RESEARCH = "research"  # Use Claude
    METRIC_QUERY = "metric_query"  # Use Claude or direct API


class OptimizerMCPServer:
    """
    MCP Server exposing optimizer operations as tools.
    
    Provides:
    - Read operations: Campaign status, allocation history, performance metrics
    - Write operations: Overrides, feedback, configuration changes
    - Explanation operations: Why decisions were made
    - Research operations: External trend analysis
    """
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize MCP server."""
        self.config_manager = config_manager or ConfigManager()
        self.server = Server("optimizer-interpretability") if MCP_AVAILABLE else None
        self.optimization_service = get_optimization_service(config_manager)
        self.change_tracker = get_change_tracker()
        self.recommendation_manager = get_recommendation_manager()
        self.research_tools = get_research_tools()
        self.auth_manager = get_auth_manager()
        self.operations = MCPOperations()
        
        if self.server:
            self._register_tools()
            logger.info("MCP server initialized")
        else:
            logger.warning("MCP server initialized in fallback mode (SDK not available)")
    
    def _register_tools(self):
        """Register all MCP tools."""
        # Read operations
        self._register_read_tools()
        # Write operations
        self._register_write_tools()
        # Explanation operations
        self._register_explanation_tools()
        # Research operations
        self._register_research_tools()
    
    def _register_read_tools(self):
        """Register read operation tools."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                Tool(
                    name="get_campaign_status",
                    description="Get current status and performance metrics for a campaign",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "campaign_id": {
                                "type": "integer",
                                "description": "Campaign ID"
                            }
                        },
                        "required": ["campaign_id"]
                    }
                ),
                Tool(
                    name="get_allocation_history",
                    description="Get allocation changes over time with explanations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "campaign_id": {
                                "type": "integer",
                                "description": "Campaign ID"
                            },
                            "days": {
                                "type": "integer",
                                "description": "Number of days to look back",
                                "default": 7
                            }
                        },
                        "required": ["campaign_id"]
                    }
                ),
                Tool(
                    name="get_arm_performance",
                    description="Get performance metrics for a specific arm",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "arm_id": {
                                "type": "integer",
                                "description": "Arm ID"
                            },
                            "start_date": {
                                "type": "string",
                                "description": "Start date (ISO format)",
                                "format": "date-time"
                            },
                            "end_date": {
                                "type": "string",
                                "description": "End date (ISO format)",
                                "format": "date-time"
                            }
                        },
                        "required": ["arm_id", "start_date", "end_date"]
                    }
                ),
                Tool(
                    name="query_metrics",
                    description="Query specific metrics (ROAS, CTR, CVR, etc.)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "campaign_id": {
                                "type": "integer",
                                "description": "Campaign ID"
                            },
                            "metric": {
                                "type": "string",
                                "description": "Metric name (roas, ctr, cvr, cost, revenue)",
                                "enum": ["roas", "ctr", "cvr", "cost", "revenue", "impressions", "clicks", "conversions"]
                            },
                            "time_range": {
                                "type": "string",
                                "description": "Time range (e.g., '7d', '30d', '1h')",
                                "default": "7d"
                            }
                        },
                        "required": ["campaign_id", "metric"]
                    }
                ),
                Tool(
                    name="get_optimizer_state",
                    description="Get current optimizer state (alpha/beta, risk scores, etc.)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "campaign_id": {
                                "type": "integer",
                                "description": "Campaign ID"
                            }
                        },
                        "required": ["campaign_id"]
                    }
                ),
                # Write operations
                Tool(
                    name="suggest_allocation_override",
                    description="Analyst suggests a manual allocation override",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "campaign_id": {"type": "integer"},
                            "arm_id": {"type": "integer"},
                            "new_allocation": {"type": "number", "description": "New allocation (0.0-1.0)"},
                            "justification": {"type": "string", "description": "Reason for override"}
                        },
                        "required": ["campaign_id", "arm_id", "new_allocation", "justification"]
                    }
                ),
                Tool(
                    name="pause_campaign",
                    description="Pause campaign optimization",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "campaign_id": {"type": "integer"},
                            "reason": {"type": "string"}
                        },
                        "required": ["campaign_id", "reason"]
                    }
                ),
                Tool(
                    name="resume_campaign",
                    description="Resume campaign optimization",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "campaign_id": {"type": "integer"},
                            "reason": {"type": "string"}
                        },
                        "required": ["campaign_id", "reason"]
                    }
                ),
                Tool(
                    name="update_campaign_budget",
                    description="Update campaign budget",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "campaign_id": {"type": "integer"},
                            "new_budget": {"type": "number"},
                            "reason": {"type": "string"}
                        },
                        "required": ["campaign_id", "new_budget", "reason"]
                    }
                ),
                Tool(
                    name="provide_feedback",
                    description="Provide analyst feedback/domain knowledge",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "campaign_id": {"type": "integer"},
                            "feedback_type": {"type": "string", "enum": ["domain_knowledge", "correction", "preference", "insight"]},
                            "message": {"type": "string"},
                            "context": {"type": "object"}
                        },
                        "required": ["campaign_id", "feedback_type", "message"]
                    }
                ),
                # Explanation operations
                Tool(
                    name="explain_allocation_change",
                    description="Get human-readable explanation of why allocation changed",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "change_id": {"type": "integer", "description": "AllocationChange ID"}
                        },
                        "required": ["change_id"]
                    }
                ),
                Tool(
                    name="explain_performance",
                    description="Explain performance metrics and trends with LLM-powered natural language",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "campaign_id": {"type": "integer"},
                            "arm_id": {"type": "integer", "description": "Optional arm ID"},
                            "time_range": {"type": "string", "default": "7d"}
                        },
                        "required": ["campaign_id"]
                    }
                ),
                Tool(
                    name="explain_anomaly",
                    description="Explain an anomaly with LLM-powered natural language",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "campaign_id": {"type": "integer"},
                            "arm_id": {"type": "integer"},
                            "anomaly_type": {"type": "string"},
                            "anomaly_data": {"type": "object"}
                        },
                        "required": ["campaign_id", "arm_id", "anomaly_type", "anomaly_data"]
                    }
                ),
                Tool(
                    name="explain_recommendation",
                    description="Explain a recommendation with LLM-powered natural language",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "recommendation_id": {"type": "integer"}
                        },
                        "required": ["recommendation_id"]
                    }
                ),
                # Research operations
                Tool(
                    name="web_search",
                    description="Search the web for information",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "max_results": {"type": "integer", "default": 5}
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="analyze_trend",
                    description="Analyze trends for a topic using Google Trends",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "keyword": {"type": "string"},
                            "timeframe": {"type": "string", "default": "today 7-d"},
                            "geo": {"type": "string", "default": "US"}
                        },
                        "required": ["keyword"]
                    }
                ),
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            # Read operations
            if name == "get_campaign_status":
                return await self._get_campaign_status(**arguments)
            elif name == "get_allocation_history":
                return await self._get_allocation_history(**arguments)
            elif name == "get_arm_performance":
                return await self._get_arm_performance(**arguments)
            elif name == "query_metrics":
                return await self._query_metrics(**arguments)
            elif name == "get_optimizer_state":
                return await self._get_optimizer_state(**arguments)
            # Write operations
            elif name == "suggest_allocation_override":
                return await self.operations.suggest_allocation_override(**arguments)
            elif name == "pause_campaign":
                return await self.operations.pause_campaign(**arguments)
            elif name == "resume_campaign":
                return await self.operations.resume_campaign(**arguments)
            elif name == "update_campaign_budget":
                return await self.operations.update_campaign_budget(**arguments)
            elif name == "provide_feedback":
                return await self.operations.provide_feedback(**arguments)
            # Explanation operations (LLM-powered)
            elif name == "explain_allocation_change":
                return await self.operations.explain_allocation_change(**arguments)
            elif name == "explain_performance":
                return await self.operations.explain_performance(**arguments)
            elif name == "explain_anomaly":
                return await self.operations.explain_anomaly(**arguments)
            elif name == "explain_recommendation":
                return await self.operations.explain_recommendation(**arguments)
            # Research operations
            elif name == "web_search":
                return await self.operations.web_search(**arguments)
            elif name == "analyze_trend":
                return await self.operations.analyze_trend(**arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")
    
    def _register_write_tools(self):
        """Register write operation tools."""
        # Add write tools to list_tools
        # Implementation in call_tool handler
        pass
    
    def _register_explanation_tools(self):
        """Register explanation operation tools."""
        # Add explanation tools to list_tools
        # Implementation in call_tool handler
        pass
    
    def _register_research_tools(self):
        """Register research operation tools."""
        # Add research tools to list_tools
        # Implementation in call_tool handler
        pass
    
    # Read operation implementations
    async def _get_campaign_status(self, campaign_id: int) -> List[TextContent]:
        """Get campaign status."""
        try:
            status = self.optimization_service.get_campaign_status(campaign_id)
            if not status:
                return [TextContent(
                    type="text",
                    text=f"Campaign {campaign_id} not found"
                )]
            
            return [TextContent(
                type="text",
                text=json.dumps(status, indent=2, default=str)
            )]
        except Exception as e:
            logger.error(f"Error getting campaign status: {str(e)}")
            return [TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )]
    
    async def _get_allocation_history(self, campaign_id: int, days: int = 7) -> List[TextContent]:
        """Get allocation history."""
        try:
            changes = self.change_tracker.get_allocation_history(campaign_id, days=days)
            
            history = []
            for change in changes:
                history.append({
                    "id": change.id,
                    "arm_id": change.arm_id,
                    "timestamp": change.timestamp.isoformat(),
                    "old_allocation": change.old_allocation,
                    "new_allocation": change.new_allocation,
                    "change_percent": change.change_percent,
                    "change_type": change.change_type,
                    "change_reason": change.change_reason,
                    "factors": change.factors,
                    "mmm_factors": change.mmm_factors
                })
            
            return [TextContent(
                type="text",
                text=json.dumps({"campaign_id": campaign_id, "days": days, "changes": history}, indent=2, default=str)
            )]
        except Exception as e:
            logger.error(f"Error getting allocation history: {str(e)}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _get_arm_performance(self, arm_id: int, start_date: str, end_date: str) -> List[TextContent]:
        """Get arm performance."""
        try:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            
            metrics = get_metrics_by_arm(arm_id, start_date=start, end_date=end)
            
            # Aggregate metrics
            total_impressions = sum(m.impressions for m in metrics)
            total_clicks = sum(m.clicks for m in metrics)
            total_conversions = sum(m.conversions for m in metrics)
            total_cost = sum(m.cost for m in metrics)
            total_revenue = sum(m.revenue for m in metrics)
            
            performance = {
                "arm_id": arm_id,
                "start_date": start_date,
                "end_date": end_date,
                "impressions": total_impressions,
                "clicks": total_clicks,
                "conversions": total_conversions,
                "cost": total_cost,
                "revenue": total_revenue,
                "roas": total_revenue / total_cost if total_cost > 0 else 0,
                "ctr": total_clicks / total_impressions if total_impressions > 0 else 0,
                "cvr": total_conversions / total_clicks if total_clicks > 0 else 0,
                "data_points": len(metrics)
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(performance, indent=2, default=str)
            )]
        except Exception as e:
            logger.error(f"Error getting arm performance: {str(e)}")
            return [TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )]
    
    async def _query_metrics(self, campaign_id: int, metric: str, time_range: str = "7d") -> List[TextContent]:
        """Query metrics."""
        # Parse time range
        days = self._parse_time_range(time_range)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get all arms for campaign
        arms = get_arms_by_campaign(campaign_id)
        if not arms:
            return [TextContent(
                type="text",
                text=f"No arms found for campaign {campaign_id}"
            )]
        
        # Aggregate metrics across all arms
        total_value = 0.0
        data_points = 0
        
        for arm in arms:
            metrics = get_metrics_by_arm(arm.id, start_date=start_date, end_date=end_date)
            for m in metrics:
                if metric == "roas" and m.cost > 0:
                    total_value += m.roas
                    data_points += 1
                elif metric == "ctr" and m.impressions > 0:
                    total_value += m.ctr
                    data_points += 1
                elif metric == "cvr" and m.clicks > 0:
                    total_value += m.cvr
                    data_points += 1
                elif metric == "cost":
                    total_value += m.cost
                    data_points += 1
                elif metric == "revenue":
                    total_value += m.revenue
                    data_points += 1
                elif metric == "impressions":
                    total_value += m.impressions
                    data_points += 1
                elif metric == "clicks":
                    total_value += m.clicks
                    data_points += 1
                elif metric == "conversions":
                    total_value += m.conversions
                    data_points += 1
        
        avg_value = total_value / data_points if data_points > 0 else 0
        
        result = {
            "campaign_id": campaign_id,
            "metric": metric,
            "time_range": time_range,
            "average_value": avg_value,
            "total_value": total_value,
            "data_points": data_points
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2, default=str)
        )]
    
    async def _get_optimizer_state(self, campaign_id: int) -> List[TextContent]:
        """Get optimizer state."""
        try:
            arms = get_arms_by_campaign(campaign_id)
            state = {}
            
            for arm in arms:
                agent_state = get_agent_state(campaign_id, arm.id)
                if agent_state:
                    state[str(arm)] = {
                        "alpha": agent_state.alpha,
                        "beta": agent_state.beta,
                        "spending": agent_state.spending,
                        "impressions": agent_state.impressions,
                        "rewards": agent_state.rewards,
                        "reward_variance": agent_state.reward_variance,
                        "trials": agent_state.trials,
                        "risk_score": agent_state.risk_score
                    }
            
            return [TextContent(
                type="text",
                text=json.dumps(state, indent=2, default=str)
            )]
        except Exception as e:
            logger.error(f"Error getting optimizer state: {str(e)}")
            return [TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )]
    
    def _parse_time_range(self, time_range: str) -> int:
        """Parse time range string to days."""
        if time_range.endswith('d'):
            return int(time_range[:-1])
        elif time_range.endswith('h'):
            return int(time_range[:-1]) / 24
        elif time_range.endswith('w'):
            return int(time_range[:-1]) * 7
        else:
            return 7  # default
    
    async def run(self):
        """Run the MCP server."""
        if not self.server:
            raise RuntimeError("MCP SDK not available")
        
        # Run server (implementation depends on MCP SDK)
        # This is a placeholder - actual implementation will depend on MCP SDK API
        logger.info("MCP server running")


# Global server instance
_server_instance: Optional[OptimizerMCPServer] = None


def get_mcp_server(config_manager: Optional[ConfigManager] = None) -> OptimizerMCPServer:
    """Get or create global MCP server instance."""
    global _server_instance
    if _server_instance is None:
        _server_instance = OptimizerMCPServer(config_manager)
    return _server_instance
