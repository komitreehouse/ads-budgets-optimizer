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

    def set_campaign_budget(self, arm: Arm, new_budget: float, dry_run: bool = False) -> bool:
        """
        Push a new daily budget to the platform for this arm's campaign.

        Args:
            arm: Arm object with platform entity IDs
            new_budget: New daily budget in dollars
            dry_run: If True, log the change without making API calls

        Returns:
            True if successful (or if dry_run)
        """
        if dry_run:
            self.logger.info(f"[DRY RUN] Would set budget ${new_budget:.2f} for arm {arm}")
            return True
        self.logger.warning(f"set_campaign_budget not implemented for {self.__class__.__name__}")
        return False


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

    @retry_on_failure(max_retries=3)
    def set_campaign_budget(self, arm: Arm, new_budget: float, dry_run: bool = False) -> bool:
        """
        Set daily budget for a Google Ads campaign.

        Uses CampaignBudgetService to update the campaign's shared budget resource.
        """
        if dry_run:
            self.logger.info(f"[DRY RUN] Would set Google Ads budget ${new_budget:.2f} for arm {arm}")
            return True

        if not self.client:
            self.logger.error("Not authenticated. Call authenticate() first.")
            return False

        self._rate_limit()

        try:
            from google.ads.googleads.errors import GoogleAdsException

            db_arm_id = self._get_arm_from_db(arm)
            campaign_id = self._get_campaign_id(arm, db_arm_id)

            if not campaign_id:
                self.logger.warning(f"No campaign_id for arm {arm}, cannot set budget")
                return False

            # Query for the campaign's budget resource
            ga_service = self.client.get_service("GoogleAdsService")
            query = (
                f"SELECT campaign.campaign_budget "
                f"FROM campaign "
                f"WHERE campaign.id = {campaign_id}"
            )
            response = ga_service.search(customer_id=self.customer_id, query=query)
            budget_resource = None
            for row in response:
                budget_resource = row.campaign.campaign_budget
                break

            if not budget_resource:
                self.logger.error(f"Could not find budget resource for campaign {campaign_id}")
                return False

            # Update the budget (convert dollars to micros)
            budget_service = self.client.get_service("CampaignBudgetService")
            budget_operation = self.client.get_type("CampaignBudgetOperation")
            budget = budget_operation.update
            budget.resource_name = budget_resource
            budget.amount_micros = int(new_budget * 1_000_000)

            budget_operation.update_mask.CopyFrom(
                self.client.get_type("FieldMask")(paths=["amount_micros"])
            )

            budget_service.mutate_campaign_budgets(
                customer_id=self.customer_id,
                operations=[budget_operation]
            )

            self.logger.info(f"Set Google Ads budget to ${new_budget:.2f} for campaign {campaign_id}")
            return True

        except ImportError:
            self.logger.warning("google-ads library not installed")
            return False
        except Exception as e:
            self.logger.error(f"Error setting Google Ads budget: {e}")
            return False

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
    
    def set_campaign_budget(self, arm: Arm, new_budget: float, dry_run: bool = False) -> bool:
        """
        Set daily budget for a Meta ad set.

        Uses the Marketing API to update the ad set's daily_budget field.
        """
        if dry_run:
            self.logger.info(f"[DRY RUN] Would set Meta budget ${new_budget:.2f} for arm {arm}")
            return True

        if not self.api:
            self.logger.error("Not authenticated. Call authenticate() first.")
            return False

        self._rate_limit()

        try:
            from facebook_business.adobjects.adset import AdSet
            from facebook_business.exceptions import FacebookRequestError

            # Look up ad set ID from platform_entity_ids
            from src.bandit_ads.database import get_db_manager, Arm as DBArm
            from sqlalchemy import and_

            db_manager = get_db_manager()
            ad_set_id = None
            with db_manager.get_session() as session:
                db_arm = session.query(DBArm).filter(
                    and_(
                        DBArm.platform == arm.platform,
                        DBArm.channel == arm.channel,
                        DBArm.creative == arm.creative
                    )
                ).first()
                if db_arm:
                    entity_ids = get_arm_platform_entity_ids(db_arm.id)
                    if entity_ids:
                        ad_set_id = entity_ids.get('ad_set_id') or entity_ids.get('adset_id')

            if not ad_set_id:
                self.logger.warning(f"No ad_set_id for arm {arm}, cannot set budget")
                return False

            ad_set = AdSet(ad_set_id)
            # Meta daily_budget is in cents
            ad_set.update(params={'daily_budget': int(new_budget * 100)})

            self.logger.info(f"Set Meta budget to ${new_budget:.2f} for ad set {ad_set_id}")
            return True

        except ImportError:
            self.logger.warning("facebook-business library not installed")
            return False
        except Exception as e:
            self.logger.error(f"Error setting Meta budget: {e}")
            return False

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
    
    def set_campaign_budget(self, arm: Arm, new_budget: float, dry_run: bool = False) -> bool:
        """
        Set daily budget for a Trade Desk campaign/flight.

        Uses the TTD campaign update endpoint to set BudgetInImpressions or DailyBudget.
        """
        if dry_run:
            self.logger.info(f"[DRY RUN] Would set TTD budget ${new_budget:.2f} for arm {arm}")
            return True

        if not self.session:
            self.logger.error("Not authenticated. Call authenticate() first.")
            return False

        self._rate_limit()

        try:
            db_arm_id = self._get_arm_from_db(arm)
            entity_ids = None
            if db_arm_id:
                entity_ids = get_arm_platform_entity_ids(db_arm_id)

            campaign_id = entity_ids.get('campaign_id') if entity_ids else None
            if not campaign_id:
                self.logger.warning(f"No campaign_id for arm {arm}, cannot set budget")
                return False

            # Get current campaign to preserve settings
            url = f"https://api.thetradedesk.com/v3/campaign/{campaign_id}"
            get_response = self.session.get(url)
            if get_response.status_code != 200:
                self.logger.error(f"Failed to get TTD campaign: {get_response.text}")
                return False

            campaign_data = get_response.json()
            # TTD uses DailyBudgetInMicros
            campaign_data['Budget']['DailyBudgetInMicros'] = int(new_budget * 1_000_000)

            update_response = self.session.put(url, json=campaign_data)
            if update_response.status_code == 200:
                self.logger.info(f"Set TTD budget to ${new_budget:.2f} for campaign {campaign_id}")
                return True
            else:
                self.logger.error(f"Failed to set TTD budget: {update_response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Error setting TTD budget: {e}")
            return False

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


