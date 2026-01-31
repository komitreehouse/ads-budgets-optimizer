"""
Data collection service for orchestrating data pulls from multiple APIs.

Coordinates API calls across platforms, handles rate limiting, aggregates metrics,
and stores data in the database.
"""

import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.bandit_ads.api_connectors import BaseAPIConnector, create_api_connector
from src.bandit_ads.arms import Arm
from src.bandit_ads.database import get_db_manager
from src.bandit_ads.db_helpers import (
    get_campaign, get_arms_by_campaign, get_arm_by_attributes,
    create_metric, log_api_call
)
from src.bandit_ads.models import MetricCreate
from src.bandit_ads.utils import get_logger, retry_on_failure

logger = get_logger('data_collector')


class DataCollector:
    """Orchestrates data collection from multiple advertising platforms."""
    
    def __init__(self, api_connectors: Optional[Dict[str, BaseAPIConnector]] = None,
                 max_workers: int = 5):
        """
        Initialize data collector.
        
        Args:
            api_connectors: Dictionary of platform -> API connector
            max_workers: Maximum number of parallel API calls
        """
        self.api_connectors = api_connectors or {}
        self.max_workers = max_workers
        logger.info(f"Data collector initialized with {len(self.api_connectors)} connectors")
    
    def add_connector(self, platform: str, connector: BaseAPIConnector):
        """Add an API connector."""
        self.api_connectors[platform.lower()] = connector
        logger.info(f"Added connector for platform: {platform}")
    
    def collect_campaign_metrics(self, campaign_id: int,
                                start_date: Optional[datetime] = None,
                                end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Collect metrics for all arms in a campaign.
        
        Args:
            campaign_id: Campaign ID
            start_date: Start date for metrics (default: last 24 hours)
            end_date: End date for metrics (default: now)
        
        Returns:
            Dictionary with collection results
        """
        if end_date is None:
            end_date = datetime.utcnow()
        if start_date is None:
            start_date = end_date - timedelta(hours=24)
        
        campaign = get_campaign(campaign_id)
        if not campaign:
            logger.error(f"Campaign not found: {campaign_id}")
            return {'success': False, 'error': 'Campaign not found'}
        
        arms = get_arms_by_campaign(campaign_id)
        if not arms:
            logger.warning(f"No arms found for campaign {campaign_id}")
            return {'success': True, 'metrics_collected': 0, 'arms_processed': 0}
        
        logger.info(f"Collecting metrics for campaign {campaign.name} ({len(arms)} arms)")
        
        # Group arms by platform
        arms_by_platform: Dict[str, List[Arm]] = {}
        for arm in arms:
            platform = arm.platform.lower()
            if platform not in arms_by_platform:
                arms_by_platform[platform] = []
            arms_by_platform[platform].append(arm)
        
        # Collect metrics in parallel
        results = {
            'success': True,
            'metrics_collected': 0,
            'arms_processed': 0,
            'errors': [],
            'platforms': {}
        }
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            for platform, platform_arms in arms_by_platform.items():
                if platform in self.api_connectors:
                    future = executor.submit(
                        self._collect_platform_metrics,
                        platform, platform_arms, campaign_id, start_date, end_date
                    )
                    futures.append((platform, future))
                else:
                    logger.warning(f"No connector found for platform: {platform}")
                    results['errors'].append(f"No connector for platform: {platform}")
            
            # Wait for all collections to complete
            for platform, future in futures:
                try:
                    platform_result = future.result(timeout=300)  # 5 minute timeout
                    results['platforms'][platform] = platform_result
                    results['metrics_collected'] += platform_result.get('metrics_collected', 0)
                    results['arms_processed'] += platform_result.get('arms_processed', 0)
                    if platform_result.get('errors'):
                        results['errors'].extend(platform_result['errors'])
                except Exception as e:
                    logger.error(f"Error collecting metrics for {platform}: {str(e)}")
                    results['errors'].append(f"{platform}: {str(e)}")
                    results['success'] = False
        
        logger.info(f"Collection complete: {results['metrics_collected']} metrics collected")
        return results
    
    @retry_on_failure(max_retries=2, delay=1.0)
    def _collect_platform_metrics(self, platform: str, arms: List[Arm],
                                  campaign_id: int, start_date: datetime,
                                  end_date: datetime) -> Dict[str, Any]:
        """Collect metrics for arms from a specific platform."""
        connector = self.api_connectors[platform]
        results = {
            'metrics_collected': 0,
            'arms_processed': 0,
            'errors': []
        }
        
        for arm in arms:
            try:
                # Fetch metrics from API
                api_start = time.time()
                metrics_data = connector.get_campaign_metrics(arm, start_date, end_date)
                api_time = time.time() - api_start
                
                # Log API call
                log_api_call(
                    platform=platform,
                    endpoint='get_campaign_metrics',
                    method='GET',
                    status_code=200 if metrics_data else None,
                    response_time=api_time,
                    success=metrics_data is not None,
                    request_data={'arm': str(arm), 'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()}
                )
                
                if metrics_data:
                    # Store metrics in database
                    metric = create_metric(MetricCreate(
                        campaign_id=campaign_id,
                        arm_id=arm.id,
                        timestamp=end_date,  # Use end_date as timestamp
                        impressions=metrics_data.get('impressions', 0),
                        clicks=metrics_data.get('clicks', 0),
                        conversions=metrics_data.get('conversions', 0),
                        revenue=metrics_data.get('revenue', 0.0),
                        cost=metrics_data.get('cost', 0.0),
                        roas=metrics_data.get('roas'),
                        source='api'
                    ))
                    results['metrics_collected'] += 1
                    logger.debug(f"Collected metrics for {arm}: ROAS={metric.roas:.2f}")
                else:
                    results['errors'].append(f"Failed to fetch metrics for {arm}")
                
                results['arms_processed'] += 1
                
                # Rate limiting
                time.sleep(0.5)  # Small delay between API calls
                
            except Exception as e:
                logger.error(f"Error collecting metrics for {arm}: {str(e)}")
                results['errors'].append(f"{arm}: {str(e)}")
                log_api_call(
                    platform=platform,
                    endpoint='get_campaign_metrics',
                    method='GET',
                    success=False,
                    error_message=str(e),
                    request_data={'arm': str(arm)}
                )
        
        return results
    
    def collect_all_active_campaigns(self) -> Dict[str, Any]:
        """Collect metrics for all active campaigns."""
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            from src.bandit_ads.database import Campaign
            active_campaigns = session.query(Campaign).filter(
                Campaign.status == 'active'
            ).all()
        
        results = {
            'success': True,
            'campaigns_processed': 0,
            'total_metrics_collected': 0,
            'errors': []
        }
        
        for campaign in active_campaigns:
            try:
                campaign_result = self.collect_campaign_metrics(campaign.id)
                results['campaigns_processed'] += 1
                results['total_metrics_collected'] += campaign_result.get('metrics_collected', 0)
                if campaign_result.get('errors'):
                    results['errors'].extend(campaign_result['errors'])
            except Exception as e:
                logger.error(f"Error collecting metrics for campaign {campaign.id}: {str(e)}")
                results['errors'].append(f"Campaign {campaign.id}: {str(e)}")
                results['success'] = False
        
        logger.info(f"Collected metrics for {results['campaigns_processed']} campaigns")
        return results


def create_data_collector_from_config(config: Dict[str, Any]) -> DataCollector:
    """
    Create a data collector from configuration.
    
    Args:
        config: Configuration dictionary with API credentials
    
    Returns:
        DataCollector instance
    """
    connectors = {}
    
    # Google Ads
    if config.get('api', {}).get('google', {}).get('client_id'):
        try:
            google_connector = create_api_connector('google', config['api']['google'])
            if google_connector.authenticate():
                connectors['google'] = google_connector
                logger.info("Google Ads connector initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Google Ads connector: {str(e)}")
    
    # Meta Ads
    if config.get('api', {}).get('meta', {}).get('access_token'):
        try:
            meta_connector = create_api_connector('meta', config['api']['meta'])
            if meta_connector.authenticate():
                connectors['meta'] = meta_connector
                logger.info("Meta Ads connector initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Meta Ads connector: {str(e)}")
    
    # The Trade Desk
    if config.get('api', {}).get('trade_desk', {}).get('username'):
        try:
            ttd_connector = create_api_connector('trade_desk', config['api']['trade_desk'])
            if ttd_connector.authenticate():
                connectors['trade_desk'] = ttd_connector
                logger.info("The Trade Desk connector initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize The Trade Desk connector: {str(e)}")
    
    return DataCollector(api_connectors=connectors)
