"""
Incrementality Testing Module

Provides functionality for measuring true incremental lift from advertising:
- HoldoutArm: Virtual arm for tracking organic conversions without ad spend
- Incrementality calculations: Lift percent, incremental CVR, iROAS
- Statistical significance testing
"""

import math
import random
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

from src.bandit_ads.utils import get_logger

logger = get_logger('incrementality')


@dataclass
class HoldoutArm:
    """
    Virtual arm that tracks organic conversions without ad spend.
    
    Used as a control group to measure true incrementality of advertising.
    Reserves a percentage of the audience to receive no ads.
    """
    
    holdout_percentage: float = 0.10  # 10% default holdout
    
    # Organic metrics (no ad exposure)
    organic_users: int = 0
    organic_conversions: int = 0
    organic_revenue: float = 0.0
    
    # Tracking data
    daily_metrics: Dict[str, Dict] = field(default_factory=dict)
    start_date: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize tracking."""
        self.start_date = datetime.now()
        self.daily_metrics = {}
    
    def record_organic(
        self, 
        users: int, 
        conversions: int, 
        revenue: float,
        date: Optional[datetime] = None
    ):
        """
        Record organic conversions in holdout period.
        
        Args:
            users: Number of users in holdout (no ad exposure)
            conversions: Number of conversions from holdout users
            revenue: Revenue from holdout users
            date: Date of the metrics (defaults to today)
        """
        self.organic_users += users
        self.organic_conversions += conversions
        self.organic_revenue += revenue
        
        # Track daily for time series analysis
        date_key = (date or datetime.now()).strftime('%Y-%m-%d')
        if date_key not in self.daily_metrics:
            self.daily_metrics[date_key] = {
                'users': 0,
                'conversions': 0,
                'revenue': 0.0
            }
        
        self.daily_metrics[date_key]['users'] += users
        self.daily_metrics[date_key]['conversions'] += conversions
        self.daily_metrics[date_key]['revenue'] += revenue
        
        logger.debug(f"Recorded organic: {users} users, {conversions} conversions, ${revenue:.2f} revenue")
    
    def get_baseline_cvr(self) -> float:
        """
        Get baseline conversion rate from holdout group.
        
        Returns:
            Organic conversion rate (conversions / users)
        """
        if self.organic_users == 0:
            return 0.0
        return self.organic_conversions / self.organic_users
    
    def get_baseline_revenue_per_user(self) -> float:
        """
        Get baseline revenue per user from holdout group.
        
        Returns:
            Organic revenue per user
        """
        if self.organic_users == 0:
            return 0.0
        return self.organic_revenue / self.organic_users
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all holdout metrics."""
        return {
            'holdout_percentage': self.holdout_percentage,
            'organic_users': self.organic_users,
            'organic_conversions': self.organic_conversions,
            'organic_revenue': self.organic_revenue,
            'baseline_cvr': self.get_baseline_cvr(),
            'baseline_revenue_per_user': self.get_baseline_revenue_per_user(),
            'days_running': (datetime.now() - self.start_date).days if self.start_date else 0
        }
    
    def reset(self):
        """Reset holdout metrics for a new experiment."""
        self.organic_users = 0
        self.organic_conversions = 0
        self.organic_revenue = 0.0
        self.daily_metrics = {}
        self.start_date = datetime.now()
    
    def __str__(self):
        """String representation for use as arm key."""
        return f"HoldoutArm(holdout={self.holdout_percentage:.0%})"


