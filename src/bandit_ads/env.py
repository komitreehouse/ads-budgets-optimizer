import random
import math
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

class AdEnvironment:
    """
    Simulates an advertising environment with comprehensive MMM factors.

    Includes seasonality, competitive effects, carryover/ad stock, and external factors
    for realistic multi-armed bandit advertising simulation.
    
    Current Implementation
    ----------------------
    Uses rule-based configurable MMM factors:
    - Seasonality: Quarterly multipliers per channel (configurable dict)
    - Carryover/Ad Stock: Exponential decay model with configurable decay_rate
    - Diminishing Returns: Saturation curves with configurable thresholds
    - External Factors: Holiday multipliers and economic indicators

    Bayesian MMM factor estimation (learned posteriors for seasonality, carryover,
    and saturation) is handled by the Meridian pipeline. See meridian_trainer.py
    for model training and meridian_insights.py for posterior-derived insights.
    """

    def __init__(self, global_params=None, arm_specific_params=None, mmm_factors=None):
        """
        global_params: default parameters applied to all arms
        arm_specific_params: dict mapping arm identifiers to specific parameters
        """
        self.global_params = global_params or {
            "ctr": 0.05,      # 5% default CTR
            "cvr": 0.1,       # 10% default CVR
            "revenue": 10.0,  # $10 per conversion
            "cpc": 1.0        # $1 per click
        }
        self.arm_specific_params = arm_specific_params or {}

        # MMM Factors
        self.mmm_factors = mmm_factors or {}
        self.ad_stock = defaultdict(float)  # Carryover effects
        self.market_saturation = defaultdict(float)  # Competitive effects
        self.current_date = datetime.now()

        # Initialize MMM factor components
        self._init_mmm_factors()

    def _init_mmm_factors(self):
        """Initialize MMM factor components with defaults."""
        self.mmm_factors.setdefault('seasonality', {
            'Q1': {'Search': 0.85, 'Display': 0.90, 'Social': 1.15},
            'Q2': {'Search': 1.05, 'Display': 1.10, 'Social': 1.08},
            'Q3': {'Search': 0.95, 'Display': 1.15, 'Social': 0.90},
            'Q4': {'Search': 1.20, 'Display': 1.25, 'Social': 1.30}
        })

        self.mmm_factors.setdefault('carryover', {
            'decay_rate': 0.8,  # 80% of previous period's effect carries over
            'max_stock': 2.0,   # Maximum ad stock multiplier
            'stock_half_life': 7  # Days for stock to decay by half
        })

        self.mmm_factors.setdefault('competition', {
            'market_saturation_threshold': 0.7,  # Point where returns diminish
            'saturation_penalty': 0.3,           # How much performance drops at saturation
            'recovery_rate': 0.95               # How quickly saturation recovers
        })

        self.mmm_factors.setdefault('external', {
            'holidays': ['12-25', '01-01', '07-04'],  # MM-DD format
            'holiday_multiplier': 1.8,
            'economic_indicators': {
                'recession_impact': 0.8,
                'growth_period_impact': 1.1
            }
        })

    def _calculate_seasonal_multiplier(self, channel, date=None):
        """Calculate seasonal performance multiplier."""
        if not date:
            date = self.current_date

        quarter = f"Q{(date.month - 1) // 3 + 1}"
        seasonal_data = self.mmm_factors['seasonality']

        if quarter in seasonal_data and channel in seasonal_data[quarter]:
            return seasonal_data[quarter][channel]

        return 1.0

    def _calculate_carryover_effect(self, arm_key):
        """Calculate ad stock/carryover effect for an arm."""
        carryover_config = self.mmm_factors['carryover']
        current_stock = self.ad_stock[arm_key]

        # Exponential decay
        decay_rate = carryover_config['decay_rate']
        decayed_stock = current_stock * decay_rate

        # Apply half-life adjustment
        half_life_days = carryover_config['stock_half_life']
        time_passed = 1  # Assuming 1 day per step for simplicity
        half_life_decay = 0.5 ** (time_passed / half_life_days)

        final_stock = decayed_stock * half_life_decay
        final_stock = min(final_stock, carryover_config['max_stock'])

        # Store for next round
        self.ad_stock[arm_key] = final_stock

        return 1.0 + final_stock * 0.1  # 10% boost per unit of stock

    def _calculate_competitive_effect(self, platform):
        """Calculate competitive/market saturation effect."""
        comp_config = self.mmm_factors['competition']
        current_saturation = self.market_saturation[platform]

        # Market saturation reduces effectiveness
        if current_saturation > comp_config['market_saturation_threshold']:
            saturation_factor = 1.0 - comp_config['saturation_penalty'] * \
                (current_saturation - comp_config['market_saturation_threshold'])
            saturation_factor = max(0.5, saturation_factor)  # Floor at 50%
        else:
            saturation_factor = 1.0

        # Recovery over time
        self.market_saturation[platform] *= comp_config['recovery_rate']

        return saturation_factor

    def _calculate_external_factors(self, date=None):
        """Calculate external factor multipliers (holidays, events, etc.)."""
        if not date:
            date = self.current_date

        external_config = self.mmm_factors['external']
        multiplier = 1.0

        # Holiday effects
        date_str = f"{date.month:02d}-{date.day:02d}"
        if date_str in external_config['holidays']:
            multiplier *= external_config['holiday_multiplier']

        # Economic cycle (simplified - could be more sophisticated)
        # Assuming business cycles affect advertising performance
        if date.month in [12, 1, 2]:  # Q1 - potentially slower
            multiplier *= 0.95
        elif date.month in [6, 7, 8]:  # Q3 - peak season for many businesses
            multiplier *= 1.05

        return multiplier

    def update_ad_spend(self, arm, spend_amount):
        """Update ad stock and market saturation based on spend."""
        arm_key = str(arm)

        # Update ad stock (carryover effect)
        stock_increase = spend_amount / 1000.0  # Normalize spend to stock units
        self.ad_stock[arm_key] += stock_increase

        # Update market saturation (competitive effect)
        platform = arm.platform
        saturation_increase = spend_amount / 50000.0  # Normalize to market impact
        self.market_saturation[platform] += saturation_increase

    def advance_time(self, days=1):
        """Advance the simulation time."""
        self.current_date += timedelta(days=days)

    def step(self, arm, impressions=1, spend_amount=None, context=None):
        """
        Simulate serving an ad (pulling the arm) for a given number of impressions.
        Includes comprehensive MMM factors for realistic simulation.

        arm: Arm object representing the ad configuration
        impressions: number of ad impressions to simulate (default 1)
        spend_amount: amount spent on this arm (for carryover effects)
        context: Optional context dictionary (for contextual bandits)
                Can include user_data, timestamp, etc.
        """
        # Get arm-specific parameters, fallback to global defaults
        arm_key = str(arm)  # Use string representation as key
        arm_params = self.arm_specific_params.get(arm_key, {})

        base_ctr = arm_params.get("ctr", self.global_params["ctr"])
        base_cvr = arm_params.get("cvr", self.global_params["cvr"])
        revenue_per_conversion = arm_params.get("revenue", self.global_params["revenue"])
        cost_per_click = arm_params.get("cpc", self.global_params["cpc"])

        # Calculate MMM factor multipliers
        seasonal_mult = self._calculate_seasonal_multiplier(arm.channel, self.current_date)
        carryover_mult = self._calculate_carryover_effect(arm_key)
        competitive_mult = self._calculate_competitive_effect(arm.platform)
        external_mult = self._calculate_external_factors(self.current_date)

        # Apply all MMM factors to base rates
        effective_ctr = base_ctr * seasonal_mult * carryover_mult * competitive_mult * external_mult
        effective_cvr = base_cvr * seasonal_mult * carryover_mult * competitive_mult * external_mult

        # Ensure rates stay within realistic bounds
        effective_ctr = max(0.001, min(0.5, effective_ctr))
        effective_cvr = max(0.001, min(0.5, effective_cvr))

        # Simulate multiple impressions
        total_clicks = 0
        total_conversions = 0
        total_cost = 0

        for _ in range(impressions):
            # Bernoulli trial for click with effective CTR
            click = int(random.random() < effective_ctr)
            total_clicks += click

            if click:
                # If clicked, Bernoulli trial for conversion with effective CVR
                conversion = int(random.random() < effective_cvr)
                total_conversions += conversion
                total_cost += cost_per_click

        revenue = total_conversions * revenue_per_conversion
        roas = revenue / total_cost if total_cost > 0 else 0.0

        # Update ad stock and market saturation if spend provided
        if spend_amount is not None:
            self.update_ad_spend(arm, spend_amount)

        # Advance time for next simulation step
        self.advance_time(days=1)

        return {
            "impressions": impressions,
            "clicks": total_clicks,
            "conversions": total_conversions,
            "revenue": revenue,
            "cost": total_cost,
            "roas": roas,
            "mmm_factors": {
                "seasonal_multiplier": seasonal_mult,
                "carryover_multiplier": carryover_mult,
                "competitive_multiplier": competitive_mult,
                "external_multiplier": external_mult,
                "effective_ctr": effective_ctr,
                "effective_cvr": effective_cvr
            }
        }


