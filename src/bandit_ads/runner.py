"""
Ad Budget Optimization Runner

Orchestrates the multi-armed bandit system for optimizing advertising spend.
Integrates arms, environment, and agent for complete MMM-based optimization.
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import json

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.bandit_ads.arms import ArmManager
from src.bandit_ads.env import AdEnvironment
from src.bandit_ads.agent import ThompsonSamplingAgent
from src.bandit_ads.contextual_agent import ContextualBanditAgent
from src.bandit_ads.data_loader import MMMDataLoader
from src.bandit_ads.utils import (
    setup_logging, get_logger, ConfigManager, 
    retry_on_failure, handle_errors, validate_arm_params
)

class AdOptimizationRunner:
    """
    Main runner for ad budget optimization campaigns.

    Handles the complete lifecycle of a bandit-based ad optimization:
    1. Campaign setup (arms, budget, environment parameters)
    2. Simulation execution
    3. Performance tracking and reporting
    4. Results analysis
    """

    def __init__(self, campaign_config, config_manager: ConfigManager = None):
        """
        Initialize the runner with campaign configuration.

        Args:
            campaign_config: Dictionary containing campaign parameters
            config_manager: Optional ConfigManager instance for global config
        """
        self.config = campaign_config
        self.config_manager = config_manager or ConfigManager()
        self.campaign_name = campaign_config.get('name', 'default_campaign')
        self.start_time = None
        self.end_time = None
        
        # Set up logging
        log_level = self.config_manager.get('logging.level', 'INFO')
        log_file = self.config_manager.get('logging.file')
        setup_logging(log_level, log_file)
        self.logger = get_logger('runner')

        # Initialize components
        self.arm_manager = None
        self.environment = None
        self.agent = None
        self.use_contextual = False

        # Results tracking
        self.results_history = []
        self.performance_log = []

    @handle_errors(default_return=False)
    def setup_campaign(self):
        """Set up the campaign components based on configuration."""
        self.logger.info(f"Setting up campaign: {self.campaign_name}")

        # Load historical MMM data if provided
        self.data_loader = MMMDataLoader()
        historical_config = self.config.get('historical_data', {})
        if historical_config.get('enabled', False):
            data_path = historical_config.get('file_path')
            if data_path:
                success = self.data_loader.load_historical_data(data_path)
                if success:
                    self.logger.info("Loaded historical MMM data for priors")
                else:
                    self.logger.warning("Could not load historical data, using defaults")
            else:
                # Use sample data for demonstration
                sample_data = self.data_loader.create_sample_historical_data()
                self.data_loader.load_historical_data(data_dict=sample_data)
                self.logger.info("Using sample historical MMM data")

        # Create arm combinations
        arm_config = self.config['arms']
        self.arm_manager = ArmManager(
            platforms=arm_config['platforms'],
            channels=arm_config['channels'],
            creatives=arm_config['creatives'],
            bids=arm_config['bids']
        )

        arms = self.arm_manager.get_arms()
        self.logger.info(f"Created {len(arms)} advertising arms")

        # Set up environment with MMM factors
        env_config = self.config.get('environment', {})
        mmm_factors = env_config.get('mmm_factors', {})

        # Initialize arm-specific params with historical data if available
        arm_specific_params = env_config.get('arm_specific_params', {})
        if self.data_loader.historical_data:
            # Enhance arm-specific params with historical priors
            for arm in arms:
                arm_key = str(arm)
                if arm_key not in arm_specific_params:
                    # Try to get historical performance for this arm combination
                    priors = self.data_loader.get_arm_priors(arm)
                    if priors['historical_performance']:
                        hist = priors['historical_performance']
                        try:
                            arm_specific_params[arm_key] = validate_arm_params({
                                'ctr': hist['historical_ctr'],
                                'cvr': hist['historical_cvr'],
                                'revenue': 10.0,  # Default revenue per conversion
                                'cpc': 1.0       # Default cost per click
                            })
                        except ValueError as e:
                            self.logger.warning(f"Invalid arm params for {arm_key}: {e}")

        self.environment = AdEnvironment(
            global_params=env_config.get('global_params', {}),
            arm_specific_params=arm_specific_params,
            mmm_factors=mmm_factors
        )

        # Set up agent (contextual or standard)
        agent_config = self.config.get('agent', {})
        contextual_config = self.config.get('contextual', {})
        use_contextual = contextual_config.get('enabled', False)
        
        if use_contextual:
            # Use contextual bandit agent
            context_config = contextual_config.get('features', {})
            self.logger.info("Using Contextual Bandit Agent")
            self.agent = ContextualBanditAgent(
                arms=arms,
                total_budget=agent_config.get('total_budget', 1000.0),
                min_allocation=agent_config.get('min_allocation', 0.01),
                risk_tolerance=agent_config.get('risk_tolerance', 0.3),
                variance_limit=agent_config.get('variance_limit', 0.1),
                context_config=context_config,
                alpha=contextual_config.get('alpha', 1.0)
            )
        else:
            # Use standard Thompson Sampling agent
            self.logger.info("Using Standard Thompson Sampling Agent")
            self.agent = ThompsonSamplingAgent(
                arms=arms,
                total_budget=agent_config.get('total_budget', 1000.0),
                min_allocation=agent_config.get('min_allocation', 0.01),
                risk_tolerance=agent_config.get('risk_tolerance', 0.3),
                variance_limit=agent_config.get('variance_limit', 0.1)
            )
        
        self.use_contextual = use_contextual

        # Initialize agent priors with historical data if available
        if self.data_loader.historical_data:
            self._initialize_agent_priors()

        self.logger.info("Campaign setup complete")

    def _initialize_agent_priors(self):
        """Initialize agent priors with historical data."""
        for arm in self.agent.arms:
            priors = self.data_loader.get_arm_priors(arm)
            arm_key = str(arm)

            if priors['historical_performance']:
                # Initialize beta distribution with historical performance
                hist = priors['historical_performance']

                # Convert historical CTR to beta parameters
                ctr_mean = hist['historical_ctr']
                ctr_var = hist.get('variance_ctr', ctr_mean * 0.1)  # Default variance

                if ctr_var > 0 and 0 < ctr_mean < 1:
                    temp = ctr_mean * (1 - ctr_mean) / ctr_var
                    alpha = ctr_mean * (temp - 1)
                    beta_param = (1 - ctr_mean) * (temp - 1)

                    self.agent.alpha[arm_key] = max(1.0, alpha)
                    self.agent.beta[arm_key] = max(1.0, beta_param)

                print(f"Initialized {arm_key} with historical priors: α={self.agent.alpha[arm_key]:.2f}, β={self.agent.beta[arm_key]:.2f}")

    def _generate_context_for_round(self, round_num: int) -> Dict[str, Any]:
        """
        Generate context for a campaign round.
        
        In a real system, this would come from actual user data.
        For simulation, we generate synthetic context.
        
        Args:
            round_num: Current round number
        
        Returns:
            Context dictionary with user_data and timestamp
        """
        import random
        from datetime import datetime, timedelta
        
        # Simulate different user segments over time
        user_segments = [
            {'age': 28, 'gender': 'male', 'location': 'us', 'device_type': 'mobile'},
            {'age': 35, 'gender': 'female', 'location': 'eu', 'device_type': 'desktop'},
            {'age': 42, 'gender': 'male', 'location': 'us', 'device_type': 'tablet'},
            {'age': 25, 'gender': 'female', 'location': 'asia', 'device_type': 'mobile'},
        ]
        
        # Cycle through user segments
        user_data = user_segments[round_num % len(user_segments)]
        
        # Add some randomness
        if random.random() < 0.3:
            user_data = random.choice(user_segments)
        
        # Simulate time progression
        timestamp = datetime.now() + timedelta(hours=round_num)
        
        return {
            'user_data': user_data,
            'timestamp': timestamp
        }

    def run_campaign(self, max_rounds=None, log_frequency=50):
        """
        Run the optimization campaign.

        Args:
            max_rounds: Maximum number of rounds to run (None = until budget exhausted)
            log_frequency: How often to log progress
        """
        if not self.agent or not self.environment:
            raise ValueError("Campaign not set up. Call setup_campaign() first.")

        print(f"\nStarting campaign: {self.campaign_name}")
        print(f"Budget: ${self.agent.total_budget}")
        print("=" * 60)

        self.start_time = datetime.now()
        round_num = 0

        while not self.agent.is_budget_exhausted():
            if max_rounds and round_num >= max_rounds:
                print(f"Reached maximum rounds ({max_rounds})")
                break

            round_num += 1

            # Generate context if using contextual bandit
            context = None
            if self.use_contextual:
                context = self._generate_context_for_round(round_num)

            # Select arm (with context if contextual mode)
            if self.use_contextual and isinstance(self.agent, ContextualBanditAgent):
                arm = self.agent.select_arm(context=context)
            else:
                arm = self.agent.select_arm()
            
            impressions = self.config.get('impressions_per_round', 100)

            # Calculate spend amount based on agent's allocation (for MMM carryover effects)
            arm_key = str(arm)
            allocated_budget = self.agent.current_allocation.get(arm_key, 0)
            spend_amount = min(allocated_budget * 0.1, self.agent.total_budget * 0.05)  # Spend 10% of allocation or 5% of total budget max

            result = self.environment.step(arm, impressions=impressions, spend_amount=spend_amount, context=context)

            # Update agent (with context if contextual mode)
            if self.use_contextual and isinstance(self.agent, ContextualBanditAgent):
                self.agent.update(arm, result, context=context)
            else:
                self.agent.update(arm, result)

            # Log results
            self.results_history.append({
                'round': round_num,
                'arm': str(arm),
                'result': result,
                'timestamp': datetime.now().isoformat()
            })

            # Periodic logging
            if round_num % log_frequency == 0:
                metrics = self.agent.get_performance_metrics()
                self.performance_log.append({
                    'round': round_num,
                    'metrics': metrics,
                    'timestamp': datetime.now().isoformat()
                })

                print(f"Round {round_num}: Spent ${metrics['total_spent']:.2f}, ROAS: {metrics['total_roas']:.2f}")

        self.end_time = datetime.now()
        duration = self.end_time - self.start_time

        print("\n" + "=" * 60)
        print("CAMPAIGN COMPLETE")
        print(f"Duration: {duration.total_seconds():.1f} seconds")
        print(f"Rounds completed: {round_num}")

        return self.get_final_results()

    def get_final_results(self):
        """Get comprehensive final results of the campaign."""
        if not self.agent:
            return None

        metrics = self.agent.get_performance_metrics()

        results = {
            'campaign_name': self.campaign_name,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else None,
            'configuration': self.config,
            'final_metrics': metrics,
            'total_rounds': len(self.results_history),
            'results_history': self.results_history,
            'performance_log': self.performance_log,
            'top_performing_arms': self._get_top_arms(metrics, top_n=5)
        }

        return results

    def _get_top_arms(self, metrics, top_n=5):
        """Get top performing arms by ROAS."""
        arm_perf = metrics['arm_performance']
        sorted_arms = sorted(
            arm_perf.items(),
            key=lambda x: x[1]['avg_roas'],
            reverse=True
        )
        return sorted_arms[:top_n]

    def save_results(self, filepath=None):
        """Save campaign results to file."""
        if not filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"campaign_results_{self.campaign_name}_{timestamp}.json"

        results = self.get_final_results()
        if results:
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"Results saved to: {filepath}")
            return filepath
        return None

    def print_summary(self):
        """Print a summary of the campaign results."""
        results = self.get_final_results()
        if not results:
            print("No results available")
            return

        print("\n" + "="*80)
        print(f"CAMPAIGN SUMMARY: {results['campaign_name'].upper()}")
        print("="*80)

        metrics = results['final_metrics']
        print(f"Total Budget: ${metrics['total_budget']:.2f}")
        print(f"Total Spent: ${metrics['total_spent']:.2f}")
        print(f"Budget Utilization: {metrics['budget_utilization']:.2f}")
        print(f"Overall ROAS: {metrics['total_roas']:.2f}")

        print("\nTOP 5 PERFORMING ARMS:")
        print("-" * 50)
        for i, (arm_str, perf) in enumerate(results['top_performing_arms'], 1):
            print(f"{i}. {arm_str}")
            print(f"   Average ROAS: {perf['avg_roas']:.2f}")
            print(f"   Total Spent: ${perf['spending']:.2f}")
            print()

# Example usage and configuration
def create_sample_campaign_config():
    """Create a sample campaign configuration with full MMM features."""
    return {
        'name': 'comprehensive_mmm_optimization',
        'historical_data': {
            'enabled': True,  # Use sample historical data
            'file_path': None  # Will use sample data
        },
        'arms': {
            'platforms': ['Google', 'Meta', 'The Trade Desk'],
            'channels': ['Search', 'Display', 'Social'],
            'creatives': ['Creative A', 'Creative B', 'Creative C'],
            'bids': [0.5, 1.0, 1.5, 2.0]
        },
        'environment': {
            'global_params': {
                'ctr': 0.03,    # 3% baseline CTR
                'cvr': 0.08,    # 8% baseline CVR
                'revenue': 10.0,# $10 per conversion
                'cpc': 1.0      # $1 per click
            },
            'arm_specific_params': {
                # High-performing combinations (based on typical MMM insights)
                'Arm(platform=Google, channel=Search, creative=Creative A, bid=1.0)': {
                    'ctr': 0.08, 'cvr': 0.15, 'revenue': 15.0, 'cpc': 0.8
                },
                'Arm(platform=Meta, channel=Social, creative=Creative B, bid=1.5)': {
                    'ctr': 0.06, 'cvr': 0.12, 'revenue': 12.0, 'cpc': 1.2
                },
                'Arm(platform=The Trade Desk, channel=Display, creative=Creative C, bid=0.5)': {
                    'ctr': 0.04, 'cvr': 0.10, 'revenue': 11.0, 'cpc': 0.9
                },
                # Underperforming combinations
                'Arm(platform=Google, channel=Display, creative=Creative A, bid=2.0)': {
                    'ctr': 0.015, 'cvr': 0.03, 'revenue': 8.0, 'cpc': 2.5
                }
            },
            'mmm_factors': {
                'seasonality': {
                    'Q1': {'Search': 0.85, 'Display': 0.90, 'Social': 1.15},
                    'Q2': {'Search': 1.05, 'Display': 1.10, 'Social': 1.08},
                    'Q3': {'Search': 0.95, 'Display': 1.15, 'Social': 0.90},
                    'Q4': {'Search': 1.20, 'Display': 1.25, 'Social': 1.30}
                },
                'carryover': {
                    'decay_rate': 0.8,
                    'max_stock': 2.0,
                    'stock_half_life': 7
                },
                'competition': {
                    'market_saturation_threshold': 0.7,
                    'saturation_penalty': 0.3,
                    'recovery_rate': 0.95
                },
                'external': {
                    'holidays': ['12-25', '01-01', '07-04'],
                    'holiday_multiplier': 1.8
                }
            }
        },
        'agent': {
            'total_budget': 5000.0,
            'min_allocation': 0.005,  # 0.5% minimum per arm
            'risk_tolerance': 0.3,    # Moderate risk tolerance
            'variance_limit': 0.1     # Max 10% variance allowed
        },
        'impressions_per_round': 200
    }

if __name__ == "__main__":
    # Run a sample campaign
    config = create_sample_campaign_config()
    runner = AdOptimizationRunner(config)
    runner.setup_campaign()
    results = runner.run_campaign(max_rounds=200, log_frequency=50)
    runner.print_summary()
    runner.save_results()

# Add to runner.py
def load_historical_mmm_data(filepath):
    """Load historical performance data to initialize priors"""
    # Initialize agent with real MMM coefficients instead of uniform priors
    # Use historical baselines for CTR/CVR estimates