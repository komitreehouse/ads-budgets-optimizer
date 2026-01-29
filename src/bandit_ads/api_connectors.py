"""
API Connectors for Real-Time Advertising Data

Provides interfaces to connect with advertising platform APIs:
- Google Ads API
- Meta Marketing API (Facebook/Instagram)
- The Trade Desk API
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import time

from src.bandit_ads.utils import get_logger, retry_on_failure, handle_errors
from src.bandit_ads.arms import Arm


class BaseAPIConnector(ABC):
    """Base class for all advertising platform API connectors."""
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize API connector.
        
        Args:
            credentials: Dictionary containing API credentials
        """
        self.credentials = credentials
        self.logger = get_logger(f'api.{self.__class__.__name__}')
        self.rate_limit_delay = 1.0  # Default rate limit delay
        self.last_request_time = 0.0
    
    def _rate_limit(self):
        """Enforce rate limiting between API requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the API. Returns True if successful."""
        pass
    
    @abstractmethod
    def get_campaign_metrics(
        self, 
        arm: Arm, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get performance metrics for a specific arm.
        
        Args:
            arm: Arm object representing the ad configuration
            start_date: Start date for metrics
            end_date: End date for metrics
        
        Returns:
            Dictionary with metrics: impressions, clicks, conversions, cost, revenue
        """
        pass
    
    @abstractmethod
    def update_bid(self, arm: Arm, new_bid: float) -> bool:
        """
        Update bid for an arm.
        
        Args:
            arm: Arm object
            new_bid: New bid value
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_available_campaigns(self) -> List[Dict[str, Any]]:
        """Get list of available campaigns."""
        pass


class GoogleAdsConnector(BaseAPIConnector):
    """Connector for Google Ads API."""
    
    def __init__(self, credentials: Dict[str, Any]):
        super().__init__(credentials)
        self.client = None
        self.customer_id = credentials.get('customer_id', '')
        self.rate_limit_delay = 0.5  # Google Ads rate limit
    
    @retry_on_failure(max_retries=3, delay=2.0)
    def authenticate(self) -> bool:
        """Authenticate with Google Ads API."""
        try:
            # Import here to avoid dependency if not using Google Ads
            from google.ads.googleads.client import GoogleAdsClient
            from google.ads.googleads.errors import GoogleAdsException
            
            # Initialize client from credentials
            self.client = GoogleAdsClient.load_from_dict({
                'developer_token': self.credentials.get('developer_token'),
                'client_id': self.credentials.get('client_id'),
                'client_secret': self.credentials.get('client_secret'),
                'refresh_token': self.credentials.get('refresh_token'),
                'use_proto_plus': True
            })
            
            self.logger.info("Successfully authenticated with Google Ads API")
            return True
            
        except ImportError:
            self.logger.warning(
                "google-ads library not installed. Install with: pip install google-ads"
            )
            return False
        except Exception as e:
            self.logger.error(f"Google Ads authentication failed: {str(e)}")
            return False
    
    @retry_on_failure(max_retries=3)
    def get_campaign_metrics(
        self, 
        arm: Arm, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get metrics from Google Ads API."""
        if not self.client:
            self.logger.error("Not authenticated. Call authenticate() first.")
            return self._empty_metrics()
        
        self._rate_limit()
        
        try:
            # Build GAQL query to get metrics for the specific campaign/ad group
            # This is a simplified example - actual implementation would need
            # to map arm attributes to Google Ads entities
            query = f"""
                SELECT
                    campaign.id,
                    campaign.name,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.conversions,
                    metrics.cost_micros,
                    metrics.conversions_value
                FROM campaign
                WHERE campaign.id = {self._get_campaign_id(arm)}
                AND segments.date BETWEEN '{start_date.strftime('%Y-%m-%d')}' 
                AND '{end_date.strftime('%Y-%m-%d')}'
            """
            
            response = self.client.service.google_ads_service.search(
                customer_id=self.customer_id,
                query=query
            )
            
            # Aggregate metrics
            total_impressions = 0
            total_clicks = 0
            total_conversions = 0
            total_cost = 0.0
            total_revenue = 0.0
            
            for row in response:
                total_impressions += row.metrics.impressions
                total_clicks += row.metrics.clicks
                total_conversions += row.metrics.conversions
                total_cost += row.metrics.cost_micros / 1_000_000  # Convert micros to dollars
                total_revenue += row.metrics.conversions_value
            
            roas = total_revenue / total_cost if total_cost > 0 else 0.0
            
            return {
                'impressions': total_impressions,
                'clicks': total_clicks,
                'conversions': total_conversions,
                'cost': total_cost,
                'revenue': total_revenue,
                'roas': roas,
                'source': 'google_ads',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching Google Ads metrics: {str(e)}")
            return self._empty_metrics()
    
    def update_bid(self, arm: Arm, new_bid: float) -> bool:
        """Update bid in Google Ads."""
        # Implementation would use Google Ads API to update keyword bids
        # or ad group bids based on arm configuration
        self.logger.info(f"Updating bid for {arm} to ${new_bid}")
        return True
    
    def get_available_campaigns(self) -> List[Dict[str, Any]]:
        """Get list of available Google Ads campaigns."""
        if not self.client:
            return []
        
        try:
            query = "SELECT campaign.id, campaign.name FROM campaign WHERE campaign.status = 'ENABLED'"
            response = self.client.service.google_ads_service.search(
                customer_id=self.customer_id,
                query=query
            )
            
            return [
                {'id': row.campaign.id, 'name': row.campaign.name}
                for row in response
            ]
        except Exception as e:
            self.logger.error(f"Error fetching campaigns: {str(e)}")
            return []
    
    def _get_campaign_id(self, arm: Arm) -> str:
        """Map arm to Google Ads campaign ID. This is a placeholder."""
        # In production, you'd maintain a mapping between arms and campaign IDs
        return self.credentials.get('default_campaign_id', '')
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure."""
        return {
            'impressions': 0,
            'clicks': 0,
            'conversions': 0,
            'cost': 0.0,
            'revenue': 0.0,
            'roas': 0.0,
            'source': 'google_ads',
            'timestamp': datetime.now().isoformat()
        }


class MetaAdsConnector(BaseAPIConnector):
    """Connector for Meta Marketing API (Facebook/Instagram)."""
    
    def __init__(self, credentials: Dict[str, Any]):
        super().__init__(credentials)
        self.api = None
        self.ad_account_id = credentials.get('ad_account_id', '')
        self.rate_limit_delay = 0.5
    
    @retry_on_failure(max_retries=3, delay=2.0)
    def authenticate(self) -> bool:
        """Authenticate with Meta Marketing API."""
        try:
            from facebook_business.api import FacebookAdsApi
            from facebook_business.adobjects.adaccount import AdAccount
            
            access_token = self.credentials.get('access_token')
            if not access_token:
                self.logger.error("Meta access token not provided")
                return False
            
            FacebookAdsApi.init(
                access_token=access_token,
                app_id=self.credentials.get('app_id'),
                app_secret=self.credentials.get('app_secret')
            )
            
            self.api = FacebookAdsApi.get_default_api()
            self.logger.info("Successfully authenticated with Meta Marketing API")
            return True
            
        except ImportError:
            self.logger.warning(
                "facebook-business library not installed. Install with: pip install facebook-business"
            )
            return False
        except Exception as e:
            self.logger.error(f"Meta authentication failed: {str(e)}")
            return False
    
    @retry_on_failure(max_retries=3)
    def get_campaign_metrics(
        self, 
        arm: Arm, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get metrics from Meta Marketing API."""
        if not self.api:
            return self._empty_metrics()
        
        self._rate_limit()
        
        try:
            from facebook_business.adobjects.adaccount import AdAccount
            from facebook_business.adobjects.adsinsights import AdsInsights
            
            account = AdAccount(f"act_{self.ad_account_id}")
            
            # Get insights for the date range
            params = {
                'time_range': {
                    'since': start_date.strftime('%Y-%m-%d'),
                    'until': end_date.strftime('%Y-%m-%d')
                },
                'fields': [
                    'impressions',
                    'clicks',
                    'conversions',
                    'spend',
                    'actions'
                ],
                'level': 'campaign'
            }
            
            insights = account.get_insights(params=params)
            
            # Aggregate metrics
            total_impressions = 0
            total_clicks = 0
            total_conversions = 0
            total_cost = 0.0
            total_revenue = 0.0
            
            for insight in insights:
                total_impressions += int(insight.get('impressions', 0))
                total_clicks += int(insight.get('clicks', 0))
                total_cost += float(insight.get('spend', 0))
                
                # Extract conversions from actions
                actions = insight.get('actions', [])
                for action in actions:
                    if action.get('action_type') == 'purchase':
                        total_conversions += int(action.get('value', 0))
                        total_revenue += float(action.get('value', 0))
            
            roas = total_revenue / total_cost if total_cost > 0 else 0.0
            
            return {
                'impressions': total_impressions,
                'clicks': total_clicks,
                'conversions': total_conversions,
                'cost': total_cost,
                'revenue': total_revenue,
                'roas': roas,
                'source': 'meta_ads',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching Meta Ads metrics: {str(e)}")
            return self._empty_metrics()
    
    def update_bid(self, arm: Arm, new_bid: float) -> bool:
        """Update bid in Meta Ads."""
        self.logger.info(f"Updating bid for {arm} to ${new_bid}")
        return True
    
    def get_available_campaigns(self) -> List[Dict[str, Any]]:
        """Get list of available Meta campaigns."""
        if not self.api:
            return []
        
        try:
            from facebook_business.adobjects.adaccount import AdAccount
            
            account = AdAccount(f"act_{self.ad_account_id}")
            campaigns = account.get_campaigns(fields=['id', 'name'])
            
            return [
                {'id': camp.get('id'), 'name': camp.get('name')}
                for camp in campaigns
            ]
        except Exception as e:
            self.logger.error(f"Error fetching campaigns: {str(e)}")
            return []
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure."""
        return {
            'impressions': 0,
            'clicks': 0,
            'conversions': 0,
            'cost': 0.0,
            'revenue': 0.0,
            'roas': 0.0,
            'source': 'meta_ads',
            'timestamp': datetime.now().isoformat()
        }


class TradeDeskConnector(BaseAPIConnector):
    """Connector for The Trade Desk API."""
    
    def __init__(self, credentials: Dict[str, Any]):
        super().__init__(credentials)
        self.session = None
        self.advertiser_id = credentials.get('advertiser_id', '')
        self.rate_limit_delay = 1.0
    
    @retry_on_failure(max_retries=3, delay=2.0)
    def authenticate(self) -> bool:
        """Authenticate with The Trade Desk API."""
        try:
            import requests
            
            # The Trade Desk uses token-based authentication
            auth_url = "https://api.thetradedesk.com/v3/authentication"
            
            response = requests.post(
                auth_url,
                json={
                    'Login': self.credentials.get('username'),
                    'Password': self.credentials.get('password')
                }
            )
            
            if response.status_code == 200:
                token = response.json().get('Token')
                self.session = requests.Session()
                self.session.headers.update({'TTD-Auth': token})
                self.logger.info("Successfully authenticated with The Trade Desk API")
                return True
            else:
                self.logger.error(f"The Trade Desk authentication failed: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"The Trade Desk authentication failed: {str(e)}")
            return False
    
    @retry_on_failure(max_retries=3)
    def get_campaign_metrics(
        self, 
        arm: Arm, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get metrics from The Trade Desk API."""
        if not self.session:
            return self._empty_metrics()
        
        self._rate_limit()
        
        try:
            # The Trade Desk API endpoint for reporting
            url = f"https://api.thetradedesk.com/v3/myquery/report"
            
            params = {
                'AdvertiserId': self.advertiser_id,
                'StartDate': start_date.strftime('%Y-%m-%d'),
                'EndDate': end_date.strftime('%Y-%m-%d'),
                'GroupBy': ['CampaignId'],
                'Metrics': ['Impressions', 'Clicks', 'Conversions', 'Spend', 'Revenue']
            }
            
            response = self.session.post(url, json=params)
            
            if response.status_code == 200:
                data = response.json()
                # Process response and aggregate metrics
                # This is simplified - actual implementation would parse the report
                return {
                    'impressions': data.get('Impressions', 0),
                    'clicks': data.get('Clicks', 0),
                    'conversions': data.get('Conversions', 0),
                    'cost': data.get('Spend', 0.0),
                    'revenue': data.get('Revenue', 0.0),
                    'roas': data.get('Revenue', 0.0) / data.get('Spend', 1.0) if data.get('Spend', 0) > 0 else 0.0,
                    'source': 'trade_desk',
                    'timestamp': datetime.now().isoformat()
                }
            else:
                self.logger.error(f"The Trade Desk API error: {response.text}")
                return self._empty_metrics()
                
        except Exception as e:
            self.logger.error(f"Error fetching The Trade Desk metrics: {str(e)}")
            return self._empty_metrics()
    
    def update_bid(self, arm: Arm, new_bid: float) -> bool:
        """Update bid in The Trade Desk."""
        self.logger.info(f"Updating bid for {arm} to ${new_bid}")
        return True
    
    def get_available_campaigns(self) -> List[Dict[str, Any]]:
        """Get list of available Trade Desk campaigns."""
        if not self.session:
            return []
        
        try:
            url = f"https://api.thetradedesk.com/v3/campaign/query/advertiser"
            params = {'AdvertiserId': self.advertiser_id}
            
            response = self.session.get(url, params=params)
            
            if response.status_code == 200:
                campaigns = response.json().get('Result', [])
                return [
                    {'id': camp.get('CampaignId'), 'name': camp.get('CampaignName')}
                    for camp in campaigns
                ]
            return []
        except Exception as e:
            self.logger.error(f"Error fetching campaigns: {str(e)}")
            return []
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure."""
        return {
            'impressions': 0,
            'clicks': 0,
            'conversions': 0,
            'cost': 0.0,
            'revenue': 0.0,
            'roas': 0.0,
            'source': 'trade_desk',
            'timestamp': datetime.now().isoformat()
        }


def create_api_connector(platform: str, credentials: Dict[str, Any]) -> Optional[BaseAPIConnector]:
    """
    Factory function to create appropriate API connector.
    
    Args:
        platform: Platform name ('google', 'meta', 'trade_desk')
        credentials: Platform-specific credentials
    
    Returns:
        API connector instance or None if platform not supported
    """
    platform_lower = platform.lower()
    
    if platform_lower in ['google', 'google_ads']:
        return GoogleAdsConnector(credentials)
    elif platform_lower in ['meta', 'facebook', 'instagram']:
        return MetaAdsConnector(credentials)
    elif platform_lower in ['trade_desk', 'ttd', 'the_trade_desk']:
        return TradeDeskConnector(credentials)
    else:
        logger = get_logger('api')
        logger.error(f"Unsupported platform: {platform}")
        return None
