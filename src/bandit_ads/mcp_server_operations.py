"""
MCP Server Operation Implementations

Write, explanation, and research operation implementations for MCP server.
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from src.bandit_ads.utils import get_logger
from src.bandit_ads.change_tracker import get_change_tracker
from src.bandit_ads.recommendations import get_recommendation_manager
from src.bandit_ads.research_tools import get_research_tools
from src.bandit_ads.optimization_service import get_optimization_service
from src.bandit_ads.explanation_generator import get_explanation_generator
from src.bandit_ads.db_helpers import get_arms_by_campaign, get_metrics_by_arm
from src.bandit_ads.database import get_db_manager

logger = get_logger('mcp_operations')


class MCPOperations:
    """MCP server operation implementations."""
    
    def __init__(self):
        """Initialize operations."""
        self.change_tracker = get_change_tracker()
        self.recommendation_manager = get_recommendation_manager()
        self.research_tools = get_research_tools()
        self.optimization_service = get_optimization_service()
        self.explanation_generator = get_explanation_generator()
        self.db_manager = get_db_manager()
    
    # Write operations
    async def suggest_allocation_override(
        self,
        campaign_id: int,
        arm_id: int,
        new_allocation: float,
        justification: str,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Suggest allocation override."""
        try:
            # Get current allocation
            campaign_status = self.optimization_service.get_campaign_status(campaign_id)
            if not campaign_status:
                return [{"type": "text", "text": f"Campaign {campaign_id} not found"}]
            
            # Get current allocation for arm (would need to query optimizer state)
            # For now, create recommendation
            recommendation = self.recommendation_manager.create_recommendation(
                campaign_id=campaign_id,
                recommendation_type="allocation_change",
                title=f"Allocation Override: Arm {arm_id}",
                description=justification,
                details={
                    "arm_id": arm_id,
                    "new_allocation": new_allocation,
                    "justification": justification
                },
                user_id=user_id,
                auto_apply=False
            )
            
            if recommendation:
                return [{
                    "type": "text",
                    "text": json.dumps({
                        "success": True,
                        "recommendation_id": recommendation.id,
                        "message": f"Allocation override recommendation created. Review and approve to apply."
                    }, indent=2)
                }]
            else:
                return [{"type": "text", "text": "Failed to create recommendation"}]
        except Exception as e:
            logger.error(f"Error suggesting allocation override: {str(e)}")
            return [{"type": "text", "text": f"Error: {str(e)}"}]
    
    async def pause_campaign(
        self,
        campaign_id: int,
        reason: str,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Pause campaign."""
        try:
            self.optimization_service.pause_campaign(campaign_id)
            
            # Log decision
            self.change_tracker.log_decision(
                campaign_id=campaign_id,
                decision_type="pause",
                decision_data={"reason": reason},
                reasoning=reason,
                initiated_by=user_id
            )
            
            return [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "message": f"Campaign {campaign_id} paused",
                    "reason": reason
                }, indent=2)
            }]
        except Exception as e:
            logger.error(f"Error pausing campaign: {str(e)}")
            return [{"type": "text", "text": f"Error: {str(e)}"}]
    
    async def resume_campaign(
        self,
        campaign_id: int,
        reason: str,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Resume campaign."""
        try:
            self.optimization_service.resume_campaign(campaign_id)
            
            # Log decision
            self.change_tracker.log_decision(
                campaign_id=campaign_id,
                decision_type="resume",
                decision_data={"reason": reason},
                reasoning=reason,
                initiated_by=user_id
            )
            
            return [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "message": f"Campaign {campaign_id} resumed",
                    "reason": reason
                }, indent=2)
            }]
        except Exception as e:
            logger.error(f"Error resuming campaign: {str(e)}")
            return [{"type": "text", "text": f"Error: {str(e)}"}]
    
    async def update_campaign_budget(
        self,
        campaign_id: int,
        new_budget: float,
        reason: str,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Update campaign budget."""
        try:
            # Get current budget
            campaign_status = self.optimization_service.get_campaign_status(campaign_id)
            if not campaign_status:
                return [{"type": "text", "text": f"Campaign {campaign_id} not found"}]
            
            current_budget = campaign_status.get('performance', {}).get('total_budget', 0)
            
            # Create recommendation
            recommendation = self.recommendation_manager.create_recommendation(
                campaign_id=campaign_id,
                recommendation_type="budget_adjustment",
                title=f"Budget Adjustment: ${new_budget:,.2f}",
                description=reason,
                details={
                    "current_budget": current_budget,
                    "new_budget": new_budget,
                    "reason": reason
                },
                user_id=user_id
            )
            
            if recommendation:
                return [{
                    "type": "text",
                    "text": json.dumps({
                        "success": True,
                        "recommendation_id": recommendation.id,
                        "message": "Budget adjustment recommendation created. Review and approve to apply."
                    }, indent=2)
                }]
            else:
                return [{"type": "text", "text": "Failed to create recommendation"}]
        except Exception as e:
            logger.error(f"Error updating campaign budget: {str(e)}")
            return [{"type": "text", "text": f"Error: {str(e)}"}]
    
    async def provide_feedback(
        self,
        campaign_id: int,
        feedback_type: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Provide analyst feedback."""
        try:
            # Store feedback (could be in database or recommendation system)
            # For now, create a recommendation with feedback type
            recommendation = self.recommendation_manager.create_recommendation(
                campaign_id=campaign_id,
                recommendation_type="feedback",
                title=f"Analyst Feedback: {feedback_type}",
                description=message,
                details={
                    "feedback_type": feedback_type,
                    "message": message,
                    "context": context or {}
                },
                user_id=user_id
            )
            
            if recommendation:
                return [{
                    "type": "text",
                    "text": json.dumps({
                        "success": True,
                        "message": "Feedback recorded and will be considered in future optimizations"
                    }, indent=2)
                }]
            else:
                return [{"type": "text", "text": "Failed to record feedback"}]
        except Exception as e:
            logger.error(f"Error providing feedback: {str(e)}")
            return [{"type": "text", "text": f"Error: {str(e)}"}]
    
    # Explanation operations (LLM-powered)
    async def explain_allocation_change(self, change_id: int) -> List[Dict[str, Any]]:
        """
        Explain allocation change using LLM-powered natural language generation.
        
        Args:
            change_id: AllocationChange ID
        
        Returns:
            Natural language explanation
        """
        try:
            # Use the explanation generator for LLM-powered explanations
            explanation = await self.explanation_generator.explain_allocation_change(
                change_id=change_id,
                include_historical_context=True
            )
            
            return [{"type": "text", "text": explanation}]
        except Exception as e:
            logger.error(f"Error explaining allocation change: {str(e)}")
            return [{"type": "text", "text": f"Error: {str(e)}"}]
    
    async def explain_performance(
        self,
        campaign_id: int,
        arm_id: Optional[int] = None,
        time_range: str = "7d"
    ) -> List[Dict[str, Any]]:
        """
        Explain performance metrics using LLM-powered natural language generation.
        
        Args:
            campaign_id: Campaign ID
            arm_id: Optional arm ID
            time_range: Time range for analysis
        
        Returns:
            Natural language explanation
        """
        try:
            # Use the explanation generator for LLM-powered explanations
            explanation = await self.explanation_generator.explain_performance(
                campaign_id=campaign_id,
                arm_id=arm_id,
                time_range=time_range,
                include_trends=True
            )
            
            return [{"type": "text", "text": explanation}]
        except Exception as e:
            logger.error(f"Error explaining performance: {str(e)}")
            return [{"type": "text", "text": f"Error: {str(e)}"}]
    
    async def explain_anomaly(
        self,
        campaign_id: int,
        arm_id: int,
        anomaly_type: str,
        anomaly_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Explain an anomaly using LLM-powered natural language generation.
        
        Args:
            campaign_id: Campaign ID
            arm_id: Arm ID
            anomaly_type: Type of anomaly
            anomaly_data: Anomaly details
        
        Returns:
            Natural language explanation
        """
        try:
            explanation = await self.explanation_generator.explain_anomaly(
                campaign_id=campaign_id,
                arm_id=arm_id,
                anomaly_type=anomaly_type,
                anomaly_data=anomaly_data
            )
            
            return [{"type": "text", "text": explanation}]
        except Exception as e:
            logger.error(f"Error explaining anomaly: {str(e)}")
            return [{"type": "text", "text": f"Error: {str(e)}"}]
    
    async def explain_recommendation(self, recommendation_id: int) -> List[Dict[str, Any]]:
        """
        Explain a recommendation using LLM-powered natural language generation.
        
        Args:
            recommendation_id: Recommendation ID
        
        Returns:
            Natural language explanation
        """
        try:
            explanation = await self.explanation_generator.explain_recommendation(
                recommendation_id=recommendation_id
            )
            
            return [{"type": "text", "text": explanation}]
        except Exception as e:
            logger.error(f"Error explaining recommendation: {str(e)}")
            return [{"type": "text", "text": f"Error: {str(e)}"}]
    
    def _parse_time_range(self, time_range: str) -> int:
        """Parse time range string to days."""
        if time_range.endswith('d'):
            return int(time_range[:-1])
        elif time_range.endswith('h'):
            return int(time_range[:-1]) / 24
        elif time_range.endswith('w'):
            return int(time_range[:-1]) * 7
        else:
            return 7
    
    # Research operations
    async def web_search(
        self,
        query: str,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Web search using Tavily."""
        try:
            results = self.research_tools.tavily.search(query, max_results=max_results)
            
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", "")[:500],  # Truncate
                    "score": result.get("score", 0.0)
                })
            
            return [{
                "type": "text",
                "text": json.dumps({
                    "query": query,
                    "results": formatted_results
                }, indent=2)
            }]
        except Exception as e:
            logger.error(f"Error in web search: {str(e)}")
            return [{"type": "text", "text": f"Error: {str(e)}"}]
    
    async def analyze_trend(
        self,
        keyword: str,
        timeframe: str = "today 7-d",
        geo: str = "US"
    ) -> List[Dict[str, Any]]:
        """Analyze trend using Google Trends."""
        try:
            trend_data = self.research_tools.google_trends.get_trend(keyword, timeframe, geo)
            
            return [{
                "type": "text",
                "text": json.dumps(trend_data, indent=2, default=str)
            }]
        except Exception as e:
            logger.error(f"Error analyzing trend: {str(e)}")
            return [{"type": "text", "text": f"Error: {str(e)}"}]
