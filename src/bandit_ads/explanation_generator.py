"""
Enhanced Explanation Generator

Uses LLM (Claude) to transform raw optimizer data into natural language explanations.
Provides context-aware, conversational explanations of decisions and performance.
"""

import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from src.bandit_ads.vector_store import get_vector_store
from src.bandit_ads.change_tracker import get_change_tracker
from src.bandit_ads.db_helpers import get_metrics_by_arm, get_arms_by_campaign
from src.bandit_ads.database import get_db_manager
from src.bandit_ads.utils import get_logger, ConfigManager

logger = get_logger('explanation_generator')


class ExplanationGenerator:
    """
    Generates natural language explanations using LLM.
    
    Transforms raw optimizer data into conversational, insightful explanations
    that help analysts understand WHY decisions were made.
    """
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize explanation generator."""
        self.config_manager = config_manager or ConfigManager()
        
        # Vector store is optional - may not be installed
        try:
            self.vector_store = get_vector_store()
        except ImportError:
            logger.warning("Vector store not available - RAG context will be disabled")
            self.vector_store = None
        
        self.change_tracker = get_change_tracker()
        self.db_manager = get_db_manager()
        
        # Initialize Claude client
        self.claude_client = None
        self._init_claude_client()
        
        logger.info("Explanation generator initialized")
    
    def _init_claude_client(self):
        """Initialize Claude API client."""
        try:
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY") or self.config_manager.get("interpretability.llm.claude_api_key")
            if api_key:
                self.claude_client = anthropic.Anthropic(api_key=api_key)
                logger.info("Claude client initialized for explanation generation")
            else:
                logger.warning("ANTHROPIC_API_KEY not set - explanations will be template-based")
        except ImportError:
            logger.warning("anthropic library not installed - explanations will be template-based")
        except Exception as e:
            logger.warning(f"Failed to initialize Claude client: {str(e)}")
    
    async def explain_allocation_change(
        self,
        change_id: int,
        include_historical_context: bool = True
    ) -> str:
        """
        Generate natural language explanation for an allocation change.
        
        Args:
            change_id: AllocationChange ID
            include_historical_context: Whether to include RAG context
        
        Returns:
            Natural language explanation
        """
        from src.bandit_ads.change_tracker import AllocationChange
        
        # Get change data
        with self.db_manager.get_session() as session:
            change = session.query(AllocationChange).filter(
                AllocationChange.id == change_id
            ).first()
            
            if not change:
                return f"Allocation change {change_id} not found."
            
            # Extract data
            change_data = {
                "arm_id": change.arm_id,
                "old_allocation": change.old_allocation,
                "new_allocation": change.new_allocation,
                "change_percent": change.change_percent,
                "change_type": change.change_type,
                "change_reason": change.change_reason,
                "factors": change.factors or {},
                "mmm_factors": change.mmm_factors or {},
                "optimizer_state": change.optimizer_state or {},
                "performance_before": change.performance_before or {},
                "performance_after": change.performance_after or {},
                "timestamp": change.timestamp.isoformat()
            }
        
        # Get historical context from RAG
        historical_context = None
        if include_historical_context and self.vector_store:
            try:
                similar_decisions = self.vector_store.search_similar_decisions(
                    f"allocation change {change_data['factors']}",
                    campaign_id=change.campaign_id,
                    top_k=3
                )
                if similar_decisions:
                    historical_context = self._format_historical_context(similar_decisions)
            except Exception as e:
                logger.debug(f"Could not retrieve RAG context: {e}")
        
        # Generate explanation using LLM
        if self.claude_client:
            return await self._generate_llm_explanation(
                explanation_type="allocation_change",
                data=change_data,
                historical_context=historical_context
            )
        else:
            return self._generate_template_explanation(
                explanation_type="allocation_change",
                data=change_data
            )
    
    async def explain_performance(
        self,
        campaign_id: int,
        arm_id: Optional[int] = None,
        time_range: str = "7d",
        include_trends: bool = True
    ) -> str:
        """
        Generate natural language explanation of performance.
        
        Args:
            campaign_id: Campaign ID
            arm_id: Optional arm ID (if None, explains campaign-level)
            time_range: Time range for analysis
            include_trends: Whether to include trend analysis
        
        Returns:
            Natural language explanation
        """
        # Parse time range
        days = self._parse_time_range(time_range)
        start_date = datetime.utcnow() - timedelta(days=days)
        end_date = datetime.utcnow()
        
        # Get performance data
        if arm_id:
            arms = [self._get_arm_by_id(arm_id)]
        else:
            arms = get_arms_by_campaign(campaign_id)
        
        performance_data = []
        for arm in arms:
            if arm is None:
                continue
            metrics = get_metrics_by_arm(arm.id, start_date=start_date, end_date=end_date)
            
            if not metrics:
                continue
            
            # Calculate aggregates
            total_cost = sum(m.cost for m in metrics)
            total_revenue = sum(m.revenue for m in metrics)
            total_impressions = sum(m.impressions for m in metrics)
            total_clicks = sum(m.clicks for m in metrics)
            total_conversions = sum(m.conversions for m in metrics)
            
            # Calculate trends (compare first half to second half)
            if len(metrics) >= 2:
                mid = len(metrics) // 2
                first_half_roas = sum(m.roas for m in metrics[:mid]) / mid if mid > 0 else 0
                second_half_roas = sum(m.roas for m in metrics[mid:]) / (len(metrics) - mid) if len(metrics) > mid else 0
                roas_trend = "increasing" if second_half_roas > first_half_roas else "decreasing"
            else:
                roas_trend = "stable"
            
            performance_data.append({
                "arm_id": arm.id,
                "arm_name": str(arm),
                "platform": arm.platform,
                "channel": arm.channel,
                "metrics": {
                    "roas": total_revenue / total_cost if total_cost > 0 else 0,
                    "ctr": total_clicks / total_impressions if total_impressions > 0 else 0,
                    "cvr": total_conversions / total_clicks if total_clicks > 0 else 0,
                    "cost": total_cost,
                    "revenue": total_revenue,
                    "impressions": total_impressions,
                    "clicks": total_clicks,
                    "conversions": total_conversions
                },
                "trend": roas_trend,
                "data_points": len(metrics)
            })
        
        # Get recent allocation changes for context
        recent_changes = self.change_tracker.get_allocation_history(campaign_id, days=days)
        changes_summary = [
            {
                "arm_id": c.arm_id,
                "change_percent": c.change_percent,
                "reason": c.change_reason
            }
            for c in recent_changes[:5]  # Top 5 recent changes
        ]
        
        # Generate explanation using LLM
        data = {
            "campaign_id": campaign_id,
            "time_range": time_range,
            "performance": performance_data,
            "recent_changes": changes_summary
        }
        
        if self.claude_client:
            return await self._generate_llm_explanation(
                explanation_type="performance",
                data=data,
                historical_context=None
            )
        else:
            return self._generate_template_explanation(
                explanation_type="performance",
                data=data
            )
    
    async def explain_anomaly(
        self,
        campaign_id: int,
        arm_id: int,
        anomaly_type: str,
        anomaly_data: Dict[str, Any]
    ) -> str:
        """
        Generate natural language explanation of an anomaly.
        
        Args:
            campaign_id: Campaign ID
            arm_id: Arm ID
            anomaly_type: Type of anomaly (roas_anomaly, ctr_anomaly, etc.)
            anomaly_data: Anomaly details
        
        Returns:
            Natural language explanation
        """
        # Get historical context
        similar_anomalies = []
        if self.vector_store:
            try:
                similar_anomalies = self.vector_store.search_similar_decisions(
                    f"anomaly {anomaly_type} {anomaly_data}",
                    campaign_id=campaign_id,
                    top_k=3
                )
            except Exception as e:
                logger.debug(f"Could not retrieve RAG context: {e}")
        
        data = {
            "campaign_id": campaign_id,
            "arm_id": arm_id,
            "anomaly_type": anomaly_type,
            "anomaly_data": anomaly_data
        }
        
        historical_context = None
        if similar_anomalies:
            historical_context = self._format_historical_context(similar_anomalies)
        
        if self.claude_client:
            return await self._generate_llm_explanation(
                explanation_type="anomaly",
                data=data,
                historical_context=historical_context
            )
        else:
            return self._generate_template_explanation(
                explanation_type="anomaly",
                data=data
            )
    
    async def explain_recommendation(
        self,
        recommendation_id: int
    ) -> str:
        """
        Generate natural language explanation for a recommendation.
        
        Args:
            recommendation_id: Recommendation ID
        
        Returns:
            Natural language explanation
        """
        from src.bandit_ads.recommendations import Recommendation
        
        with self.db_manager.get_session() as session:
            rec = session.query(Recommendation).filter(
                Recommendation.id == recommendation_id
            ).first()
            
            if not rec:
                return f"Recommendation {recommendation_id} not found."
            
            data = {
                "type": rec.recommendation_type,
                "title": rec.title,
                "description": rec.description,
                "details": json.loads(rec.details) if rec.details else {},
                "status": rec.status
            }
        
        if self.claude_client:
            return await self._generate_llm_explanation(
                explanation_type="recommendation",
                data=data,
                historical_context=None
            )
        else:
            return self._generate_template_explanation(
                explanation_type="recommendation",
                data=data
            )
    
    async def _generate_llm_explanation(
        self,
        explanation_type: str,
        data: Dict[str, Any],
        historical_context: Optional[str] = None
    ) -> str:
        """Generate explanation using Claude LLM."""
        
        # Build prompt based on explanation type
        system_prompt = self._build_system_prompt(explanation_type)
        user_prompt = self._build_user_prompt(explanation_type, data, historical_context)
        
        try:
            response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            
            explanation = response.content[0].text if response.content else ""
            return explanation
            
        except Exception as e:
            logger.error(f"Error generating LLM explanation: {str(e)}")
            # Fall back to template
            return self._generate_template_explanation(explanation_type, data)
    
    def _build_system_prompt(self, explanation_type: str) -> str:
        """Build system prompt for explanation generation."""
        base_prompt = """You are an expert advertising analyst assistant that explains budget optimizer decisions in clear, conversational language.

