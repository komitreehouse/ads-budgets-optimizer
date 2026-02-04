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
from src.bandit_ads.db_helpers import (
    get_arm_platform_entity_ids, 
    update_arm_bid,
    get_arm,
    get_arm_by_attributes
)
import json


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
    
    @retry_on_failure(max_retries=3)
    def update_bid(self, arm: Arm, new_bid: float) -> bool:
        """
        Update bid in Google Ads.
        
        Updates keyword bid if keyword_id is available, otherwise updates ad group bid.
        """
        if not self.client:
            self.logger.error("Not authenticated. Call authenticate() first.")
            return False
        
        self._rate_limit()
        
        try:
            from google.ads.googleads.errors import GoogleAdsException
            # Use the client's version-agnostic methods instead of hardcoded version
            # The client handles versioning automatically
            
            # Look up arm in database first
            db_arm_id = self._get_arm_from_db(arm)
            
            keyword_id = self._get_keyword_id(arm, db_arm_id)
            ad_group_id = self._get_ad_group_id(arm, db_arm_id)
            campaign_id = self._get_campaign_id(arm, db_arm_id)
            
            if keyword_id and ad_group_id:
                # Update keyword bid (CPC bid)
                self.logger.info(f"Updating keyword bid for arm {arm} to ${new_bid}")
                
                # Get services
                google_ads_service = self.client.get_service("GoogleAdsService")
                ad_group_criterion_service = self.client.get_service("AdGroupCriterionService")
                
                # Create ad group criterion operation
                ad_group_criterion = self.client.get_type("AdGroupCriterion")
                ad_group_criterion.resource_name = google_ads_service.ad_group_criterion_path(
                    self.customer_id, ad_group_id, keyword_id
                )
                
                # Set the bid (convert dollars to micros)
                ad_group_criterion.cpc_bid_micros = int(new_bid * 1_000_000)
                
                # Create mutate operation
                mutate_operation = self.client.get_type("AdGroupCriterionOperation")
                mutate_operation.update = ad_group_criterion
                mutate_operation.update_mask.CopyFrom(
                    self.client.get_type("FieldMask")(paths=["cpc_bid_micros"])
                )
                
                # Execute the mutation
                response = ad_group_criterion_service.mutate_ad_group_criteria(
                    customer_id=self.customer_id,
                    operations=[mutate_operation]
                )
                
                # Update bid in database
                if db_arm_id:
                    update_arm_bid(db_arm_id, new_bid)
                
                self.logger.info(f"Successfully updated keyword bid to ${new_bid}")
                return True
                
            elif ad_group_id:
                # Update ad group bid (CPC bid)
                self.logger.info(f"Updating ad group bid for arm {arm} to ${new_bid}")
                
                # Get services
                google_ads_service = self.client.get_service("GoogleAdsService")
                ad_group_service = self.client.get_service("AdGroupService")
                
                # Create ad group operation
                ad_group = self.client.get_type("AdGroup")
                ad_group.resource_name = google_ads_service.ad_group_path(
                    self.customer_id, ad_group_id
                )
                
                # Set the bid (convert dollars to micros)
                ad_group.cpc_bid_micros = int(new_bid * 1_000_000)
                
                # Create mutate operation
                mutate_operation = self.client.get_type("AdGroupOperation")
                mutate_operation.update = ad_group
                mutate_operation.update_mask.CopyFrom(
                    self.client.get_type("FieldMask")(paths=["cpc_bid_micros"])
                )
                
                # Execute the mutation
                response = ad_group_service.mutate_ad_groups(
                    customer_id=self.customer_id,
                    operations=[mutate_operation]
                )
                
                # Update bid in database
                if db_arm_id:
                    update_arm_bid(db_arm_id, new_bid)
                
                self.logger.info(f"Successfully updated ad group bid to ${new_bid}")
                return True
            else:
                self.logger.warning(
                    f"Cannot update bid for arm {arm}: missing keyword_id or ad_group_id. "
                    f"Set platform_entity_ids in the arm's database record."
                )
                return False
                
        except ImportError:
            self.logger.warning(
                "google-ads library not installed. Install with: pip install google-ads"
            )
            return False
        except GoogleAdsException as e:
            self.logger.error(f"Google Ads API error updating bid: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error updating Google Ads bid: {str(e)}")
            return False
    
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
    
    def _get_arm_from_db(self, arm: Arm, campaign_id: Optional[int] = None) -> Optional[int]:
        """
        Look up arm in database to get its ID.
        
        Args:
            arm: Arm object
            campaign_id: Optional campaign ID to narrow search
        
        Returns:
            Database arm ID or None if not found
        """
        from src.bandit_ads.database import get_db_manager
        from sqlalchemy import and_
        
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            from src.bandit_ads.database import Arm as DBArm
            
            query = session.query(DBArm).filter(
                and_(
                    DBArm.platform == arm.platform,
                    DBArm.channel == arm.channel,
                    DBArm.creative == arm.creative
                )
            )
            
            if campaign_id:
                query = query.filter(DBArm.campaign_id == campaign_id)
            
            db_arm = query.first()
            return db_arm.id if db_arm else None
    
    def _get_campaign_id(self, arm: Arm, db_arm_id: Optional[int] = None) -> str:
        """
        Map arm to Google Ads campaign ID.
        
        First tries to get from arm's platform_entity_ids in database,
        then falls back to credentials default.
        """
        # Try to get from database
        arm_id = db_arm_id
        if not arm_id:
            arm_id = self._get_arm_from_db(arm)
        
        if arm_id:
            entity_ids = get_arm_platform_entity_ids(arm_id)
            if entity_ids and 'campaign_id' in entity_ids:
                return str(entity_ids['campaign_id'])
        
        # Fall back to credentials default
        return self.credentials.get('default_campaign_id', '')
    
    def _get_ad_group_id(self, arm: Arm, db_arm_id: Optional[int] = None) -> Optional[str]:
        """Get Google Ads ad group ID from arm's platform_entity_ids."""
        arm_id = db_arm_id
        if not arm_id:
            arm_id = self._get_arm_from_db(arm)
        
        if arm_id:
            entity_ids = get_arm_platform_entity_ids(arm_id)
            if entity_ids and 'ad_group_id' in entity_ids:
                return str(entity_ids['ad_group_id'])
        return None
    
    def _get_keyword_id(self, arm: Arm, db_arm_id: Optional[int] = None) -> Optional[str]:
        """Get Google Ads keyword ID from arm's platform_entity_ids."""
        arm_id = db_arm_id
        if not arm_id:
            arm_id = self._get_arm_from_db(arm)
        
        if arm_id:
            entity_ids = get_arm_platform_entity_ids(arm_id)
            if entity_ids and 'keyword_id' in entity_ids:
                return str(entity_ids['keyword_id'])
        return None
    
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
    
    @retry_on_failure(max_retries=3)
    def update_bid(self, arm: Arm, new_bid: float) -> bool:
        """
        Update bid in Meta Ads.
        
        Updates the bid for an ad set or ad based on arm's platform_entity_ids.
        """
        if not self.api:
            self.logger.error("Not authenticated. Call authenticate() first.")
            return False
        
        self._rate_limit()
        
        try:
            from facebook_business.adobjects.adset import AdSet
            from facebook_business.adobjects.ad import Ad
            from facebook_business.exceptions import FacebookRequestError
            
            # Look up arm in database first
            from src.bandit_ads.database import get_db_manager
            from sqlalchemy import and_
            from src.bandit_ads.database import Arm as DBArm
            
            db_manager = get_db_manager()
            db_arm_id = None
            with db_manager.get_session() as session:
                db_arm = session.query(DBArm).filter(
                    and_(
                        DBArm.platform == arm.platform,
                        DBArm.channel == arm.channel,
                        DBArm.creative == arm.creative
                    )
                ).first()
                if db_arm:
                    db_arm_id = db_arm.id
            
            # Get platform entity IDs from database
            entity_ids = None
            if db_arm_id:
                entity_ids = get_arm_platform_entity_ids(db_arm_id)
            
            ad_set_id = None
            ad_id = None
            
            if entity_ids:
                ad_set_id = entity_ids.get('ad_set_id') or entity_ids.get('adset_id')
                ad_id = entity_ids.get('ad_id')
            
            # Try to update ad set bid first (most common)
            if ad_set_id:
                self.logger.info(f"Updating ad set bid for arm {arm} to ${new_bid}")
                ad_set = AdSet(ad_set_id)
                
                # Update bid amount based on bidding strategy
                # Meta uses different fields: bid_amount, cost_per_result, etc.
                # For CPC campaigns, use bid_amount
                update_params = {
                    'bid_amount': int(new_bid * 100)  # Convert to cents
                }
                
                ad_set.update(params=update_params)
                
                # Update bid in database
                if db_arm_id:
                    update_arm_bid(db_arm_id, new_bid)
                
                self.logger.info(f"Successfully updated ad set bid to ${new_bid}")
                return True
            
            # Fall back to ad-level bid update if ad_id is available
            elif ad_id:
                self.logger.info(f"Updating ad bid for arm {arm} to ${new_bid}")
                ad = Ad(ad_id)
                
                # Note: Ad-level bid updates are less common in Meta
                # This may need to be adjusted based on your campaign structure
                update_params = {
                    'bid_amount': int(new_bid * 100)  # Convert to cents
                }
                
                ad.update(params=update_params)
                
                # Update bid in database
                if db_arm_id:
                    update_arm_bid(db_arm_id, new_bid)
                
                self.logger.info(f"Successfully updated ad bid to ${new_bid}")
                return True
            else:
                self.logger.warning(
                    f"Cannot update bid for arm {arm}: missing ad_set_id or ad_id. "
                    f"Set platform_entity_ids in the arm's database record."
                )
                return False
                
        except ImportError:
            self.logger.warning(
                "facebook-business library not installed. Install with: pip install facebook-business"
            )
            return False
        except FacebookRequestError as e:
            self.logger.error(f"Meta API error updating bid: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error updating Meta Ads bid: {str(e)}")
            return False
    
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
    
    def _get_arm_from_db(self, arm: Arm, campaign_id: Optional[int] = None) -> Optional[int]:
        """
        Look up arm in database to get its ID.
        
        Args:
            arm: Arm object
            campaign_id: Optional campaign ID to narrow search
        
        Returns:
            Database arm ID or None if not found
        """
        from src.bandit_ads.database import get_db_manager
        from sqlalchemy import and_
        
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            from src.bandit_ads.database import Arm as DBArm
            
            query = session.query(DBArm).filter(
                and_(
                    DBArm.platform == arm.platform,
                    DBArm.channel == arm.channel,
                    DBArm.creative == arm.creative
                )
            )
            
            if campaign_id:
                query = query.filter(DBArm.campaign_id == campaign_id)
            
            db_arm = query.first()
            return db_arm.id if db_arm else None
    
    def _get_campaign_id(self, arm: Arm, db_arm_id: Optional[int] = None) -> str:
        """
        Map arm to TTD campaign ID.
        
        First tries to get from arm's platform_entity_ids in database,
        then falls back to credentials default.
        """
        # Try to get from database
        arm_id = db_arm_id
        if not arm_id:
            arm_id = self._get_arm_from_db(arm)
        
        if arm_id:
            entity_ids = get_arm_platform_entity_ids(arm_id)
            if entity_ids and 'campaign_id' in entity_ids:
                return str(entity_ids['campaign_id'])
        
        # Fall back to credentials default
        return self.credentials.get('default_campaign_id', '')
    
    def _get_strategy_id(self, arm: Arm, db_arm_id: Optional[int] = None) -> Optional[str]:
        """Get TTD strategy ID from arm's platform_entity_ids."""
        arm_id = db_arm_id
        if not arm_id:
            arm_id = self._get_arm_from_db(arm)
        
        if arm_id:
            entity_ids = get_arm_platform_entity_ids(arm_id)
            if entity_ids and 'strategy_id' in entity_ids:
                return str(entity_ids['strategy_id'])
        return None
    
    def _get_ad_group_id(self, arm: Arm, db_arm_id: Optional[int] = None) -> Optional[str]:
        """Get TTD ad group ID from arm's platform_entity_ids."""
        arm_id = db_arm_id
        if not arm_id:
            arm_id = self._get_arm_from_db(arm)
        
        if arm_id:
            entity_ids = get_arm_platform_entity_ids(arm_id)
            if entity_ids and 'ad_group_id' in entity_ids:
                return str(entity_ids['ad_group_id'])
        return None
    
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
            # Look up arm in database to get campaign ID
            db_arm_id = self._get_arm_from_db(arm)
            campaign_id = self._get_campaign_id(arm, db_arm_id)
            
            if not campaign_id:
                self.logger.warning(f"No campaign ID found for arm {arm}")
                return self._empty_metrics()
            
            # The Trade Desk API endpoint for reporting
            url = "https://api.thetradedesk.com/v3/myquery/report"
            
            # Build query parameters
            params = {
                'AdvertiserId': self.advertiser_id,
                'StartDate': start_date.strftime('%Y-%m-%d'),
                'EndDate': end_date.strftime('%Y-%m-%d'),
                'GroupBy': ['CampaignId'],
                'Metrics': ['Impressions', 'Clicks', 'Conversions', 'Spend', 'Revenue'],
                'Filter': {
                    'CampaignId': campaign_id
                }
            }
            
            response = self.session.post(url, json=params)
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse TTD report response
                # TTD returns data in a structured format
                total_impressions = 0
                total_clicks = 0
                total_conversions = 0
                total_cost = 0.0
                total_revenue = 0.0
                
                # Handle different response formats
                if isinstance(data, dict):
                    # Check if response has ReportData array
                    report_data = data.get('ReportData', [])
                    if report_data:
                        for row in report_data:
                            total_impressions += int(row.get('Impressions', 0))
                            total_clicks += int(row.get('Clicks', 0))
                            total_conversions += int(row.get('Conversions', 0))
                            total_cost += float(row.get('Spend', 0.0))
                            total_revenue += float(row.get('Revenue', 0.0))
                    else:
                        # Fallback to top-level keys
                        total_impressions = int(data.get('Impressions', 0))
                        total_clicks = int(data.get('Clicks', 0))
                        total_conversions = int(data.get('Conversions', 0))
                        total_cost = float(data.get('Spend', 0.0))
                        total_revenue = float(data.get('Revenue', 0.0))
                elif isinstance(data, list):
                    # Handle array response
                    for row in data:
                        total_impressions += int(row.get('Impressions', 0))
                        total_clicks += int(row.get('Clicks', 0))
                        total_conversions += int(row.get('Conversions', 0))
                        total_cost += float(row.get('Spend', 0.0))
                        total_revenue += float(row.get('Revenue', 0.0))
                
                roas = total_revenue / total_cost if total_cost > 0 else 0.0
                
                return {
                    'impressions': total_impressions,
                    'clicks': total_clicks,
                    'conversions': total_conversions,
                    'cost': total_cost,
                    'revenue': total_revenue,
                    'roas': roas,
                    'source': 'trade_desk',
                    'timestamp': datetime.now().isoformat()
                }
            else:
                self.logger.error(f"The Trade Desk API error: {response.status_code} - {response.text}")
                return self._empty_metrics()
                
        except Exception as e:
            self.logger.error(f"Error fetching The Trade Desk metrics: {str(e)}")
            return self._empty_metrics()
    
    @retry_on_failure(max_retries=3)
    def update_bid(self, arm: Arm, new_bid: float) -> bool:
        """
        Update bid in The Trade Desk.
        
        Updates the bid for a strategy or ad group based on arm's platform_entity_ids.
        """
        if not self.session:
            self.logger.error("Not authenticated. Call authenticate() first.")
            return False
        
        self._rate_limit()
        
        try:
            import requests
            
            # Look up arm in database first
            db_arm_id = self._get_arm_from_db(arm)
            
            # Get platform entity IDs
            strategy_id = self._get_strategy_id(arm, db_arm_id)
            ad_group_id = self._get_ad_group_id(arm, db_arm_id)
            campaign_id = self._get_campaign_id(arm, db_arm_id)
            
            if strategy_id:
                # Update strategy bid (preferred method)
                self.logger.info(f"Updating strategy bid for arm {arm} to ${new_bid}")
                
                url = f"https://api.thetradedesk.com/v3/strategy/{strategy_id}"
                
                # Get current strategy to preserve other settings
                get_response = self.session.get(url)
                if get_response.status_code != 200:
                    self.logger.error(f"Failed to get strategy: {get_response.text}")
                    return False
                
                strategy_data = get_response.json()
                
                # Update bid amount (convert dollars to micros for TTD)
                # TTD uses micros (1/1,000,000 of currency unit)
                strategy_data['BidAmountInMicros'] = int(new_bid * 1_000_000)
                
                # Update strategy
                update_response = self.session.put(url, json=strategy_data)
                
                if update_response.status_code == 200:
                    # Update bid in database
                    if db_arm_id:
                        update_arm_bid(db_arm_id, new_bid)
                    
                    self.logger.info(f"Successfully updated strategy bid to ${new_bid}")
                    return True
                else:
                    self.logger.error(f"Failed to update strategy bid: {update_response.text}")
                    return False
                    
            elif ad_group_id:
                # Update ad group bid (fallback)
                self.logger.info(f"Updating ad group bid for arm {arm} to ${new_bid}")
                
                url = f"https://api.thetradedesk.com/v3/adgroup/{ad_group_id}"
                
                # Get current ad group
                get_response = self.session.get(url)
                if get_response.status_code != 200:
                    self.logger.error(f"Failed to get ad group: {get_response.text}")
                    return False
                
                ad_group_data = get_response.json()
                
                # Update bid amount
                ad_group_data['BidAmountInMicros'] = int(new_bid * 1_000_000)
                
                # Update ad group
                update_response = self.session.put(url, json=ad_group_data)
                
                if update_response.status_code == 200:
                    # Update bid in database
                    if db_arm_id:
                        update_arm_bid(db_arm_id, new_bid)
                    
                    self.logger.info(f"Successfully updated ad group bid to ${new_bid}")
                    return True
                else:
                    self.logger.error(f"Failed to update ad group bid: {update_response.text}")
                    return False
            else:
                self.logger.warning(
                    f"Cannot update bid for arm {arm}: missing strategy_id or ad_group_id. "
                    f"Set platform_entity_ids in the arm's database record."
                )
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating The Trade Desk bid: {str(e)}")
            return False
    
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