def calculate_incrementality(
    treatment_cvr: float,
    control_cvr: float,
    treatment_users: Optional[int] = None,
    control_users: Optional[int] = None,
    treatment_conversions: Optional[int] = None,
    control_conversions: Optional[int] = None
) -> Dict[str, Any]:
    """
    Calculate incremental lift from treatment vs control.
    
    Args:
        treatment_cvr: Conversion rate for treatment group (saw ads)
        control_cvr: Conversion rate for control group (no ads)
        treatment_users: Number of users in treatment (optional, for CI)
        control_users: Number of users in control (optional, for CI)
        treatment_conversions: Conversions in treatment (optional, for CI)
        control_conversions: Conversions in control (optional, for CI)
    
    Returns:
        Dictionary with:
        - lift_percent: How much better treatment performed (%)
        - incremental_cvr: True incremental conversion rate
        - relative_lift: Lift as a ratio
        - confidence_interval: 95% CI if sample sizes provided
        - is_significant: Whether lift is statistically significant
    """
    # Handle edge cases
    if control_cvr == 0:
        if treatment_cvr == 0:
            return {
                'lift_percent': 0.0,
                'incremental_cvr': 0.0,
                'relative_lift': 1.0,
                'confidence_interval': None,
                'is_significant': False,
                'p_value': 1.0
            }
        else:
            return {
                'lift_percent': float('inf'),
                'incremental_cvr': treatment_cvr,
                'relative_lift': float('inf'),
                'confidence_interval': None,
                'is_significant': True,
                'p_value': 0.0
            }
    
    # Calculate lift metrics
    lift_percent = (treatment_cvr - control_cvr) / control_cvr * 100
    incremental_cvr = treatment_cvr - control_cvr
    relative_lift = treatment_cvr / control_cvr
    
    result = {
        'lift_percent': lift_percent,
        'incremental_cvr': incremental_cvr,
        'relative_lift': relative_lift,
        'confidence_interval': None,
        'is_significant': False,
        'p_value': None
    }
    
    # Calculate confidence interval if sample sizes provided
    if all(v is not None for v in [treatment_users, control_users]):
        ci_result = _calculate_confidence_interval(
            treatment_cvr, control_cvr,
            treatment_users, control_users,
            treatment_conversions, control_conversions
        )
        result.update(ci_result)
    
    return result


def _calculate_confidence_interval(
    treatment_cvr: float,
    control_cvr: float,
    treatment_users: int,
    control_users: int,
    treatment_conversions: Optional[int] = None,
    control_conversions: Optional[int] = None,
    confidence_level: float = 0.95
) -> Dict[str, Any]:
    """
    Calculate confidence interval for lift using normal approximation.
    
    Uses the delta method for ratio of proportions.
    """
    # Standard errors for each proportion
    se_treatment = math.sqrt(treatment_cvr * (1 - treatment_cvr) / treatment_users) if treatment_users > 0 else 0
    se_control = math.sqrt(control_cvr * (1 - control_cvr) / control_users) if control_users > 0 else 0
    
    # Standard error of the difference
    se_diff = math.sqrt(se_treatment**2 + se_control**2)
    
    # Z-score for confidence level
    z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
    z = z_scores.get(confidence_level, 1.96)
    
    # Confidence interval for absolute difference
    diff = treatment_cvr - control_cvr
    ci_lower_abs = diff - z * se_diff
    ci_upper_abs = diff + z * se_diff
    
    # Convert to percentage lift CI
    if control_cvr > 0:
        ci_lower_pct = (ci_lower_abs / control_cvr) * 100
        ci_upper_pct = (ci_upper_abs / control_cvr) * 100
    else:
        ci_lower_pct = 0
        ci_upper_pct = 0
    
    # Statistical significance (CI doesn't cross 0)
    is_significant = ci_lower_abs > 0 or ci_upper_abs < 0
    
    # Calculate p-value using z-test
    if se_diff > 0:
        z_stat = diff / se_diff
        # Two-tailed p-value
        p_value = 2 * (1 - _norm_cdf(abs(z_stat)))
    else:
        p_value = 1.0 if diff == 0 else 0.0
    
    return {
        'confidence_interval': (ci_lower_pct, ci_upper_pct),
        'confidence_interval_absolute': (ci_lower_abs, ci_upper_abs),
        'is_significant': is_significant,
        'p_value': p_value,
        'standard_error': se_diff
    }