Your explanations should:
1. Be conversational and easy to understand
2. Explain WHY decisions were made, not just WHAT happened
3. Reference specific factors and their impact
4. Connect to business context (seasonality, competition, etc.)
5. Be concise but thorough
6. Use bullet points for clarity when listing multiple factors
7. Include actionable insights when relevant

Do NOT:
- Use overly technical jargon
- Simply repeat raw numbers without context
- Be vague or generic
- Provide recommendations unless asked"""
        
        type_specific = {
            "allocation_change": "\n\nYou are explaining WHY a budget allocation changed. Focus on the factors that drove the decision.",
            "performance": "\n\nYou are explaining performance metrics. Focus on trends, comparisons, and what's working vs what's not.",
            "anomaly": "\n\nYou are explaining an anomaly or unexpected behavior. Focus on possible causes and whether it's concerning.",
            "recommendation": "\n\nYou are explaining a recommendation from the optimizer. Focus on why it's being suggested and expected impact."
        }
        
        return base_prompt + type_specific.get(explanation_type, "")
    
    def _build_user_prompt(
        self,
        explanation_type: str,
        data: Dict[str, Any],
        historical_context: Optional[str]
    ) -> str:
        """Build user prompt for explanation generation."""
        
        if explanation_type == "allocation_change":
            prompt = f"""Explain this budget allocation change:

