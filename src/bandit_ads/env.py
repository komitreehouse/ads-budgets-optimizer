import random
from datetime import datetime, timedelta
from collections import defaultdict

class AdEnvironment:
    """
    Simulates an advertising environment with comprehensive MMM factors.

    Includes seasonality, competitive effects, carryover/ad stock, and external factors
    for realistic multi-armed bandit advertising simulation.
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
