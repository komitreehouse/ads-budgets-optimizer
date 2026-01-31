"""
ETL (Extract, Transform, Load) pipeline for MMM analysis.

Extracts data from database, transforms for MMM modeling, calculates derived metrics,
and updates MMM coefficients.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

from src.bandit_ads.database import get_db_manager
from src.bandit_ads.db_helpers import (
    get_metrics_by_arm, get_aggregated_metrics, get_arms_by_campaign
)
from src.bandit_ads.data_loader import MMMDataLoader
from src.bandit_ads.utils import get_logger

logger = get_logger('etl')


class ETLPipeline:
    """ETL pipeline for MMM data processing."""
    
    def __init__(self, lookback_days: int = 30):
        """
        Initialize ETL pipeline.
        
        Args:
            lookback_days: Number of days to look back for data extraction
        """
        self.lookback_days = lookback_days
        self.data_loader = MMMDataLoader()
        logger.info(f"ETL pipeline initialized (lookback: {lookback_days} days)")
    
    def extract_campaign_data(self, campaign_id: int,
                             start_date: Optional[datetime] = None,
                             end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Extract campaign data from database.
        
        Args:
            campaign_id: Campaign ID
            start_date: Start date (default: lookback_days ago)
            end_date: End date (default: now)
        
        Returns:
            Dictionary with extracted data
        """
        if end_date is None:
            end_date = datetime.utcnow()
        if start_date is None:
            start_date = end_date - timedelta(days=self.lookback_days)
        
        arms = get_arms_by_campaign(campaign_id)
        if not arms:
            logger.warning(f"No arms found for campaign {campaign_id}")
            return {'arms': [], 'metrics': {}}
        
        extracted_data = {
            'campaign_id': campaign_id,
            'start_date': start_date,
            'end_date': end_date,
            'arms': [],
            'metrics': {}
        }
        
        for arm in arms:
            arm_data = {
                'id': arm.id,
                'platform': arm.platform,
                'channel': arm.channel,
                'creative': arm.creative,
                'bid': arm.bid
            }
            extracted_data['arms'].append(arm_data)
            
            # Get metrics for this arm
            metrics = get_metrics_by_arm(arm.id, start_date=start_date, end_date=end_date)
            extracted_data['metrics'][arm.id] = [
                {
                    'timestamp': m.timestamp,
                    'impressions': m.impressions,
                    'clicks': m.clicks,
                    'conversions': m.conversions,
                    'revenue': m.revenue,
                    'cost': m.cost,
                    'roas': m.roas,
                    'ctr': m.ctr,
                    'cvr': m.cvr
                }
                for m in metrics
            ]
        
        logger.info(f"Extracted data for {len(arms)} arms, {sum(len(m) for m in extracted_data['metrics'].values())} metrics")
        return extracted_data
    
    def transform_for_mmm(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform data for MMM analysis.
        
        Args:
            extracted_data: Data from extract step
        
        Returns:
            Transformed data with MMM features
        """
        transformed = {
            'campaign_id': extracted_data['campaign_id'],
            'start_date': extracted_data['start_date'],
            'end_date': extracted_data['end_date'],
            'arm_aggregates': {},
            'time_series': [],
            'mmm_features': {}
        }
        
        # Aggregate by arm
        for arm_data in extracted_data['arms']:
            arm_id = arm_data['id']
            metrics = extracted_data['metrics'].get(arm_id, [])
            
            if not metrics:
                continue
            
            # Calculate aggregated metrics
            total_impressions = sum(m['impressions'] for m in metrics)
            total_clicks = sum(m['clicks'] for m in metrics)
            total_conversions = sum(m['conversions'] for m in metrics)
            total_revenue = sum(m['revenue'] for m in metrics)
            total_cost = sum(m['cost'] for m in metrics)
            
            avg_roas = statistics.mean([m['roas'] for m in metrics if m['cost'] > 0]) if any(m['cost'] > 0 for m in metrics) else 0.0
            avg_ctr = statistics.mean([m['ctr'] for m in metrics if m['impressions'] > 0]) if any(m['impressions'] > 0 for m in metrics) else 0.0
            avg_cvr = statistics.mean([m['cvr'] for m in metrics if m['clicks'] > 0]) if any(m['clicks'] > 0 for m in metrics) else 0.0
            
            # Calculate variance
            roas_values = [m['roas'] for m in metrics if m['cost'] > 0]
            roas_variance = statistics.variance(roas_values) if len(roas_values) > 1 else 0.0
            
            ctr_values = [m['ctr'] for m in metrics if m['impressions'] > 0]
            ctr_variance = statistics.variance(ctr_values) if len(ctr_values) > 1 else 0.0
            
            cvr_values = [m['cvr'] for m in metrics if m['clicks'] > 0]
            cvr_variance = statistics.variance(cvr_values) if len(cvr_values) > 1 else 0.0
            
            transformed['arm_aggregates'][arm_id] = {
                'platform': arm_data['platform'],
                'channel': arm_data['channel'],
                'creative': arm_data['creative'],
                'bid': arm_data['bid'],
                'total_impressions': total_impressions,
                'total_clicks': total_clicks,
                'total_conversions': total_conversions,
                'total_revenue': total_revenue,
                'total_cost': total_cost,
                'avg_roas': avg_roas,
                'avg_ctr': avg_ctr,
                'avg_cvr': avg_cvr,
                'roas_variance': roas_variance,
                'ctr_variance': ctr_variance,
                'cvr_variance': cvr_variance,
                'data_points': len(metrics)
            }
        
        # Create time series data
        all_timestamps = set()
        for metrics in extracted_data['metrics'].values():
            all_timestamps.update(m['timestamp'] for m in metrics)
        
        for timestamp in sorted(all_timestamps):
            time_point = {
                'timestamp': timestamp,
                'arms': {}
            }
            
            for arm_data in extracted_data['arms']:
                arm_id = arm_data['id']
                metrics = extracted_data['metrics'].get(arm_id, [])
                
                # Find metric for this timestamp (or closest)
                matching_metrics = [m for m in metrics if abs((m['timestamp'] - timestamp).total_seconds()) < 3600]
                if matching_metrics:
                    m = matching_metrics[0]  # Use first match
                    time_point['arms'][arm_id] = {
                        'impressions': m['impressions'],
                        'clicks': m['clicks'],
                        'conversions': m['conversions'],
                        'revenue': m['revenue'],
                        'cost': m['cost'],
                        'roas': m['roas']
                    }
            
            transformed['time_series'].append(time_point)
        
        # Calculate MMM features
        transformed['mmm_features'] = self._calculate_mmm_features(transformed)
        
        logger.info(f"Transformed data: {len(transformed['arm_aggregates'])} arms, {len(transformed['time_series'])} time points")
        return transformed
    
    def _calculate_mmm_features(self, transformed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate MMM-specific features."""
        features = {
            'seasonality': {},
            'trends': {},
            'carryover_effects': {},
            'competitive_effects': {}
        }
        
        # Seasonality: Group by quarter
        for arm_id, arm_data in transformed_data['arm_aggregates'].items():
            # Determine quarter from start_date
            start_date = transformed_data['start_date']
            quarter = (start_date.month - 1) // 3 + 1
            quarter_key = f'Q{quarter}'
            
            if quarter_key not in features['seasonality']:
                features['seasonality'][quarter_key] = {}
            
            channel = arm_data['channel']
            if channel not in features['seasonality'][quarter_key]:
                features['seasonality'][quarter_key][channel] = {
                    'total_revenue': 0.0,
                    'total_cost': 0.0,
                    'count': 0
                }
            
            features['seasonality'][quarter_key][channel]['total_revenue'] += arm_data['total_revenue']
            features['seasonality'][quarter_key][channel]['total_cost'] += arm_data['total_cost']
            features['seasonality'][quarter_key][channel]['count'] += 1
        
        # Calculate seasonal multipliers
        for quarter, channels in features['seasonality'].items():
            for channel, data in channels.items():
                if data['total_cost'] > 0:
                    avg_roas = data['total_revenue'] / data['total_cost']
                    # Normalize to baseline (assume Q2 is baseline = 1.0)
                    baseline_roas = 1.0  # This would come from historical data
                    features['seasonality'][quarter][channel]['multiplier'] = avg_roas / baseline_roas if baseline_roas > 0 else 1.0
        
        # Trends: Calculate trend direction
        for arm_id, arm_data in transformed_data['arm_aggregates'].items():
            # Simple trend: compare first half vs second half
            time_series = transformed_data['time_series']
            if len(time_series) > 1:
                midpoint = len(time_series) // 2
                first_half = time_series[:midpoint]
                second_half = time_series[midpoint:]
                
                first_half_roas = statistics.mean([
                    point['arms'][arm_id]['roas']
                    for point in first_half
                    if arm_id in point['arms'] and point['arms'][arm_id].get('cost', 0) > 0
                ]) if any(arm_id in point['arms'] for point in first_half) else 0.0
                
                second_half_roas = statistics.mean([
                    point['arms'][arm_id]['roas']
                    for point in second_half
                    if arm_id in point['arms'] and point['arms'][arm_id].get('cost', 0) > 0
                ]) if any(arm_id in point['arms'] for point in second_half) else 0.0
                
                if first_half_roas > 0:
                    trend = (second_half_roas - first_half_roas) / first_half_roas
                    features['trends'][arm_id] = {
                        'direction': 'up' if trend > 0.1 else 'down' if trend < -0.1 else 'stable',
                        'magnitude': abs(trend)
                    }
        
        return features
    
    def load_mmm_coefficients(self, transformed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load/update MMM coefficients from transformed data.
        
        Args:
            transformed_data: Transformed data from transform step
        
        Returns:
            Dictionary with updated MMM coefficients
        """
        mmm_data = {
            'historical_performance': {},
            'seasonal_multipliers': transformed_data['mmm_features'].get('seasonality', {})
        }
        
        # Create historical performance data
        for arm_id, arm_data in transformed_data['arm_aggregates'].items():
            key = f"{arm_data['platform']}_{arm_data['channel']}_{arm_data['creative']}_{arm_data['bid']}"
            
            mmm_data['historical_performance'][key] = {
                'historical_ctr': arm_data['avg_ctr'],
                'historical_cvr': arm_data['avg_cvr'],
                'historical_roas': arm_data['avg_roas'],
                'spend_baseline': arm_data['total_cost'],
                'variance_ctr': arm_data['ctr_variance'],
                'variance_cvr': arm_data['cvr_variance'],
                'impressions': arm_data['total_impressions'],
                'clicks': arm_data['total_clicks'],
                'conversions': arm_data['total_conversions'],
                'revenue': arm_data['total_revenue'],
                'cost': arm_data['total_cost']
            }
        
        # Load into data loader
        self.data_loader.load_historical_data(data_dict=mmm_data)
        
        logger.info(f"Loaded MMM coefficients for {len(mmm_data['historical_performance'])} arm combinations")
        return mmm_data
    
    def run_etl_pipeline(self, campaign_id: int) -> Dict[str, Any]:
        """
        Run complete ETL pipeline for a campaign.
        
        Args:
            campaign_id: Campaign ID
        
        Returns:
            Dictionary with ETL results
        """
        logger.info(f"Starting ETL pipeline for campaign {campaign_id}")
        
        try:
            # Extract
            extracted = self.extract_campaign_data(campaign_id)
            
            if not extracted['arms']:
                return {'success': False, 'error': 'No arms found'}
            
            # Transform
            transformed = self.transform_for_mmm(extracted)
            
            # Load
            mmm_coefficients = self.load_mmm_coefficients(transformed)
            
            result = {
                'success': True,
                'campaign_id': campaign_id,
                'arms_processed': len(transformed['arm_aggregates']),
                'metrics_processed': sum(len(extracted['metrics'][aid]) for aid in extracted['metrics']),
                'time_points': len(transformed['time_series']),
                'mmm_coefficients_updated': len(mmm_coefficients['historical_performance']),
                'mmm_features': transformed['mmm_features']
            }
            
            logger.info(f"ETL pipeline completed successfully for campaign {campaign_id}")
            return result
            
        except Exception as e:
            logger.error(f"ETL pipeline failed for campaign {campaign_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def run_etl_for_all_campaigns(self) -> Dict[str, Any]:
        """Run ETL pipeline for all active campaigns."""
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            from src.bandit_ads.database import Campaign
            active_campaigns = session.query(Campaign).filter(
                Campaign.status == 'active'
            ).all()
        
        results = {
            'success': True,
            'campaigns_processed': 0,
            'total_arms': 0,
            'total_metrics': 0,
            'errors': []
        }
        
        for campaign in active_campaigns:
            try:
                result = self.run_etl_pipeline(campaign.id)
                if result.get('success'):
                    results['campaigns_processed'] += 1
                    results['total_arms'] += result.get('arms_processed', 0)
                    results['total_metrics'] += result.get('metrics_processed', 0)
                else:
                    results['errors'].append(f"Campaign {campaign.id}: {result.get('error')}")
                    results['success'] = False
            except Exception as e:
                logger.error(f"Error in ETL for campaign {campaign.id}: {str(e)}")
                results['errors'].append(f"Campaign {campaign.id}: {str(e)}")
                results['success'] = False
        
        logger.info(f"ETL completed for {results['campaigns_processed']} campaigns")
        return results