**Change Details:**
- Previous allocation: {data['old_allocation']:.1%}
- New allocation: {data['new_allocation']:.1%}
- Change: {data['change_percent']:+.1f}%
- Change type: {data['change_type']}
- Timestamp: {data['timestamp']}

**Stored Reason:** {data.get('change_reason', 'Not specified')}

**Contributing Factors:**
{json.dumps(data.get('factors', {}), indent=2)}

**MMM (Marketing Mix Model) Factors:**
{json.dumps(data.get('mmm_factors', {}), indent=2)}

**Optimizer State at Time of Change:**
{json.dumps(data.get('optimizer_state', {}), indent=2)}

**Performance Before:** {json.dumps(data.get('performance_before', {}), indent=2)}
**Performance After:** {json.dumps(data.get('performance_after', {}), indent=2)}
"""
        
        elif explanation_type == "performance":
            perf_summary = "\n".join([
                f"- {p['arm_name']}: ROAS={p['metrics']['roas']:.2f}, CTR={p['metrics']['ctr']:.2%}, Trend={p['trend']}"
                for p in data.get('performance', [])
            ])
            
            changes_summary = "\n".join([
                f"- Arm {c['arm_id']}: {c['change_percent']:+.1f}% ({c['reason'] or 'no reason recorded'})"
                for c in data.get('recent_changes', [])
            ])
            
            prompt = f"""Explain the performance for Campaign {data['campaign_id']} over the last {data['time_range']}:

**Performance by Arm:**
{perf_summary}

**Recent Allocation Changes:**
{changes_summary if changes_summary else 'No recent changes'}