def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def calculate_incremental_roas(
    treatment_revenue: float,
    control_revenue: float,
    treatment_spend: float,
    treatment_users: int,
    control_users: int
) -> Dict[str, Any]:
    """
    Calculate incremental ROAS (iROAS).
    
    iROAS measures the true return on ad spend by comparing:
    - Revenue from treatment group vs control group
    - Normalized by the number of users in each group
    
    Args:
        treatment_revenue: Total revenue from treatment group
        control_revenue: Total revenue from control group
        treatment_spend: Total ad spend on treatment group
        treatment_users: Number of users in treatment
        control_users: Number of users in control
    
    Returns:
        Dictionary with iROAS and supporting metrics
    """
    if treatment_spend == 0:
        return {
            'incremental_roas': 0.0,
            'observed_roas': 0.0,
            'incremental_revenue': 0.0,
            'roas_inflation': 0.0
        }
    
    # Calculate revenue per user for each group
    treatment_rpu = treatment_revenue / treatment_users if treatment_users > 0 else 0
    control_rpu = control_revenue / control_users if control_users > 0 else 0
    
    # Incremental revenue per user (what ads actually added)
    incremental_rpu = treatment_rpu - control_rpu
    
    # Scale to treatment group size
    incremental_revenue = incremental_rpu * treatment_users
    
    # Incremental ROAS
    incremental_roas = incremental_revenue / treatment_spend
    
    # Observed (attributed) ROAS for comparison
    observed_roas = treatment_revenue / treatment_spend
    
    # ROAS inflation (how much we're overestimating)
    roas_inflation = (observed_roas / incremental_roas - 1) * 100 if incremental_roas > 0 else 0
    
    return {
        'incremental_roas': incremental_roas,
        'observed_roas': observed_roas,
        'incremental_revenue': incremental_revenue,
        'treatment_revenue': treatment_revenue,
        'control_revenue_normalized': control_rpu * treatment_users,
        'roas_inflation': roas_inflation,
        'treatment_rpu': treatment_rpu,
        'control_rpu': control_rpu
    }


def run_permutation_test(
    treatment_conversions: int,
    treatment_users: int,
    control_conversions: int,
    control_users: int,
    num_permutations: int = 10000
) -> Dict[str, Any]:
    """
    Run permutation test for statistical significance.
    
    More robust than normal approximation for small sample sizes.
    
    Args:
        treatment_conversions: Number of conversions in treatment
        treatment_users: Number of users in treatment
        control_conversions: Number of conversions in control
        control_users: Number of users in control
        num_permutations: Number of permutations to run
    
    Returns:
        Dictionary with p-value and confidence interval
    """
    # Observed difference
    treatment_cvr = treatment_conversions / treatment_users if treatment_users > 0 else 0
    control_cvr = control_conversions / control_users if control_users > 0 else 0
    observed_diff = treatment_cvr - control_cvr
    
    # Pool all conversions
    total_conversions = treatment_conversions + control_conversions
    total_users = treatment_users + control_users
    
    # Create pooled population (1 = conversion, 0 = no conversion)
    population = [1] * total_conversions + [0] * (total_users - total_conversions)
    
    # Run permutations
    permuted_diffs = []
    for _ in range(num_permutations):
        random.shuffle(population)
        
        # Split into treatment and control
        perm_treatment = population[:treatment_users]
        perm_control = population[treatment_users:]
        
        # Calculate permuted difference
        perm_treatment_cvr = sum(perm_treatment) / len(perm_treatment) if perm_treatment else 0
        perm_control_cvr = sum(perm_control) / len(perm_control) if perm_control else 0
        permuted_diffs.append(perm_treatment_cvr - perm_control_cvr)
    
    # Calculate p-value (two-tailed)
    extreme_count = sum(1 for d in permuted_diffs if abs(d) >= abs(observed_diff))
    p_value = extreme_count / num_permutations
    
    # Calculate confidence interval from permutation distribution
    permuted_diffs.sort()
    ci_lower_idx = int(0.025 * num_permutations)
    ci_upper_idx = int(0.975 * num_permutations)
    
    # Shift to be centered on observed difference
    ci_lower = observed_diff - (permuted_diffs[ci_upper_idx] - 0)
    ci_upper = observed_diff - (permuted_diffs[ci_lower_idx] - 0)
    
    return {
        'p_value': p_value,
        'confidence_interval': (ci_lower * 100 / control_cvr if control_cvr > 0 else 0,
                               ci_upper * 100 / control_cvr if control_cvr > 0 else 0),
        'is_significant': p_value < 0.05,
        'observed_difference': observed_diff,
        'num_permutations': num_permutations
    }


