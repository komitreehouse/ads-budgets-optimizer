"""
Research Tools for External Data Access

Integrates with Tavily (web search) and Google Trends.
"""

from typing import Dict, List, Optional, Any
import os

from src.bandit_ads.utils import get_logger

logger = get_logger('research_tools')


class TavilySearch:
    """Tavily API integration for web search."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Tavily search.
        
        Args:
            api_key: Tavily API key (from env or parameter)
        """
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            logger.warning("Tavily API key not found. Set TAVILY_API_KEY env var.")
        
        self.base_url = "https://api.tavily.com/v1"
    
    def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic"
    ) -> List[Dict[str, Any]]:
        """
        Search the web using Tavily.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            search_depth: "basic" or "advanced"
        
        Returns:
            List of search results
        """
        if not self.api_key:
            logger.error("Tavily API key not configured")
            return []
        
        try:
            import requests
            
            response = requests.post(
                f"{self.base_url}/search",
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": search_depth
                },
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Tavily API error: {response.status_code}")
                return []
            
            data = response.json()
            results = data.get("results", [])
            
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "score": result.get("score", 0.0)
                })
            
            logger.info(f"Tavily search: '{query}' -> {len(formatted_results)} results")
            return formatted_results
            
        except ImportError:
            logger.error("requests library not installed")
            return []
        except Exception as e:
            logger.error(f"Error searching Tavily: {str(e)}")
            return []


class GoogleTrends:
    """Google Trends API integration."""
    
    def __init__(self):
        """Initialize Google Trends."""
        # Note: Google Trends doesn't have official API
        # We'll use pytrends library which scrapes Google Trends
        try:
            from pytrends.request import TrendReq
            self.pytrends = TrendReq(hl='en-US', tz=360)
            self.available = True
            logger.info("Google Trends initialized")
        except ImportError:
            logger.warning("pytrends not installed. Install with: pip install pytrends")
            self.available = False
    
    def get_trend(
        self,
        keyword: str,
        timeframe: str = "today 7-d",
        geo: str = "US"
    ) -> Dict[str, Any]:
        """
        Get trend data for a keyword.
        
        Args:
            keyword: Search keyword
            timeframe: Time range (e.g., "today 7-d", "today 1-m")
            geo: Geographic location (e.g., "US", "GB")
        
        Returns:
            Trend data dictionary
        """
        if not self.available:
            return {"error": "Google Trends not available"}
        
        try:
            self.pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
            trend_data = self.pytrends.interest_over_time()
            
            if trend_data.empty:
                return {"error": "No trend data available"}
            
            # Calculate trend direction
            values = trend_data[keyword].values
            if len(values) > 1:
                trend_direction = "increasing" if values[-1] > values[0] else "decreasing"
                change_percent = ((values[-1] - values[0]) / values[0]) * 100
            else:
                trend_direction = "stable"
                change_percent = 0
            
            return {
                "keyword": keyword,
                "timeframe": timeframe,
                "geo": geo,
                "trend_direction": trend_direction,
                "change_percent": change_percent,
                "current_value": float(values[-1]) if len(values) > 0 else 0,
                "average_value": float(values.mean()) if len(values) > 0 else 0,
                "data_points": len(values)
            }
        except Exception as e:
            logger.error(f"Error getting Google Trends data: {str(e)}")
            return {"error": str(e)}
    
    def compare_keywords(
        self,
        keywords: List[str],
        timeframe: str = "today 7-d",
        geo: str = "US"
    ) -> Dict[str, Any]:
        """
        Compare trends for multiple keywords.
        
        Args:
            keywords: List of keywords to compare
            timeframe: Time range
            geo: Geographic location
        
        Returns:
            Comparison data
        """
        if not self.available:
            return {"error": "Google Trends not available"}
        
        try:
            self.pytrends.build_payload(keywords, timeframe=timeframe, geo=geo)
            trend_data = self.pytrends.interest_over_time()
            
            if trend_data.empty:
                return {"error": "No trend data available"}
            
            comparison = {}
            for keyword in keywords:
                if keyword in trend_data.columns:
                    values = trend_data[keyword].values
                    comparison[keyword] = {
                        "current_value": float(values[-1]) if len(values) > 0 else 0,
                        "average_value": float(values.mean()) if len(values) > 0 else 0,
                        "trend": "increasing" if len(values) > 1 and values[-1] > values[0] else "decreasing"
                    }
            
            return {
                "keywords": keywords,
                "timeframe": timeframe,
                "comparison": comparison
            }
        except Exception as e:
            logger.error(f"Error comparing keywords: {str(e)}")
            return {"error": str(e)}


class ResearchTools:
    """Combined research tools."""
    
    def __init__(self):
        """Initialize research tools."""
        self.tavily = TavilySearch()
        self.google_trends = GoogleTrends()
        logger.info("Research tools initialized")
    
    def research_topic(
        self,
        topic: str,
        include_trends: bool = True,
        max_search_results: int = 5
    ) -> Dict[str, Any]:
        """
        Research a topic using web search and trends.
        
        Args:
            topic: Topic to research
            include_trends: Whether to include Google Trends data
            max_search_results: Maximum search results
        
        Returns:
            Research results
        """
        results = {
            "topic": topic,
            "web_search": [],
            "trends": None
        }
        
        # Web search
        search_results = self.tavily.search(topic, max_results=max_search_results)
        results["web_search"] = search_results
        
        # Trends (if requested)
        if include_trends:
            trend_data = self.google_trends.get_trend(topic)
            results["trends"] = trend_data
        
        return results


# Global research tools instance
_research_tools_instance: Optional[ResearchTools] = None


def get_research_tools() -> ResearchTools:
    """Get or create global research tools instance."""
    global _research_tools_instance
    if _research_tools_instance is None:
        _research_tools_instance = ResearchTools()
    return _research_tools_instance
