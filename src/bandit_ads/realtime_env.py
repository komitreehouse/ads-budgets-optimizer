"""
Real-Time Environment for Advertising Data

Connects to actual advertising platform APIs to get real performance metrics
instead of simulated data. Falls back to simulation if APIs are unavailable.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from collections import defaultdict

from src.bandit_ads.env import AdEnvironment
from src.bandit_ads.arms import Arm
from src.bandit_ads.api_connectors import (
    BaseAPIConnector, create_api_connector
)
from src.bandit_ads.utils import get_logger, handle_errors, retry_on_failure


class RealTimeEnvironment(AdEnvironment):
    """
    Real-time advertising environment that fetches actual performance data
    from advertising platform APIs.
    
    Falls back to simulated data if APIs are unavailable or fail.
    """
    
    def __init__(
        self,
        api_connectors: Dict[str, BaseAPIConnector] = None,
        fallback_to_simulated: bool = True,
        data_retention_days: int = 7,
        **kwargs
    ):
        """
        Initialize real-time environment.
        
        Args:
            api_connectors: Dictionary mapping platform names to API connectors
            fallback_to_simulated: Whether to use simulated data if APIs fail
            data_retention_days: Days to cache API responses
            **kwargs: Arguments passed to parent AdEnvironment
        """
        super().__init__(**kwargs)
        
        self.api_connectors = api_connectors or {}
        self.fallback_to_simulated = fallback_to_simulated
        self.data_retention_days = data_retention_days
        self.logger = get_logger('realtime_env')
        
        # Cache for API responses
        self.metrics_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
        
        # Authenticate with all connectors
        self._authenticate_connectors()
    
    def _authenticate_connectors(self):
        """Authenticate with all API connectors."""
        authenticated = []
        failed = []
        
        for platform, connector in self.api_connectors.items():
            try:
                if connector.authenticate():
                    authenticated.append(platform)
                    self.logger.info(f"Authenticated with {platform} API")
                else:
                    failed.append(platform)
                    self.logger.warning(f"Failed to authenticate with {platform} API")
            except Exception as e:
                failed.append(platform)
                self.logger.error(f"Error authenticating with {platform}: {str(e)}")
        
        if authenticated:
            self.logger.info(f"Successfully connected to: {', '.join(authenticated)}")
        if failed and not self.fallback_to_simulated:
            self.logger.warning(
                f"Some APIs failed: {', '.join(failed)}. "
                "Consider enabling fallback_to_simulated=True"
            )
    
    def _get_connector_for_arm(self, arm: Arm) -> Optional[BaseAPIConnector]:
        """Get the appropriate API connector for an arm's platform."""
        platform = arm.platform.lower()
        
        # Map platform names to connector keys
        platform_mapping = {
            'google': ['google', 'google_ads'],
            'meta': ['meta', 'facebook', 'instagram'],
            'the trade desk': ['trade_desk', 'ttd', 'the_trade_desk']
        }
        
        for connector_key, platforms in platform_mapping.items():
            if platform in platforms:
                return self.api_connectors.get(connector_key)
        
        return None
    
    def _get_cached_metrics(self, arm_key: str) -> Optional[Dict[str, Any]]:
        """Get cached metrics if still valid."""
        if arm_key not in self.metrics_cache:
            return None
        
        cache_time = self.cache_timestamps.get(arm_key)
        if cache_time:
            age = datetime.now() - cache_time
            if age < timedelta(days=self.data_retention_days):
                return self.metrics_cache[arm_key]
            else:
                # Cache expired
                del self.metrics_cache[arm_key]
                del self.cache_timestamps[arm_key]
        
        return None
    
    def _cache_metrics(self, arm_key: str, metrics: Dict[str, Any]):
        """Cache metrics with timestamp."""
        self.metrics_cache[arm_key] = metrics
        self.cache_timestamps[arm_key] = datetime.now()
    
    @retry_on_failure(max_retries=2, delay=1.0)
    def _fetch_real_metrics(
        self, 
        arm: Arm, 
        start_date: datetime, 
        end_date: datetime
    ) -> Optional[Dict[str, Any]]:
        """Fetch real metrics from API."""
        connector = self._get_connector_for_arm(arm)
        
        if not connector:
            self.logger.debug(f"No connector available for platform: {arm.platform}")
            return None
        
        try:
            metrics = connector.get_campaign_metrics(arm, start_date, end_date)
            
            # Validate metrics structure
            required_keys = ['impressions', 'clicks', 'conversions', 'cost', 'revenue', 'roas']
            if all(key in metrics for key in required_keys):
                return metrics
            else:
                self.logger.warning(f"Invalid metrics structure from {arm.platform}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error fetching metrics from {arm.platform}: {str(e)}")
            return None
    
    @handle_errors(default_return=None)
    def step(
        self, 
        arm: Arm, 
        impressions: int = 1, 
        spend_amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Get performance metrics for an arm, using real API data if available.
        
        Falls back to simulated data if:
        - No API connector available for the platform
        - API call fails
        - fallback_to_simulated is True
        """
        arm_key = str(arm)
        
        # Try to get cached metrics first
        cached_metrics = self._get_cached_metrics(arm_key)
        if cached_metrics:
            self.logger.debug(f"Using cached metrics for {arm_key}")
            return cached_metrics
        
        # Try to fetch real metrics
        end_date = self.current_date
        start_date = end_date - timedelta(days=1)  # Last 24 hours
        
        real_metrics = self._fetch_real_metrics(arm, start_date, end_date)
        
        if real_metrics:
            # Cache and return real metrics
            self._cache_metrics(arm_key, real_metrics)
            self.logger.debug(f"Fetched real metrics for {arm_key} from {real_metrics.get('source')}")
            
            # Apply MMM factors to real data (optional - can be disabled)
            # For now, return raw API data
            return real_metrics
        
        # Fall back to simulated data
        if self.fallback_to_simulated:
            self.logger.debug(f"Falling back to simulated data for {arm_key}")
            return super().step(arm, impressions, spend_amount)
        else:
            # Return empty metrics if no fallback
            self.logger.warning(f"No data available for {arm_key} and fallback disabled")
            return {
                "impressions": 0,
                "clicks": 0,
                "conversions": 0,
                "revenue": 0.0,
                "cost": 0.0,
                "roas": 0.0,
                "source": "none",
                "mmm_factors": {
                    "seasonal_multiplier": 1.0,
                    "carryover_multiplier": 1.0,
                    "competitive_multiplier": 1.0,
                    "external_multiplier": 1.0,
                    "effective_ctr": 0.0,
                    "effective_cvr": 0.0
                }
            }
    
    def update_bid(self, arm: Arm, new_bid: float) -> bool:
        """
        Update bid for an arm using the API.
        
        Args:
            arm: Arm to update
            new_bid: New bid value
        
        Returns:
            True if successful
        """
        connector = self._get_connector_for_arm(arm)
        
        if not connector:
            self.logger.warning(f"No connector available to update bid for {arm.platform}")
            return False
        
        try:
            success = connector.update_bid(arm, new_bid)
            if success:
                self.logger.info(f"Updated bid for {arm} to ${new_bid}")
                # Invalidate cache for this arm
                arm_key = str(arm)
                if arm_key in self.metrics_cache:
                    del self.metrics_cache[arm_key]
                    del self.cache_timestamps[arm_key]
            return success
        except Exception as e:
            self.logger.error(f"Error updating bid: {str(e)}")
            return False
    
    def get_available_campaigns(self, platform: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of available campaigns from APIs.
        
        Args:
            platform: Optional platform name to filter
        
        Returns:
            List of campaign dictionaries
        """
        campaigns = []
        
        connectors_to_query = {}
        if platform:
            # Find connector for specific platform
            connector = create_api_connector(platform, {})
            if connector and platform.lower() in [k.lower() for k in self.api_connectors.keys()]:
                connectors_to_query[platform] = self.api_connectors.get(platform.lower())
        else:
            # Query all connectors
            connectors_to_query = self.api_connectors
        
        for platform_name, connector in connectors_to_query.items():
            try:
                platform_campaigns = connector.get_available_campaigns()
                for camp in platform_campaigns:
                    camp['platform'] = platform_name
                campaigns.extend(platform_campaigns)
            except Exception as e:
                self.logger.error(f"Error fetching campaigns from {platform_name}: {str(e)}")
        
        return campaigns
