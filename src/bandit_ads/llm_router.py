"""
LLM Router for Query-Based Model Selection

Routes queries to appropriate LLM based on query type:
- Claude 4.5 Sonnet: Explanations, analysis, research
- GPT-4 Turbo: Optimization logic, structured planning
"""

from typing import Dict, Optional, Any
from enum import Enum
import re

from src.bandit_ads.utils import get_logger

logger = get_logger('llm_router')


class QueryType(Enum):
    """Query type classification."""
    EXPLANATION = "explanation"  # Use Claude
    OPTIMIZATION = "optimization"  # Use GPT-4 Turbo
    ANALYSIS = "analysis"  # Use Claude
    RESEARCH = "research"  # Use Claude
    METRIC_QUERY = "metric_query"  # Use Claude or direct API
    UNKNOWN = "unknown"  # Default to Claude


class LLMRouter:
    """
    Routes queries to appropriate LLM based on query characteristics.
    
    Claude 4.5 Sonnet: Best for explanations, analysis, research
    GPT-4 Turbo: Best for structured planning, optimization logic
    """
    
    def __init__(self):
        """Initialize LLM router."""
        self.claude_model = "claude-3-5-sonnet-20241022"  # Claude 4.5 Sonnet
        self.gpt4_model = "gpt-4-turbo-preview"  # GPT-4 Turbo
        
        # Keywords for classification
        self.optimization_keywords = [
            "optimize", "optimization", "allocate", "allocation", "budget",
            "plan", "strategy", "recommend", "suggest", "reallocate",
            "redistribute", "adjust", "modify", "change budget"
        ]
        
        self.explanation_keywords = [
            "why", "explain", "reason", "cause", "because", "due to",
            "what caused", "what led to", "how did", "what happened",
            "anomaly", "unusual", "unexpected", "strange"
        ]
        
        self.analysis_keywords = [
            "analyze", "analysis", "compare", "trend", "pattern",
            "performance", "metrics", "statistics", "insights"
        ]
        
        self.research_keywords = [
            "research", "search", "find", "investigate", "look up",
            "trend", "news", "competitor", "market", "external"
        ]
    
    def classify_query(self, query: str) -> QueryType:
        """
        Classify query type based on content.
        
        Args:
            query: User query string
        
        Returns:
            QueryType enum
        """
        query_lower = query.lower()
        
        # Check for optimization queries
        if any(keyword in query_lower for keyword in self.optimization_keywords):
            return QueryType.OPTIMIZATION
        
        # Check for explanation queries
        if any(keyword in query_lower for keyword in self.explanation_keywords):
            return QueryType.EXPLANATION
        
        # Check for research queries
        if any(keyword in query_lower for keyword in self.research_keywords):
            return QueryType.RESEARCH
        
        # Check for analysis queries
        if any(keyword in query_lower for keyword in self.analysis_keywords):
            return QueryType.ANALYSIS
        
        # Check for metric queries (simple data requests)
        metric_patterns = [
            r"show me",
            r"what is",
            r"what are",
            r"get",
            r"fetch",
            r"roas",
            r"ctr",
            r"cvr",
            r"revenue",
            r"cost"
        ]
        if any(re.search(pattern, query_lower) for pattern in metric_patterns):
            return QueryType.METRIC_QUERY
        
        return QueryType.UNKNOWN
    
    def select_model(self, query: str) -> str:
        """
        Select appropriate LLM model for query.
        
        Args:
            query: User query string
        
        Returns:
            Model identifier string
        """
        query_type = self.classify_query(query)
        
        if query_type == QueryType.OPTIMIZATION:
            logger.info(f"Routing to GPT-4 Turbo (optimization query)")
            return self.gpt4_model
        else:
            logger.info(f"Routing to Claude 4.5 Sonnet ({query_type.value} query)")
            return self.claude_model
    
    def get_model_for_type(self, query_type: QueryType) -> str:
        """
        Get model for specific query type.
        
        Args:
            query_type: QueryType enum
        
        Returns:
            Model identifier string
        """
        if query_type == QueryType.OPTIMIZATION:
            return self.gpt4_model
        else:
            return self.claude_model
    
    def should_use_direct_api(self, query: str) -> bool:
        """
        Determine if query should use direct API instead of LLM.
        
        Simple metric queries can bypass LLM for speed.
        
        Args:
            query: User query string
        
        Returns:
            True if should use direct API
        """
        query_type = self.classify_query(query)
        
        # Simple metric queries can use direct API
        if query_type == QueryType.METRIC_QUERY:
            # Check if it's a simple query (no complex reasoning needed)
            simple_patterns = [
                r"^show me (roas|ctr|cvr|revenue|cost)",
                r"^what is (the )?(roas|ctr|cvr|revenue|cost)",
                r"^get (roas|ctr|cvr|revenue|cost)"
            ]
            if any(re.search(pattern, query.lower()) for pattern in simple_patterns):
                return True
        
        return False


# Global router instance
_router_instance: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    """Get or create global LLM router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = LLMRouter()
    return _router_instance