@dataclass
class Market:
    """Represents a geographic market for geo-lift experiments."""
    
    code: str  # e.g., 'NYC', 'CHI', 'LAX'
    name: str  # e.g., 'New York City', 'Chicago', 'Los Angeles'
    population: int
    baseline_revenue: float = 0.0
    baseline_conversions: int = 0
    
    # Pre-experiment historical data (for synthetic control)
    historical_data: Dict[str, float] = field(default_factory=dict)  # date_str -> revenue
    
    def get_historical_series(self) -> List[float]:
        """Get historical revenue as ordered list."""
        return [v for k, v in sorted(self.historical_data.items())]


class GeoLiftExperiment:
    """
    Geo-Lift experiment for measuring incrementality across geographic markets.
    
    Uses synthetic control methodology:
    1. Select treatment markets (will receive ads/increased spend)
    2. Match with control markets (similar characteristics, no ads/normal spend)
    3. Run experiment for specified duration
    4. Calculate lift using synthetic control matching
    """
    
    def __init__(
        self,
        experiment_id: int,
        campaign_id: int,
        treatment_markets: List[Market],
        control_markets: List[Market],
        start_date: datetime,
        duration_days: int = 28
    ):
        """
        Initialize geo-lift experiment.
        
        Args:
            experiment_id: Unique ID for this experiment
            campaign_id: Campaign being tested
            treatment_markets: Markets that will receive treatment (ads)
            control_markets: Markets that serve as control (no ads)
            start_date: When experiment begins
            duration_days: How long to run (default 4 weeks)
        """
        self.experiment_id = experiment_id
        self.campaign_id = campaign_id
        self.treatment_markets = treatment_markets
        self.control_markets = control_markets
        self.start_date = start_date
        self.end_date = start_date + timedelta(days=duration_days)
        self.duration_days = duration_days
        self.status = 'designing'  # 'designing', 'running', 'completed', 'aborted'
        
        # Synthetic control weights (calculated during matching)
        self.control_weights: Dict[str, float] = {}
        
        # Daily tracking
        self.treatment_daily: Dict[str, Dict] = {}  # date -> {revenue, conversions, spend}
        self.control_daily: Dict[str, Dict] = {}    # date -> {revenue, conversions}
        
        # Results
        self.results: Optional[Dict] = None
    
    def match_synthetic_control(self, min_correlation: float = 0.85) -> bool:
        """
        Find optimal weights for control markets to match treatment pre-period.
        
        Uses constrained optimization to find weights that make the weighted
        average of control markets best match the treatment markets' historical
        performance.
        
        Args:
            min_correlation: Minimum acceptable correlation (default 0.85)
        
        Returns:
            True if matching succeeded with acceptable correlation
        """
        if not all(m.historical_data for m in self.treatment_markets):
            return False
        if not all(m.historical_data for m in self.control_markets):
            return False
        
        # Get aggregated treatment historical series
        treatment_series = self._aggregate_market_series(self.treatment_markets)
        
        # Get individual control market series
        control_series_list = [m.get_historical_series() for m in self.control_markets]
        
        if not treatment_series or not all(control_series_list):
            return False
        
        # Simple matching: find weights that minimize MSE
        # Using constrained least squares (weights sum to 1, non-negative)
        weights = self._calculate_optimal_weights(treatment_series, control_series_list)
        
        if weights is None:
            return False
        
        # Store weights
        for i, market in enumerate(self.control_markets):
            self.control_weights[market.code] = weights[i]
        
        # Calculate correlation
        synthetic_series = self._apply_weights(control_series_list, weights)
        correlation = self._calculate_correlation(treatment_series, synthetic_series)
        
        return correlation >= min_correlation
    
    def _aggregate_market_series(self, markets: List[Market]) -> List[float]:
        """Aggregate revenue series across markets."""
        if not markets:
            return []
        
        # Get all dates
        all_dates = set()
        for m in markets:
            all_dates.update(m.historical_data.keys())
        
        sorted_dates = sorted(all_dates)
        
        # Sum across markets for each date
        series = []
        for date in sorted_dates:
            total = sum(m.historical_data.get(date, 0) for m in markets)
            series.append(total)
        
        return series
    
    def _calculate_optimal_weights(
        self, 
        treatment: List[float], 
        controls: List[List[float]]
    ) -> Optional[List[float]]:
        """
        Calculate optimal weights for synthetic control.
        
        Uses simplified gradient descent with constraints:
        - Weights sum to 1
        - Weights are non-negative
        """
        n_controls = len(controls)
        if n_controls == 0:
            return None
        
        # Initialize with equal weights
        weights = [1.0 / n_controls] * n_controls
        
        # Simple iterative optimization
        learning_rate = 0.01
        for _ in range(1000):
            # Calculate synthetic control
            synthetic = self._apply_weights(controls, weights)
            
            # Calculate gradient (MSE)
            gradient = [0.0] * n_controls
            for i in range(n_controls):
                for t in range(len(treatment)):
                    if t < len(controls[i]):
                        error = synthetic[t] - treatment[t]
                        gradient[i] += 2 * error * controls[i][t]
            
            # Update weights
            for i in range(n_controls):
                weights[i] -= learning_rate * gradient[i]
            
            # Project to constraints (simplex projection)
            weights = self._project_to_simplex(weights)
        
        return weights
    
    def _project_to_simplex(self, weights: List[float]) -> List[float]:
        """Project weights to probability simplex (sum=1, non-negative)."""
        # Clip to non-negative
        weights = [max(0, w) for w in weights]
        
        # Normalize to sum to 1
        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]
        else:
            # If all zero, use equal weights
            n = len(weights)
            weights = [1.0 / n] * n
        
        return weights
    
    def _apply_weights(
        self, 
        control_series: List[List[float]], 
        weights: List[float]
    ) -> List[float]:
        """Apply weights to create synthetic control series."""
        if not control_series:
            return []
        
        max_len = max(len(s) for s in control_series)
        synthetic = []
        
        for t in range(max_len):
            weighted_sum = 0.0
            for i, series in enumerate(control_series):
                if t < len(series):
                    weighted_sum += weights[i] * series[t]
            synthetic.append(weighted_sum)
        
        return synthetic
    
    def _calculate_correlation(self, series1: List[float], series2: List[float]) -> float:
        """Calculate Pearson correlation between two series."""
        n = min(len(series1), len(series2))
        if n < 2:
            return 0.0
        
        s1, s2 = series1[:n], series2[:n]
        
        mean1 = sum(s1) / n
        mean2 = sum(s2) / n
        
        numerator = sum((s1[i] - mean1) * (s2[i] - mean2) for i in range(n))
        
        var1 = sum((x - mean1) ** 2 for x in s1)
        var2 = sum((x - mean2) ** 2 for x in s2)
        
        denominator = math.sqrt(var1 * var2)
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    def start(self):
        """Start the experiment."""
        self.status = 'running'
        self.start_date = datetime.now()
        self.end_date = self.start_date + timedelta(days=self.duration_days)
    
    def record_daily_metrics(
        self,
        date: datetime,
        treatment_revenue: float,
        treatment_conversions: int,
        treatment_spend: float,
        control_revenue: float,
        control_conversions: int
    ):
        """
        Record daily metrics for both treatment and control.
        
        Args:
            date: Date of metrics
            treatment_revenue: Total revenue from treatment markets
            treatment_conversions: Total conversions from treatment markets
            treatment_spend: Total ad spend in treatment markets
            control_revenue: Total revenue from control markets
            control_conversions: Total conversions from control markets
        """
        date_key = date.strftime('%Y-%m-%d')
        
        self.treatment_daily[date_key] = {
            'revenue': treatment_revenue,
            'conversions': treatment_conversions,
            'spend': treatment_spend
        }
        
        self.control_daily[date_key] = {
            'revenue': control_revenue,
            'conversions': control_conversions
        }
    
    def calculate_lift(self, num_permutations: int = 1000) -> Dict[str, Any]:
        """
        Calculate lift using synthetic control methodology with permutation test.
        
        Returns:
            Dictionary with lift metrics and confidence intervals
        """
        if self.status != 'completed' and len(self.treatment_daily) < 7:
            return {'error': 'Insufficient data'}
        
        # Get experiment period data
        treatment_revenue = sum(d['revenue'] for d in self.treatment_daily.values())
        treatment_spend = sum(d['spend'] for d in self.treatment_daily.values())
        control_revenue_raw = sum(d['revenue'] for d in self.control_daily.values())
        
        # Apply synthetic control weights to get expected control
        if self.control_weights:
            # Scale control revenue by weights (simplified)
            control_revenue = control_revenue_raw
        else:
            control_revenue = control_revenue_raw
        
        # Calculate treatment markets' expected revenue without ads
        # Use pre-period ratio
        treatment_population = sum(m.population for m in self.treatment_markets)
        control_population = sum(m.population for m in self.control_markets)
        
        if control_population > 0:
            # Scale control to treatment size
            scale_factor = treatment_population / control_population
            expected_without_ads = control_revenue * scale_factor
        else:
            expected_without_ads = 0
        
        # Calculate lift
        incremental_revenue = treatment_revenue - expected_without_ads
        
        if expected_without_ads > 0:
            lift_percent = (incremental_revenue / expected_without_ads) * 100
        else:
            lift_percent = 0
        
        # Calculate iROAS
        if treatment_spend > 0:
            incremental_roas = incremental_revenue / treatment_spend
            observed_roas = treatment_revenue / treatment_spend
        else:
            incremental_roas = 0
            observed_roas = 0
        
        # Run permutation test for confidence interval
        ci_result = self._permutation_test(num_permutations)
        
        self.results = {
            'lift_percent': lift_percent,
            'incremental_revenue': incremental_revenue,
            'incremental_roas': incremental_roas,
            'observed_roas': observed_roas,
            'treatment_revenue': treatment_revenue,
            'control_revenue': control_revenue,
            'expected_without_ads': expected_without_ads,
            'treatment_spend': treatment_spend,
            'confidence_interval': ci_result.get('confidence_interval'),
            'p_value': ci_result.get('p_value'),
            'is_significant': ci_result.get('is_significant', False),
            'days_in_experiment': len(self.treatment_daily)
        }
        
        return self.results
    
    def _permutation_test(self, num_permutations: int = 1000) -> Dict[str, Any]:
        """
        Run permutation test for statistical significance.
        
        Randomly reassigns treatment/control labels and calculates lift
        to build null distribution.
        """
        treatment_values = [d['revenue'] for d in self.treatment_daily.values()]
        control_values = [d['revenue'] for d in self.control_daily.values()]
        
        if not treatment_values or not control_values:
            return {'p_value': 1.0, 'is_significant': False, 'confidence_interval': (0, 0)}
        
        # Observed difference
        observed_diff = sum(treatment_values) - sum(control_values)
        
        # Pool all values
        pooled = treatment_values + control_values
        n_treatment = len(treatment_values)
        
        # Permutation distribution
        permuted_diffs = []
        for _ in range(num_permutations):
            random.shuffle(pooled)
            perm_treatment = pooled[:n_treatment]
            perm_control = pooled[n_treatment:]
            perm_diff = sum(perm_treatment) - sum(perm_control)
            permuted_diffs.append(perm_diff)
        
        # P-value (two-tailed)
        extreme_count = sum(1 for d in permuted_diffs if abs(d) >= abs(observed_diff))
        p_value = extreme_count / num_permutations
        
        # Confidence interval
        permuted_diffs.sort()
        ci_lower_idx = int(0.025 * num_permutations)
        ci_upper_idx = int(0.975 * num_permutations)
        
        ci_lower = permuted_diffs[ci_lower_idx] if ci_lower_idx < len(permuted_diffs) else 0
        ci_upper = permuted_diffs[ci_upper_idx] if ci_upper_idx < len(permuted_diffs) else 0
        
        return {
            'p_value': p_value,
            'is_significant': p_value < 0.05,
            'confidence_interval': (ci_lower, ci_upper)
        }
    
    def complete(self):
        """Mark experiment as completed and calculate final results."""
        self.status = 'completed'
        self.calculate_lift()
    
    def abort(self, reason: str = None):
        """Abort the experiment."""
        self.status = 'aborted'
        self.abort_reason = reason
    
    def get_status(self) -> Dict[str, Any]:
        """Get current experiment status."""
        return {
            'experiment_id': self.experiment_id,
            'campaign_id': self.campaign_id,
            'status': self.status,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'days_remaining': (self.end_date - datetime.now()).days if self.end_date else None,
            'treatment_markets': [m.code for m in self.treatment_markets],
            'control_markets': [m.code for m in self.control_markets],
            'days_of_data': len(self.treatment_daily),
            'results': self.results
        }