Provide insights on:
1. Which arms are performing well and why
2. Which arms need attention
3. How the trends are looking
4. Any notable patterns
"""
        
        elif explanation_type == "anomaly":
            prompt = f"""Explain this anomaly detected in Campaign {data['campaign_id']}, Arm {data['arm_id']}:

**Anomaly Type:** {data['anomaly_type']}

**Anomaly Details:**
{json.dumps(data.get('anomaly_data', {}), indent=2)}

Explain:
1. What this anomaly means
2. Possible causes
3. Whether it's concerning
4. Suggested actions (if any)
"""
        
        elif explanation_type == "recommendation":
            prompt = f"""Explain this optimizer recommendation:

**Type:** {data['type']}
**Title:** {data['title']}
**Description:** {data['description']}
**Status:** {data['status']}

**Details:**
{json.dumps(data.get('details', {}), indent=2)}

Explain:
1. Why the optimizer is making this recommendation
2. Expected impact
3. Any considerations before approving
"""
        
        else:
            prompt = f"""Explain the following data:\n{json.dumps(data, indent=2)}"""
        
        # Add historical context if available
        if historical_context:
            prompt += f"""

**Historical Context (similar past situations):**
{historical_context}

Use this historical context to provide additional insights about patterns and what happened in similar situations.
"""
        
        return prompt
    
    def _generate_template_explanation(
        self,
        explanation_type: str,
        data: Dict[str, Any]
    ) -> str:
        """Generate template-based explanation (fallback when LLM unavailable)."""
        
        if explanation_type == "allocation_change":
            parts = [
                f"**Allocation Change Summary**\n",
                f"The budget allocation changed from {data['old_allocation']:.1%} to {data['new_allocation']:.1%} "
                f"({data['change_percent']:+.1f}%).\n"
            ]
            
            if data.get('change_reason'):
                parts.append(f"\n**Reason:** {data['change_reason']}\n")
            
            if data.get('factors'):
                parts.append("\n**Contributing Factors:**")
                for factor, value in data['factors'].items():
                    parts.append(f"\n- {factor}: {value}")
            
            if data.get('mmm_factors'):
                parts.append("\n\n**MMM Factors:**")
                for factor, value in data['mmm_factors'].items():
                    parts.append(f"\n- {factor}: {value}")
            
            return "".join(parts)
        
        elif explanation_type == "performance":
            parts = [f"**Performance Summary for Campaign {data['campaign_id']}**\n"]
            
            for perf in data.get('performance', []):
                parts.append(f"\n**{perf['arm_name']}**")
                parts.append(f"\n- ROAS: {perf['metrics']['roas']:.2f}")
                parts.append(f"\n- CTR: {perf['metrics']['ctr']:.2%}")
                parts.append(f"\n- Trend: {perf['trend']}")
            
            return "".join(parts)
        
        elif explanation_type == "anomaly":
            return f"""**Anomaly Detected**

Type: {data['anomaly_type']}
Arm: {data['arm_id']}

Details: {json.dumps(data.get('anomaly_data', {}), indent=2)}

This anomaly requires investigation to determine the cause."""
        
        elif explanation_type == "recommendation":
            return f"""**Recommendation: {data['title']}**

{data['description']}

Details: {json.dumps(data.get('details', {}), indent=2)}

Status: {data['status']}"""
        
        else:
            return f"Data: {json.dumps(data, indent=2)}"
    
    def _format_historical_context(self, similar_decisions: List[Dict[str, Any]]) -> str:
        """Format historical context from RAG results."""
        parts = []
        for i, decision in enumerate(similar_decisions, 1):
            text = decision.get('text', '')[:300]  # Truncate
            parts.append(f"{i}. {text}...")
        return "\n".join(parts)
    
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
    
    def _get_arm_by_id(self, arm_id: int):
        """Get arm by ID."""
        from src.bandit_ads.database import Arm
        with self.db_manager.get_session() as session:
            return session.query(Arm).filter(Arm.id == arm_id).first()


# Global explanation generator instance
_explanation_generator_instance: Optional[ExplanationGenerator] = None


def get_explanation_generator(config_manager: Optional[ConfigManager] = None) -> ExplanationGenerator:
    """Get or create global explanation generator instance."""
    global _explanation_generator_instance
    if _explanation_generator_instance is None:
        _explanation_generator_instance = ExplanationGenerator(config_manager)
    return _explanation_generator_instance