# ---- Budget Push Dispatcher ----

# Cached connector instances
_connectors: Dict[str, BaseAPIConnector] = {}


def get_platform_connector(platform: str, credentials: Optional[Dict[str, Any]] = None) -> Optional[BaseAPIConnector]:
    """Get or create a connector for the given platform."""
    platform_lower = platform.lower()
    if platform_lower in _connectors:
        return _connectors[platform_lower]

    if not credentials:
        # Try loading from config
        try:
            from src.bandit_ads.utils import ConfigManager
            config = ConfigManager()
            credentials = config.get(f'api_credentials.{platform_lower}', {})
        except Exception:
            return None

    connector = None
    if platform_lower in ('google', 'google ads'):
        connector = GoogleAdsConnector(credentials)
    elif platform_lower in ('meta', 'facebook', 'meta ads'):
        connector = MetaAdsConnector(credentials)
    elif platform_lower in ('the trade desk', 'ttd', 'trade desk'):
        connector = TradeDeskConnector(credentials)

    if connector:
        _connectors[platform_lower] = connector
    return connector


def push_budget_to_platform(
    arm: Arm,
    new_budget: float,
    dry_run: bool = False,
    credentials: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Push a budget change to the appropriate ad platform.

    Dispatches to the correct connector based on the arm's platform.

    Args:
        arm: Arm object (platform field determines which connector to use)
        new_budget: New daily budget in dollars
        dry_run: If True, log the change without making API calls
        credentials: Optional platform credentials

    Returns:
        True if successful
    """
    logger = get_logger('budget_push')
    connector = get_platform_connector(arm.platform, credentials)
    if not connector:
        logger.warning(f"No connector available for platform '{arm.platform}'")
        return False

    return connector.set_campaign_budget(arm, new_budget, dry_run=dry_run)


class IncrementalityConnector:
    """
    Connector for platform-native incrementality studies.
    
    Supports:
    - Meta Conversion Lift studies
    - Google Conversion Lift reports
    - The Trade Desk Ghost Bid experiments
    """
    
    def __init__(
        self,
        google_connector: Optional[GoogleAdsConnector] = None,
        meta_connector: Optional[MetaAdsConnector] = None,
        ttd_connector: Optional[TradeDeskConnector] = None
    ):
        """
        Initialize with platform connectors.
        
        Args:
            google_connector: Authenticated Google Ads connector
            meta_connector: Authenticated Meta Ads connector
            ttd_connector: Authenticated Trade Desk connector
        """
        self.google = google_connector
        self.meta = meta_connector
        self.ttd = ttd_connector
        self.logger = get_logger('api.IncrementalityConnector')
    
    # ========== Meta Conversion Lift ==========
    
    def create_meta_conversion_lift_study(
        self,
        campaign_id: str,
        name: str,
        holdout_percentage: float = 0.10,
        objective: str = 'CONVERSIONS',
        duration_days: int = 28
    ) -> Optional[Dict[str, Any]]:
        """
        Create a Meta Conversion Lift study.
        
        Uses Meta's native lift measurement API to create holdout experiments.
        
        Args:
            campaign_id: Meta campaign ID to measure
            name: Study name
            holdout_percentage: Percentage to holdout (default 10%)
            objective: Optimization objective
            duration_days: Study duration
        
        Returns:
            Study configuration or None if failed
        """
        if not self.meta or not self.meta.api:
            self.logger.error("Meta connector not available")
            return None
        
        try:
            from facebook_business.adobjects.adaccount import AdAccount
            from facebook_business.adobjects.adliftstudy import AdLiftStudy
            
            account = AdAccount(f"act_{self.meta.ad_account_id}")
            
            # Create lift study
            study_params = {
                'name': name,
                'description': f'Incrementality study for campaign {campaign_id}',
                'cells': [
                    {
                        'name': 'Treatment',
                        'treatment_percentage': int((1 - holdout_percentage) * 100),
                        'control_percentage': int(holdout_percentage * 100),
                        'campaigns': [campaign_id]
                    }
                ],
                'objectives': [objective],
                'start_time': int(datetime.now().timestamp()),
                'end_time': int((datetime.now() + timedelta(days=duration_days)).timestamp())
            }
            
            study = account.create_ad_lift_study(params=study_params)
            
            self.logger.info(f"Created Meta Conversion Lift study: {study.get('id')}")
            
            return {
                'platform': 'meta',
                'study_id': study.get('id'),
                'name': name,
                'campaign_id': campaign_id,
                'holdout_percentage': holdout_percentage,
                'status': 'created'
            }
            
        except ImportError:
            self.logger.warning("facebook-business library not installed")
            return None
        except Exception as e:
            self.logger.error(f"Failed to create Meta lift study: {str(e)}")
            return None
    
    def get_meta_conversion_lift_results(
        self,
        study_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get results from a Meta Conversion Lift study.
        
        Args:
            study_id: Meta lift study ID
        
        Returns:
            Study results including lift metrics
        """
        if not self.meta or not self.meta.api:
            self.logger.error("Meta connector not available")
            return None
        
        try:
            from facebook_business.adobjects.adliftstudy import AdLiftStudy
            
            study = AdLiftStudy(study_id)
            fields = [
                'name',
                'status',
                'cells',
                'lift',
                'confidence_level'
            ]
            
            study_data = study.api_get(fields=fields)
            
            # Parse results
            lift_data = study_data.get('lift', {})
            
            return {
                'platform': 'meta',
                'study_id': study_id,
                'name': study_data.get('name'),
                'status': study_data.get('status'),
                'lift_percent': lift_data.get('value'),
                'confidence_interval': (
                    lift_data.get('lower_bound'),
                    lift_data.get('upper_bound')
                ),
                'confidence_level': study_data.get('confidence_level'),
                'is_significant': lift_data.get('is_statistically_significant', False),
                'treatment_conversions': lift_data.get('treatment_conversions'),
                'control_conversions': lift_data.get('control_conversions'),
                'incremental_conversions': lift_data.get('incremental_conversions')
            }
            
        except ImportError:
            self.logger.warning("facebook-business library not installed")
            return None
        except Exception as e:
            self.logger.error(f"Failed to get Meta lift results: {str(e)}")
            return None
    
    # ========== Google Conversion Lift ==========
    
    def create_google_conversion_lift_experiment(
        self,
        campaign_id: str,
        name: str,
        holdout_percentage: float = 0.10,
        duration_days: int = 28
    ) -> Optional[Dict[str, Any]]:
        """
        Create a Google Ads Conversion Lift experiment.
        
        Uses Google's Experiments API to set up brand lift/conversion lift studies.
        
        Args:
            campaign_id: Google Ads campaign ID
            name: Experiment name
            holdout_percentage: Control group percentage
            duration_days: Experiment duration
        
        Returns:
            Experiment configuration or None if failed
        """
        if not self.google or not self.google.client:
            self.logger.error("Google Ads connector not available")
            return None
        
        try:
            from google.ads.googleads.errors import GoogleAdsException
            
            # Get services
            experiment_service = self.google.client.get_service("ExperimentService")
            campaign_experiment_service = self.google.client.get_service("CampaignExperimentService")
            
            # Create experiment
            experiment = self.google.client.get_type("Experiment")
            experiment.name = name
            experiment.description = f"Incrementality lift study for campaign {campaign_id}"
            experiment.type_ = self.google.client.enums.ExperimentTypeEnum.CONVERSION_LIFT
            
            # Set traffic split
            experiment.goals.append(
                self.google.client.get_type("ExperimentGoal")(
                    conversion_goal_metric_type=self.google.client.enums.ConversionGoalMetricTypeEnum.CONVERSIONS
                )
            )
            
            # Create operation
            operation = self.google.client.get_type("ExperimentOperation")
            operation.create = experiment
            
            response = experiment_service.mutate_experiments(
                customer_id=self.google.customer_id,
                operations=[operation]
            )
            
            experiment_resource = response.results[0].resource_name
            
            self.logger.info(f"Created Google Conversion Lift experiment: {experiment_resource}")
            
            return {
                'platform': 'google',
                'experiment_resource': experiment_resource,
                'name': name,
                'campaign_id': campaign_id,
                'holdout_percentage': holdout_percentage,
                'status': 'created'
            }
            
        except ImportError:
            self.logger.warning("google-ads library not installed")
            return None
        except Exception as e:
            self.logger.error(f"Failed to create Google lift experiment: {str(e)}")
            return None
    
    def get_google_conversion_lift_results(
        self,
        experiment_resource: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get results from a Google Conversion Lift experiment.
        
        Args:
            experiment_resource: Google Ads experiment resource name
        
        Returns:
            Experiment results including lift metrics
        """
        if not self.google or not self.google.client:
            self.logger.error("Google Ads connector not available")
            return None
        
        try:
            # Query experiment results using GAQL
            query = f"""
                SELECT
                    experiment.name,
                    experiment.status,
                    metrics.conversions,
                    metrics.conversions_value,
                    metrics.cost_micros
                FROM experiment
                WHERE experiment.resource_name = '{experiment_resource}'
            """
            
            response = self.google.client.get_service("GoogleAdsService").search(
                customer_id=self.google.customer_id,
                query=query
            )
            
            results = []
            for row in response:
                results.append({
                    'name': row.experiment.name,
                    'status': row.experiment.status.name,
                    'conversions': row.metrics.conversions,
                    'revenue': row.metrics.conversions_value,
                    'cost': row.metrics.cost_micros / 1_000_000
                })
            
            if results:
                result = results[0]
                return {
                    'platform': 'google',
                    'experiment_resource': experiment_resource,
                    'name': result['name'],
                    'status': result['status'],
                    'conversions': result['conversions'],
                    'revenue': result['revenue'],
                    'cost': result['cost'],
                    'roas': result['revenue'] / result['cost'] if result['cost'] > 0 else 0
                }
            
            return None
            
        except ImportError:
            self.logger.warning("google-ads library not installed")
            return None
        except Exception as e:
            self.logger.error(f"Failed to get Google lift results: {str(e)}")
            return None
    
    # ========== The Trade Desk Ghost Bids ==========
    
    def create_ttd_ghost_bid_experiment(
        self,
        campaign_id: str,
        name: str,
        ghost_bid_percentage: float = 0.10,
        duration_days: int = 28
    ) -> Optional[Dict[str, Any]]:
        """
        Create a Trade Desk Ghost Bid experiment.
        
        Ghost bids are fake bids that track what would have happened without ads.
        They participate in the auction but don't actually win/serve impressions.
        
        Args:
            campaign_id: TTD campaign ID
            name: Experiment name
            ghost_bid_percentage: Percentage of bids to ghost
            duration_days: Experiment duration
        
        Returns:
            Experiment configuration or None if failed
        """
        if not self.ttd or not self.ttd.session:
            self.logger.error("Trade Desk connector not available")
            return None
        
        try:
            # TTD Ghost Bid API endpoint
            url = "https://api.thetradedesk.com/v3/experiment/ghostbid"
            
            experiment_config = {
                'AdvertiserId': self.ttd.advertiser_id,
                'CampaignId': campaign_id,
                'Name': name,
                'Description': f'Incrementality experiment for campaign {campaign_id}',
                'GhostBidPercentage': ghost_bid_percentage * 100,  # API expects percentage
                'StartDate': datetime.now().isoformat(),
                'EndDate': (datetime.now() + timedelta(days=duration_days)).isoformat(),
                'Status': 'Active'
            }
            
            response = self.ttd.session.post(url, json=experiment_config)
            
            if response.status_code == 200:
                result = response.json()
                
                self.logger.info(f"Created TTD Ghost Bid experiment: {result.get('ExperimentId')}")
                
                return {
                    'platform': 'ttd',
                    'experiment_id': result.get('ExperimentId'),
                    'name': name,
                    'campaign_id': campaign_id,
                    'ghost_bid_percentage': ghost_bid_percentage,
                    'status': 'created'
                }
            else:
                self.logger.error(f"TTD API error: {response.status_code} - {response.text}")
                return None
            
        except Exception as e:
            self.logger.error(f"Failed to create TTD ghost bid experiment: {str(e)}")
            return None
    
    def get_ttd_ghost_bid_results(
        self,
        experiment_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get results from a Trade Desk Ghost Bid experiment.
        
        Args:
            experiment_id: TTD experiment ID
        
        Returns:
            Experiment results including incrementality metrics
        """
        if not self.ttd or not self.ttd.session:
            self.logger.error("Trade Desk connector not available")
            return None
        
        try:
            # TTD Ghost Bid results endpoint
            url = f"https://api.thetradedesk.com/v3/experiment/ghostbid/{experiment_id}/results"
            
            response = self.ttd.session.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse results
                treatment = data.get('TreatmentMetrics', {})
                control = data.get('ControlMetrics', {})  # Ghost bid group
                
                treatment_conversions = treatment.get('Conversions', 0)
                control_conversions = control.get('Conversions', 0)
                treatment_revenue = treatment.get('Revenue', 0)
                control_revenue = control.get('Revenue', 0)
                treatment_users = treatment.get('Users', 0)
                control_users = control.get('Users', 0)
                treatment_spend = treatment.get('Spend', 0)
                
                # Calculate lift
                treatment_cvr = treatment_conversions / treatment_users if treatment_users > 0 else 0
                control_cvr = control_conversions / control_users if control_users > 0 else 0
                
                if control_cvr > 0:
                    lift_percent = (treatment_cvr - control_cvr) / control_cvr * 100
                else:
                    lift_percent = 0 if treatment_cvr == 0 else float('inf')
                
                # Calculate iROAS
                if treatment_spend > 0:
                    # Scale control revenue to treatment population size
                    scale_factor = treatment_users / control_users if control_users > 0 else 1
                    expected_organic_revenue = control_revenue * scale_factor
                    incremental_revenue = treatment_revenue - expected_organic_revenue
                    incremental_roas = incremental_revenue / treatment_spend
                    observed_roas = treatment_revenue / treatment_spend
                else:
                    incremental_roas = 0
                    observed_roas = 0
                    incremental_revenue = 0
                
                return {
                    'platform': 'ttd',
                    'experiment_id': experiment_id,
                    'status': data.get('Status', 'unknown'),
                    'lift_percent': lift_percent,
                    'incremental_roas': incremental_roas,
                    'observed_roas': observed_roas,
                    'incremental_revenue': incremental_revenue,
                    'treatment_conversions': treatment_conversions,
                    'control_conversions': control_conversions,
                    'treatment_revenue': treatment_revenue,
                    'control_revenue': control_revenue,
                    'treatment_users': treatment_users,
                    'control_users': control_users,
                    'treatment_spend': treatment_spend,
                    'confidence_interval': data.get('ConfidenceInterval'),
                    'p_value': data.get('PValue'),
                    'is_significant': data.get('IsSignificant', False)
                }
            else:
                self.logger.error(f"TTD API error: {response.status_code} - {response.text}")
                return None
            
        except Exception as e:
            self.logger.error(f"Failed to get TTD ghost bid results: {str(e)}")
            return None
    
    # ========== Unified Interface ==========
    
    def create_incrementality_study(
        self,
        platform: str,
        campaign_id: str,
        name: str,
        holdout_percentage: float = 0.10,
        duration_days: int = 28,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Create an incrementality study on the specified platform.
        
        Unified interface for all platforms.
        
        Args:
            platform: 'google', 'meta', or 'ttd'
            campaign_id: Platform-specific campaign ID
            name: Study name
            holdout_percentage: Control group percentage
            duration_days: Study duration
            **kwargs: Platform-specific parameters
        
        Returns:
            Study configuration or None if failed
        """
        platform = platform.lower()
        
        if platform in ['meta', 'facebook']:
            return self.create_meta_conversion_lift_study(
                campaign_id, name, holdout_percentage, 
                kwargs.get('objective', 'CONVERSIONS'), duration_days
            )
        elif platform in ['google', 'google_ads']:
            return self.create_google_conversion_lift_experiment(
                campaign_id, name, holdout_percentage, duration_days
            )
        elif platform in ['ttd', 'trade_desk', 'the_trade_desk']:
            return self.create_ttd_ghost_bid_experiment(
                campaign_id, name, holdout_percentage, duration_days
            )
        else:
            self.logger.error(f"Unsupported platform: {platform}")
            return None
    
    def get_incrementality_results(
        self,
        platform: str,
        study_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get incrementality study results from the specified platform.
        
        Args:
            platform: 'google', 'meta', or 'ttd'
            study_id: Platform-specific study/experiment ID
        
        Returns:
            Study results or None if failed
        """
        platform = platform.lower()
        
        if platform in ['meta', 'facebook']:
            return self.get_meta_conversion_lift_results(study_id)
        elif platform in ['google', 'google_ads']:
            return self.get_google_conversion_lift_results(study_id)
        elif platform in ['ttd', 'trade_desk', 'the_trade_desk']:
            return self.get_ttd_ghost_bid_results(study_id)
        else:
            self.logger.error(f"Unsupported platform: {platform}")
            return None


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
