"""
Historical Data Loader for MMM Integration

Loads and processes historical advertising data to initialize bandit priors
and provide baseline MMM coefficients for realistic simulation.
"""

import json
import csv
from pathlib import Path
from datetime import datetime, timedelta
import random

class MMMDataLoader:
    """
    Loads and processes historical MMM (Marketing Mix Modeling) data.

    Provides baseline coefficients, seasonal patterns, and historical priors
    for initializing the bandit agent with realistic performance expectations.
    """

    def __init__(self):
        self.historical_data = None
        self.mmm_coefficients = {}
        self.seasonal_patterns = {}
        self.baseline_metrics = {}

    def load_historical_data(self, filepath=None, data_dict=None):
        """
        Load historical advertising performance data.

        Args:
            filepath: Path to CSV/JSON file with historical data
            data_dict: Dictionary with historical data (alternative to file)

        Expected data format:
        {
            'platform_channel_combinations': {
                'Google_Search': {
                    'historical_ctr': 0.045,
                    'historical_cvr': 0.12,
                    'historical_roas': 2.1,
                    'spend_baseline': 10000,
                    'variance_ctr': 0.01,
                    'variance_cvr': 0.02
                },
                ...
            },
            'seasonal_multipliers': {
                'Q1': {'Search': 0.8, 'Display': 0.9, 'Social': 1.2},
                'Q2': {'Search': 1.0, 'Display': 1.1, 'Social': 1.1},
                ...
            },
            'external_factors': {
                'holidays': ['2024-12-25', '2024-01-01'],
                'events': {'Super_Bowl': {'dates': ['2024-02-11'], 'impact': 1.5}}
            }
        }
        """
        if filepath:
            if filepath.endswith('.json'):
                with open(filepath, 'r') as f:
                    self.historical_data = json.load(f)
            elif filepath.endswith('.csv'):
                with open(filepath, 'r') as f:
                    csv_data = list(csv.DictReader(f))
                self.historical_data = self._process_csv_data(csv_data)
        elif data_dict:
            self.historical_data = data_dict

        if self.historical_data:
            self._extract_coefficients()
            self._extract_seasonal_patterns()
            self._calculate_baselines()

        return self.historical_data is not None

    def _process_csv_data(self, csv_rows):
        """Process CSV data into expected format using built-in Python."""
        from collections import defaultdict
        import statistics

        # Group data by platform and channel
        grouped_data = defaultdict(lambda: defaultdict(list))

        for row in csv_rows:
            platform = row.get('platform', '').strip()
            channel = row.get('channel', '').strip()
            key = f"{platform}_{channel}"

            # Collect numeric values
            try:
                if 'ctr' in row and row['ctr']:
                    grouped_data[key]['ctr'].append(float(row['ctr']))
                if 'cvr' in row and row['cvr']:
                    grouped_data[key]['cvr'].append(float(row['cvr']))
                if 'roas' in row and row['roas']:
                    grouped_data[key]['roas'].append(float(row['roas']))
                if 'spend' in row and row['spend']:
                    grouped_data[key]['spend'].append(float(row['spend']))
            except (ValueError, KeyError):
                continue  # Skip invalid rows

        data_dict = {'platform_channel_combinations': {}}

        for key, metrics in grouped_data.items():
            ctr_values = metrics.get('ctr', [])
            cvr_values = metrics.get('cvr', [])
            roas_values = metrics.get('roas', [])
            spend_values = metrics.get('spend', [])

            if ctr_values and cvr_values and roas_values:
                data_dict['platform_channel_combinations'][key] = {
                    'historical_ctr': statistics.mean(ctr_values),
                    'historical_cvr': statistics.mean(cvr_values),
                    'historical_roas': statistics.mean(roas_values),
                    'spend_baseline': sum(spend_values) if spend_values else 1000,
                    'variance_ctr': statistics.variance(ctr_values) if len(ctr_values) > 1 else statistics.mean(ctr_values) * 0.1,
                    'variance_cvr': statistics.variance(cvr_values) if len(cvr_values) > 1 else statistics.mean(cvr_values) * 0.1
                }

        return data_dict

    def _extract_coefficients(self):
        """Extract MMM coefficients from historical data."""
        # Support both formats: platform_channel_combinations and historical_performance
        if 'platform_channel_combinations' in self.historical_data:
            for combo_key, metrics in self.historical_data['platform_channel_combinations'].items():
                # Initialize priors based on historical performance
                self.mmm_coefficients[combo_key] = {
                    'ctr_baseline': metrics.get('historical_ctr', 0.03),
                    'cvr_baseline': metrics.get('historical_cvr', 0.08),
                    'roas_baseline': metrics.get('historical_roas', 1.2),
                    'spend_baseline': metrics.get('spend_baseline', 1000),
                    'ctr_variance': metrics.get('variance_ctr', 0.001),
                    'cvr_variance': metrics.get('variance_cvr', 0.004)
                }
        elif 'historical_performance' in self.historical_data:
            # Handle historical_performance format (e.g., "Google_Search_Creative A_1.0")
            for combo_key, metrics in self.historical_data['historical_performance'].items():
                # Extract platform and channel from key (format: Platform_Channel_...)
                parts = combo_key.split('_')
                if len(parts) >= 2:
                    platform = parts[0].lower()
                    channel = parts[1].lower()
                    simple_key = f"{platform}_{channel}"
                    
                    # Initialize priors based on historical performance
                    self.mmm_coefficients[simple_key] = {
                        'ctr_baseline': metrics.get('historical_ctr', 0.03),
                        'cvr_baseline': metrics.get('historical_cvr', 0.08),
                        'roas_baseline': metrics.get('historical_roas', 1.2),
                        'spend_baseline': metrics.get('spend_baseline', 1000),
                        'ctr_variance': metrics.get('variance_ctr', 0.001),
                        'cvr_variance': metrics.get('variance_cvr', 0.004)
                    }

    def _extract_seasonal_patterns(self):
        """Extract seasonal patterns from data."""
        if 'seasonal_multipliers' in self.historical_data:
            self.seasonal_patterns = self.historical_data['seasonal_multipliers']
        else:
            # Default seasonal patterns based on typical digital advertising
            self.seasonal_patterns = {
                'Q1': {'Search': 0.85, 'Display': 0.90, 'Social': 1.15},  # Holiday recovery
                'Q2': {'Search': 1.05, 'Display': 1.10, 'Social': 1.08},  # Spring growth
                'Q3': {'Search': 0.95, 'Display': 1.15, 'Social': 0.90},  # Back to school
                'Q4': {'Search': 1.20, 'Display': 1.25, 'Social': 1.30}   # Holiday season
            }

    def _calculate_baselines(self):
        """Calculate baseline metrics for initialization."""
        if self.mmm_coefficients:
            # Calculate overall baselines
            ctr_sum = sum(coeff['ctr_baseline'] for coeff in self.mmm_coefficients.values())
            cvr_sum = sum(coeff['cvr_baseline'] for coeff in self.mmm_coefficients.values())
            roas_sum = sum(coeff['roas_baseline'] for coeff in self.mmm_coefficients.values())

            n_combos = len(self.mmm_coefficients)

            self.baseline_metrics = {
                'avg_ctr': ctr_sum / n_combos,
                'avg_cvr': cvr_sum / n_combos,
                'avg_roas': roas_sum / n_combos,
                'total_combinations': n_combos
            }

    def get_arm_priors(self, arm):
        """
        Get Bayesian priors for a specific arm based on historical data.

        Args:
            arm: Arm object

        Returns:
            dict: Prior parameters for beta distribution
        """
        # Create key from arm attributes
        platform = arm.platform.lower().replace(' ', '_')
        channel = arm.channel.lower()

        # Try exact match first
        exact_key = f"{platform}_{channel}"
        if exact_key in self.mmm_coefficients:
            coeff = self.mmm_coefficients[exact_key]
            # Convert historical performance to beta distribution parameters
            # Using method of moments for beta distribution
            ctr_mean = coeff['ctr_baseline']
            ctr_var = coeff['ctr_variance']

            # Beta parameters: alpha = mean*(mean*(1-mean)/var - 1)
            # beta = (1-mean)*(mean*(1-mean)/var - 1)
            if ctr_var > 0 and 0 < ctr_mean < 1:
                temp = ctr_mean * (1 - ctr_mean) / ctr_var
                alpha_ctr = ctr_mean * (temp - 1)
                beta_ctr = (1 - ctr_mean) * (temp - 1)
            else:
                alpha_ctr = beta_ctr = 1.0  # Uniform prior

            return {
                'alpha': max(1.0, alpha_ctr),
                'beta': max(1.0, beta_ctr),
                'expected_roas': coeff['roas_baseline'],
                'historical_performance': coeff
            }

        # Fallback to platform-only match
        platform_key = platform
        for key, coeff in self.mmm_coefficients.items():
            if key.startswith(platform_key):
                return {
                    'alpha': 1.0,  # Conservative prior
                    'beta': 1.0,
                    'expected_roas': coeff['roas_baseline'],
                    'historical_performance': coeff
                }

        # Ultimate fallback
        return {
            'alpha': 1.0,
            'beta': 1.0,
            'expected_roas': 1.2,
            'historical_performance': None
        }

    def get_seasonal_multiplier(self, date=None, channel=None):
        """
        Get seasonal multiplier for given date and channel.

        Args:
            date: datetime object or string
            channel: channel name

        Returns:
            float: seasonal multiplier
        """
        if not date:
            date = datetime.now()

        if isinstance(date, str):
            date = datetime.fromisoformat(date.replace('Z', '+00:00'))

        # Determine quarter
        quarter = f"Q{(date.month - 1) // 3 + 1}"

        if quarter in self.seasonal_patterns and channel:
            channel_multipliers = self.seasonal_patterns[quarter]
            return channel_multipliers.get(channel, 1.0)

        return 1.0

    def create_sample_historical_data(self):
        """
        Create sample historical MMM data for testing.

        Returns:
            dict: Sample historical data
        """
        return {
            'platform_channel_combinations': {
                'Google_Search': {
                    'historical_ctr': 0.045,
                    'historical_cvr': 0.12,
                    'historical_roas': 2.1,
                    'spend_baseline': 50000,
                    'variance_ctr': 0.0008,
                    'variance_cvr': 0.0025
                },
                'Google_Display': {
                    'historical_ctr': 0.025,
                    'historical_cvr': 0.08,
                    'historical_roas': 1.8,
                    'spend_baseline': 30000,
                    'variance_ctr': 0.0004,
                    'variance_cvr': 0.0018
                },
                'Meta_Social': {
                    'historical_ctr': 0.035,
                    'historical_cvr': 0.09,
                    'historical_roas': 1.9,
                    'spend_baseline': 40000,
                    'variance_ctr': 0.0006,
                    'variance_cvr': 0.0021
                },
                'The Trade Desk_Display': {
                    'historical_ctr': 0.020,
                    'historical_cvr': 0.07,
                    'historical_roas': 1.5,
                    'spend_baseline': 20000,
                    'variance_ctr': 0.0005,
                    'variance_cvr': 0.0016
                }
            },
            'seasonal_multipliers': {
                'Q1': {'Search': 0.85, 'Display': 0.90, 'Social': 1.15},
                'Q2': {'Search': 1.05, 'Display': 1.10, 'Social': 1.08},
                'Q3': {'Search': 0.95, 'Display': 1.15, 'Social': 0.90},
                'Q4': {'Search': 1.20, 'Display': 1.25, 'Social': 1.30}
            },
            'external_factors': {
                'holidays': ['12-25', '01-01', '07-04'],
                'major_events': {
                    'super_bowl': {'month': 2, 'impact_multiplier': 1.4},
                    'black_friday': {'month': 11, 'week': 4, 'impact_multiplier': 2.0}
                }
            }
        }