@dataclass
class IncrementalityResult:
    """Container for incrementality test results."""
    
    experiment_id: int
    campaign_id: int
    experiment_type: str  # 'holdout', 'geo_lift', 'platform_native'
    
    # Core metrics
    lift_percent: float
    incremental_cvr: float
    incremental_roas: float
    observed_roas: float
    
    # Statistical measures
    confidence_interval: Tuple[float, float]
    p_value: float
    is_significant: bool
    
    # Sample sizes
    treatment_users: int
    control_users: int
    treatment_conversions: int
    control_conversions: int
    
    # Revenue
    treatment_revenue: float
    control_revenue: float
    treatment_spend: float
    incremental_revenue: float
    
    # Metadata
    start_date: datetime
    end_date: datetime
    days_running: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'experiment_id': self.experiment_id,
            'campaign_id': self.campaign_id,
            'experiment_type': self.experiment_type,
            'lift_percent': self.lift_percent,
            'incremental_cvr': self.incremental_cvr,
            'incremental_roas': self.incremental_roas,
            'observed_roas': self.observed_roas,
            'confidence_interval_lower': self.confidence_interval[0],
            'confidence_interval_upper': self.confidence_interval[1],
            'p_value': self.p_value,
            'is_significant': self.is_significant,
            'treatment_users': self.treatment_users,
            'control_users': self.control_users,
            'treatment_conversions': self.treatment_conversions,
            'control_conversions': self.control_conversions,
            'treatment_revenue': self.treatment_revenue,
            'control_revenue': self.control_revenue,
            'treatment_spend': self.treatment_spend,
            'incremental_revenue': self.incremental_revenue,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'days_running': self.days_running
        }


def calculate_sample_size(
    baseline_cvr: float,
    minimum_detectable_effect: float,
    power: float = 0.80,
    significance_level: float = 0.05
) -> Dict[str, int]:
    """
    Calculate required sample size for an incrementality test.
    
    Args:
        baseline_cvr: Expected baseline conversion rate
        minimum_detectable_effect: Minimum lift to detect (e.g., 0.10 for 10%)
        power: Statistical power (default 80%)
        significance_level: Alpha level (default 5%)
    
    Returns:
        Dictionary with required users per group
    """
    # Z-scores
    z_alpha = 1.96 if significance_level == 0.05 else 2.576 if significance_level == 0.01 else 1.645
    z_beta = 0.84 if power == 0.80 else 1.28 if power == 0.90 else 0.52
    
    # Expected treatment CVR
    treatment_cvr = baseline_cvr * (1 + minimum_detectable_effect)
    
    # Pooled variance
    pooled_cvr = (baseline_cvr + treatment_cvr) / 2
    pooled_var = pooled_cvr * (1 - pooled_cvr)
    
    # Effect size
    effect = treatment_cvr - baseline_cvr
    
    # Sample size per group
    if effect == 0:
        n_per_group = float('inf')
    else:
        n_per_group = 2 * ((z_alpha + z_beta) ** 2) * pooled_var / (effect ** 2)
    
    n_per_group = int(math.ceil(n_per_group))
    
    return {
        'users_per_group': n_per_group,
        'total_users': n_per_group * 2,
        'treatment_users': n_per_group,
        'control_users': n_per_group,
        'expected_treatment_cvr': treatment_cvr,
        'expected_control_cvr': baseline_cvr,
        'minimum_detectable_effect': minimum_detectable_effect,
        'power': power,
        'significance_level': significance_level
    }
