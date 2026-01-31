"""
Data validation and quality checks for metrics and campaign data.

Includes anomaly detection, data quality scoring, and validation rules.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

from src.bandit_ads.database import get_db_manager
from src.bandit_ads.db_helpers import get_metrics_by_arm
from src.bandit_ads.models import MetricCreate
from src.bandit_ads.utils import get_logger

logger = get_logger('data_validator')


class DataValidator:
    """Validates data quality and detects anomalies."""
    
    def __init__(self, anomaly_threshold: float = 3.0):
        """
        Initialize data validator.
        
        Args:
            anomaly_threshold: Number of standard deviations for anomaly detection
        """
        self.anomaly_threshold = anomaly_threshold
        logger.info(f"Data validator initialized (anomaly threshold: {anomaly_threshold}σ)")
    
    def validate_metric(self, metric_data: MetricCreate) -> Tuple[bool, List[str]]:
        """
        Validate a metric before storage.
        
        Args:
            metric_data: Metric data to validate
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required fields
        if metric_data.impressions < 0:
            errors.append("Impressions cannot be negative")
        if metric_data.clicks < 0:
            errors.append("Clicks cannot be negative")
        if metric_data.conversions < 0:
            errors.append("Conversions cannot be negative")
        if metric_data.revenue < 0:
            errors.append("Revenue cannot be negative")
        if metric_data.cost < 0:
            errors.append("Cost cannot be negative")
        
        # Check logical constraints
        if metric_data.clicks > metric_data.impressions:
            errors.append("Clicks cannot exceed impressions")
        if metric_data.conversions > metric_data.clicks:
            errors.append("Conversions cannot exceed clicks")
        
        # Check CTR and CVR ranges
        if metric_data.impressions > 0:
            ctr = metric_data.clicks / metric_data.impressions
            if ctr > 1.0:
                errors.append(f"CTR ({ctr:.2%}) exceeds 100%")
            if ctr > 0.5:  # Unusually high CTR
                errors.append(f"CTR ({ctr:.2%}) is unusually high (>50%)")
        
        if metric_data.clicks > 0:
            cvr = metric_data.conversions / metric_data.clicks
            if cvr > 1.0:
                errors.append(f"CVR ({cvr:.2%}) exceeds 100%")
            if cvr > 0.5:  # Unusually high CVR
                errors.append(f"CVR ({cvr:.2%}) is unusually high (>50%)")
        
        # Check ROAS
        if metric_data.cost > 0:
            roas = metric_data.roas if metric_data.roas is not None else (
                metric_data.revenue / metric_data.cost
            )
            if roas < 0:
                errors.append("ROAS cannot be negative")
            if roas > 100:  # Unusually high ROAS
                errors.append(f"ROAS ({roas:.2f}) is unusually high (>100)")
        
        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning(f"Metric validation failed: {', '.join(errors)}")
        
        return is_valid, errors
    
    def detect_anomalies(self, arm_id: int, new_metric: MetricCreate,
                        lookback_days: int = 7) -> List[Dict[str, Any]]:
        """
        Detect anomalies in new metric compared to historical data.
        
        Args:
            arm_id: Arm ID
            new_metric: New metric to check
            lookback_days: Number of days to look back for comparison
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Get historical metrics
        start_date = datetime.utcnow() - timedelta(days=lookback_days)
        historical_metrics = get_metrics_by_arm(arm_id, start_date=start_date)
        
        if len(historical_metrics) < 3:
            # Not enough data for anomaly detection
            return anomalies
        
        # Calculate historical statistics
        historical_roas = [m.roas for m in historical_metrics if m.cost > 0]
        historical_ctr = [m.ctr for m in historical_metrics if m.impressions > 0]
        historical_cvr = [m.cvr for m in historical_metrics if m.clicks > 0]
        
        # Check ROAS anomaly
        if historical_roas and new_metric.cost > 0:
            new_roas = new_metric.roas if new_metric.roas else (
                new_metric.revenue / new_metric.cost
            )
            mean_roas = statistics.mean(historical_roas)
            stdev_roas = statistics.stdev(historical_roas) if len(historical_roas) > 1 else 0
            
            if stdev_roas > 0:
                z_score = abs((new_roas - mean_roas) / stdev_roas)
                if z_score > self.anomaly_threshold:
                    anomalies.append({
                        'type': 'roas_anomaly',
                        'metric': 'ROAS',
                        'value': new_roas,
                        'expected_range': f"{mean_roas - self.anomaly_threshold * stdev_roas:.2f} - {mean_roas + self.anomaly_threshold * stdev_roas:.2f}",
                        'z_score': z_score,
                        'severity': 'high' if z_score > 4 else 'medium'
                    })
        
        # Check CTR anomaly
        if historical_ctr and new_metric.impressions > 0:
            new_ctr = new_metric.clicks / new_metric.impressions
            mean_ctr = statistics.mean(historical_ctr)
            stdev_ctr = statistics.stdev(historical_ctr) if len(historical_ctr) > 1 else 0
            
            if stdev_ctr > 0:
                z_score = abs((new_ctr - mean_ctr) / stdev_ctr)
                if z_score > self.anomaly_threshold:
                    anomalies.append({
                        'type': 'ctr_anomaly',
                        'metric': 'CTR',
                        'value': new_ctr,
                        'expected_range': f"{mean_ctr - self.anomaly_threshold * stdev_ctr:.4f} - {mean_ctr + self.anomaly_threshold * stdev_ctr:.4f}",
                        'z_score': z_score,
                        'severity': 'high' if z_score > 4 else 'medium'
                    })
        
        # Check CVR anomaly
        if historical_cvr and new_metric.clicks > 0:
            new_cvr = new_metric.conversions / new_metric.clicks
            mean_cvr = statistics.mean(historical_cvr)
            stdev_cvr = statistics.stdev(historical_cvr) if len(historical_cvr) > 1 else 0
            
            if stdev_cvr > 0:
                z_score = abs((new_cvr - mean_cvr) / stdev_cvr)
                if z_score > self.anomaly_threshold:
                    anomalies.append({
                        'type': 'cvr_anomaly',
                        'metric': 'CVR',
                        'value': new_cvr,
                        'expected_range': f"{mean_cvr - self.anomaly_threshold * stdev_cvr:.4f} - {mean_cvr + self.anomaly_threshold * stdev_cvr:.4f}",
                        'z_score': z_score,
                        'severity': 'high' if z_score > 4 else 'medium'
                    })
        
        if anomalies:
            logger.warning(f"Detected {len(anomalies)} anomalies for arm {arm_id}")
        
        return anomalies
    
    def calculate_data_quality_score(self, arm_id: int,
                                     lookback_days: int = 7) -> Dict[str, Any]:
        """
        Calculate data quality score for an arm.
        
        Args:
            arm_id: Arm ID
            lookback_days: Number of days to analyze
        
        Returns:
            Dictionary with quality scores
        """
        start_date = datetime.utcnow() - timedelta(days=lookback_days)
        metrics = get_metrics_by_arm(arm_id, start_date=start_date)
        
        if not metrics:
            return {
                'arm_id': arm_id,
                'completeness': 0.0,
                'timeliness': 0.0,
                'consistency': 0.0,
                'overall_score': 0.0
            }
        
        # Completeness: percentage of expected data points
        expected_points = lookback_days * 24  # Assuming hourly data
        actual_points = len(metrics)
        completeness = min(1.0, actual_points / expected_points) if expected_points > 0 else 1.0
        
        # Timeliness: how recent is the data
        if metrics:
            latest_metric = max(metrics, key=lambda m: m.timestamp)
            hours_since_update = (datetime.utcnow() - latest_metric.timestamp).total_seconds() / 3600
            timeliness = max(0.0, 1.0 - (hours_since_update / 24))  # Decay over 24 hours
        else:
            timeliness = 0.0
        
        # Consistency: variance in metrics
        if len(metrics) > 1:
            roas_values = [m.roas for m in metrics if m.cost > 0]
            if roas_values:
                roas_variance = statistics.variance(roas_values) if len(roas_values) > 1 else 0
                roas_mean = statistics.mean(roas_values)
                # Lower variance = higher consistency
                consistency = max(0.0, 1.0 - (roas_variance / (roas_mean ** 2 + 1)))
            else:
                consistency = 0.5
        else:
            consistency = 0.5
        
        overall_score = (completeness * 0.4 + timeliness * 0.3 + consistency * 0.3)
        
        return {
            'arm_id': arm_id,
            'completeness': completeness,
            'timeliness': timeliness,
            'consistency': consistency,
            'overall_score': overall_score,
            'data_points': actual_points,
            'expected_points': expected_points
        }


def validate_and_clean_metric(metric_data: MetricCreate,
                              validator: Optional[DataValidator] = None) -> Tuple[bool, MetricCreate, List[str]]:
    """
    Validate and clean a metric.
    
    Args:
        metric_data: Metric to validate
        validator: Optional validator instance
    
    Returns:
        Tuple of (is_valid, cleaned_metric, warnings)
    """
    if validator is None:
        validator = DataValidator()
    
    warnings = []
    
    # Validate
    is_valid, errors = validator.validate_metric(metric_data)
    
    if not is_valid:
        return False, metric_data, errors
    
    # Clean data (normalize, handle edge cases)
    cleaned = metric_data.copy() if hasattr(metric_data, 'copy') else metric_data
    
    # Ensure ROAS is calculated
    if cleaned.roas is None and cleaned.cost > 0:
        cleaned.roas = cleaned.revenue / cleaned.cost
    
    # Check for suspicious values (warnings, not errors)
    if cleaned.impressions > 0:
        ctr = cleaned.clicks / cleaned.impressions
        if ctr > 0.3:  # Very high CTR
            warnings.append(f"Unusually high CTR: {ctr:.2%}")
    
    if cleaned.clicks > 0:
        cvr = cleaned.conversions / cleaned.clicks
        if cvr > 0.3:  # Very high CVR
            warnings.append(f"Unusually high CVR: {cvr:.2%}")
    
    return True, cleaned, warnings
