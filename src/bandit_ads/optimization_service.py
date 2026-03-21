"""
Continuous Optimization Service

Long-running service that continuously optimizes advertising campaigns.
Runs optimization cycles, maintains state, and handles multiple campaigns.
"""

import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from threading import Lock, Event
from enum import Enum

from src.bandit_ads.runner import AdOptimizationRunner, create_sample_campaign_config
from src.bandit_ads.database import get_db_manager
from src.bandit_ads.db_helpers import (
    get_campaign, get_arms_by_campaign, 
    get_agent_state, update_agent_state,
    get_experiments_by_campaign, record_incrementality_metric
)
from src.bandit_ads.agent import IncrementalityAwareBandit
from src.bandit_ads.utils import get_logger, ConfigManager
from src.bandit_ads.scheduler import get_scheduler

logger = get_logger('optimization_service')


class CampaignStatus(Enum):
    """Campaign status enumeration."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class ContinuousOptimizationService:
    """
    Continuous optimization service that runs optimization loops for campaigns.
    
    Features:
    - Runs optimization cycles at regular intervals
    - Maintains agent state in database
    - Handles multiple campaigns concurrently
    - Graceful shutdown/restart
    - Health monitoring
    
    Current Implementation
    ----------------------
    Uses IncrementalityAwareBandit by default with Thompson Sampling and
    real-time holdout tracking. This provides production-ready optimization
    with incrementality feedback.
    
    FUTURE BAYESIAN INTEGRATION POINT:
    ----------------------------------
    This service is where real-time Bayesian updates would be orchestrated:
    
    1. BAYESIAN LAYER INITIALIZATION:
       When a campaign is added, initialize Bayesian layer with priors:
       # def add_campaign(self, campaign_id, campaign_config):
       #     ...
       #     if self.bayesian_layer_enabled:
       #         self.bayesian_layers[campaign_id] = BayesianMMMLayer(
       #             prior_source='incrementality_experiments'  # Use experiment results as priors
       #         )
    
    2. REAL-TIME POSTERIOR UPDATES:
       After each optimization cycle, update Bayesian posteriors:
       # def _optimize_campaign(self, campaign_id):
       #     ...
       #     if campaign_id in self.bayesian_layers:
       #         self.bayesian_layers[campaign_id].update_posterior(
       #             arm=arm, result=result, context=context
       #         )
    
    3. INCREMENTALITY EXPERIMENT COMPLETION TRIGGER:
       When experiments complete, trigger Bayesian prior updates:
       # def on_experiment_completed(self, experiment_result):
       #     campaign_id = experiment_result['campaign_id']
       #     if campaign_id in self.bayesian_layers:
       #         self.bayesian_layers[campaign_id].incorporate_incrementality_prior(
       #             experiment_result
       #         )
       #     # Also update the bandit agent
       #     runner = self.campaign_runners.get(campaign_id)
       #     if runner and isinstance(runner.agent, IncrementalityAwareBandit):
       #         runner.agent.incorporate_incrementality(arm_key, experiment_result)
    
    4. UNCERTAINTY-AWARE ALLOCATION:
       Pass Bayesian uncertainty to agent for richer exploration:
       # allocation = runner.agent.allocate_with_uncertainty(
       #     bayesian_posterior=self.bayesian_layers[campaign_id].get_posterior()
       # )
    """
    
    def __init__(self, config_manager: Optional[ConfigManager] = None, 
                 optimization_interval_minutes: int = 15):
        """
        Initialize the continuous optimization service.
        
        Args:
            config_manager: Configuration manager
            optimization_interval_minutes: How often to run optimization (minutes)
        """
        self.config_manager = config_manager or ConfigManager()
        self.optimization_interval = optimization_interval_minutes
        self.running = False
        self.shutdown_event = Event()
        self.lock = Lock()

        # Track active campaigns
        self.active_campaigns: Dict[int, Dict[str, Any]] = {}
        self.campaign_runners: Dict[int, AdOptimizationRunner] = {}

        # Track previous allocations per campaign to detect changes
        self.previous_allocations: Dict[int, Dict[str, float]] = {}

        # Budget push config
        self.budget_push_enabled = self.config_manager.get('budget_push.enabled', False)
        self.budget_push_dry_run = self.config_manager.get('budget_push.dry_run', True)
        self.allocation_change_threshold = 0.01  # 1% minimum change to trigger push

        # Change tracking and explanation generation
        self._init_change_tracker()

        # Statistics
        self.stats = {
            'total_cycles': 0,
            'successful_cycles': 0,
            'failed_cycles': 0,
            'last_cycle_time': None,
            'campaigns_optimized': 0
        }
        
        logger.info(f"Optimization service initialized (interval: {optimization_interval_minutes} min)")
    
    def _init_change_tracker(self):
        """Initialize change tracking and explanation generation."""
        try:
            from src.bandit_ads.change_tracker import get_change_tracker
            self.change_tracker = get_change_tracker()
        except Exception as e:
            logger.warning(f"Change tracker unavailable: {e}")
            self.change_tracker = None

        try:
            from src.bandit_ads.explanation_generator import ExplanationGenerator
            self.explanation_generator = ExplanationGenerator()
        except Exception as e:
            logger.warning(f"Explanation generator unavailable: {e}")
            self.explanation_generator = None

    def start(self):
        """Start the continuous optimization service."""
        if self.running:
            logger.warning("Service is already running")
            return
        
        self.running = True
        self.shutdown_event.clear()
        
        # Load active campaigns from database
        self._load_active_campaigns()
        
        # Start optimization loop in background thread
        import threading
        self.optimization_thread = threading.Thread(
            target=self._optimization_loop,
            daemon=True,
            name="OptimizationLoop"
        )
        self.optimization_thread.start()
        
        logger.info("Continuous optimization service started")
    
    def stop(self, timeout: int = 30):
        """Stop the continuous optimization service."""
        if not self.running:
            logger.warning("Service is not running")
            return
        
        logger.info("Stopping optimization service...")
        self.running = False
        self.shutdown_event.set()
        
        # Wait for optimization thread to finish
        if hasattr(self, 'optimization_thread'):
            self.optimization_thread.join(timeout=timeout)
        
        logger.info("Optimization service stopped")
    
    def _load_active_campaigns(self):
        """Load active campaigns from database and create runners."""
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            from src.bandit_ads.database import Campaign
            campaigns = session.query(Campaign).filter(
                Campaign.status == 'active'
            ).all()

            for campaign in campaigns:
                # Build config and create runner for each active campaign
                config = self._build_campaign_config_from_db(campaign)
                if config:
                    success = self.add_campaign(campaign.id, config)
                    if not success:
                        # Still track the campaign even if runner creation fails
                        self.active_campaigns[campaign.id] = {
                            'id': campaign.id,
                            'name': campaign.name,
                            'budget': campaign.budget,
                            'status': CampaignStatus.ERROR,
                            'last_optimization': None,
                            'optimization_count': 0
                        }
                        logger.warning(f"Failed to create runner for campaign {campaign.id}")
                else:
                    logger.warning(f"Could not build config for campaign {campaign.id}")

        runners_created = len(self.campaign_runners)
        logger.info(f"Loaded {len(self.active_campaigns)} active campaigns, {runners_created} runners created")

    def _build_campaign_config_from_db(self, campaign) -> Optional[Dict[str, Any]]:
        """
        Build a campaign config dict from a Campaign database record.

        Uses the stored campaign_config JSON if available, otherwise
        reconstructs from campaign fields and associated arms.

        Args:
            campaign: Campaign database model instance

        Returns:
            Campaign config dict compatible with AdOptimizationRunner, or None on failure
        """
        try:
            # If campaign has stored config JSON, use it directly
            if campaign.campaign_config:
                config = json.loads(campaign.campaign_config)
                # Ensure budget is current
                config.setdefault('agent', {})['total_budget'] = campaign.budget
                config['name'] = campaign.name
                return config

            # Otherwise, reconstruct from DB fields and arms
            arms_db = get_arms_by_campaign(campaign.id)
            if not arms_db:
                logger.warning(f"No arms found for campaign {campaign.id}")
                return None

            # Extract unique platforms, channels, creatives, bids from arms
            platforms = list(set(a.platform for a in arms_db))
            channels = list(set(a.channel for a in arms_db))
            creatives = list(set(a.creative for a in arms_db))
            bids = sorted(set(a.bid for a in arms_db))

            config = {
                'name': campaign.name,
                'arms': {
                    'platforms': platforms,
                    'channels': channels,
                    'creatives': creatives,
                    'bids': bids
                },
                'environment': {
                    'global_params': {
                        'ctr': 0.03,
                        'cvr': 0.08,
                        'revenue': 10.0,
                        'cpc': 1.0
                    },
                    'mmm_factors': {}
                },
                'agent': {
                    'total_budget': campaign.budget,
                    'min_allocation': 0.005,
                    'risk_tolerance': 0.3,
                    'variance_limit': 0.1
                },
                'incrementality': {
                    'enabled': True,
                    'holdout_percentage': 0.10
                },
                'impressions_per_round': 200
            }

            return config

        except Exception as e:
            logger.error(f"Error building config for campaign {campaign.id}: {e}")
            return None
    
    def _get_or_create_runner(self, campaign_id: int) -> Optional[AdOptimizationRunner]:
        """Get existing runner or create one from DB config."""
        with self.lock:
            runner = self.campaign_runners.get(campaign_id)
            if runner:
                return runner

        # No runner — try to create from DB
        campaign = get_campaign(campaign_id)
        if not campaign:
            return None

        config = self._build_campaign_config_from_db(campaign)
        if not config:
            logger.warning(f"Cannot build config for campaign {campaign_id}")
            return None

        success = self.add_campaign(campaign_id, config)
        if not success:
            return None

        with self.lock:
            return self.campaign_runners.get(campaign_id)

    def add_campaign(self, campaign_id: int, campaign_config: Dict[str, Any]) -> bool:
        """
        Add a campaign to the optimization service.
        
        Args:
            campaign_id: Campaign ID
            campaign_config: Campaign configuration dictionary
        
        Returns:
            True if successful
        """
        with self.lock:
            try:
                # Create runner
                runner = AdOptimizationRunner(campaign_config, self.config_manager)
                runner.setup_campaign()
                
                # Restore agent state from database
                self._restore_agent_state(runner, campaign_id)
                
                # Register campaign
                self.active_campaigns[campaign_id] = {
                    'id': campaign_id,
                    'name': campaign_config.get('name', f'campaign_{campaign_id}'),
                    'budget': campaign_config.get('agent', {}).get('total_budget', 0),
                    'status': CampaignStatus.ACTIVE,
                    'last_optimization': None,
                    'optimization_count': 0
                }
                self.campaign_runners[campaign_id] = runner
                
                logger.info(f"Added campaign {campaign_id} to optimization service")
                return True
                
            except Exception as e:
                logger.error(f"Failed to add campaign {campaign_id}: {str(e)}")
                return False
    
    def remove_campaign(self, campaign_id: int):
        """Remove a campaign from optimization."""
        with self.lock:
            if campaign_id in self.active_campaigns:
                # Save state before removing
                if campaign_id in self.campaign_runners:
                    self._save_agent_state(self.campaign_runners[campaign_id], campaign_id)
                    del self.campaign_runners[campaign_id]
                
                del self.active_campaigns[campaign_id]
                logger.info(f"Removed campaign {campaign_id} from optimization service")
    
    def pause_campaign(self, campaign_id: int):
        """Pause optimization for a campaign."""
        with self.lock:
            if campaign_id in self.active_campaigns:
                self.active_campaigns[campaign_id]['status'] = CampaignStatus.PAUSED
                logger.info(f"Paused campaign {campaign_id}")
    
    def resume_campaign(self, campaign_id: int):
        """Resume optimization for a campaign."""
        with self.lock:
            if campaign_id in self.active_campaigns:
                self.active_campaigns[campaign_id]['status'] = CampaignStatus.ACTIVE
                logger.info(f"Resumed campaign {campaign_id}")
    
    def _optimization_loop(self):
        """Main optimization loop that runs continuously."""
        logger.info("Optimization loop started")
        
        while self.running and not self.shutdown_event.is_set():
            try:
                cycle_start = datetime.now()
                
                # Run optimization for all active campaigns
                campaigns_optimized = self._run_optimization_cycle()
                
                cycle_duration = (datetime.now() - cycle_start).total_seconds()
                
                # Update statistics
                with self.lock:
                    self.stats['total_cycles'] += 1
                    self.stats['successful_cycles'] += 1
                    self.stats['last_cycle_time'] = cycle_start
                    self.stats['campaigns_optimized'] = campaigns_optimized
                
                logger.info(
                    f"Optimization cycle completed: {campaigns_optimized} campaigns, "
                    f"duration: {cycle_duration:.2f}s"
                )
                
                # Wait for next cycle (with early exit on shutdown)
                wait_seconds = self.optimization_interval * 60
                if self.shutdown_event.wait(timeout=wait_seconds):
                    break  # Shutdown requested
                    
            except Exception as e:
                logger.error(f"Error in optimization loop: {str(e)}", exc_info=True)
                with self.lock:
                    self.stats['failed_cycles'] += 1
                
                # Wait a bit before retrying
                if self.shutdown_event.wait(timeout=60):
                    break
        
        logger.info("Optimization loop stopped")
    
    def _run_optimization_cycle(self) -> int:
        """
        Run one optimization cycle for all active campaigns.
        
        Returns:
            Number of campaigns optimized
        """
        campaigns_optimized = 0
        
        with self.lock:
            active_campaign_ids = list(self.active_campaigns.keys())
        
        for campaign_id in active_campaign_ids:
            try:
                with self.lock:
                    campaign_info = self.active_campaigns.get(campaign_id)
                    if not campaign_info or campaign_info['status'] != CampaignStatus.ACTIVE:
                        continue
                
                # Run optimization step
                success = self._optimize_campaign(campaign_id)
                
                if success:
                    campaigns_optimized += 1
                    with self.lock:
                        if campaign_id in self.active_campaigns:
                            self.active_campaigns[campaign_id]['last_optimization'] = datetime.now()
                            self.active_campaigns[campaign_id]['optimization_count'] += 1
                
            except Exception as e:
                logger.error(f"Error optimizing campaign {campaign_id}: {str(e)}")
                with self.lock:
                    if campaign_id in self.active_campaigns:
                        self.active_campaigns[campaign_id]['status'] = CampaignStatus.ERROR
        
        return campaigns_optimized
    
    def _optimize_campaign(self, campaign_id: int) -> bool:
        """
        Run one optimization step for a campaign.
        
        Args:
            campaign_id: Campaign ID
        
        Returns:
            True if successful
        """
        try:
            # Get or create runner
            runner = self._get_or_create_runner(campaign_id)
            if not runner:
                return False
            
            # Check if budget exhausted
            if runner.agent.is_budget_exhausted():
                logger.info(f"Campaign {campaign_id} budget exhausted")
                with self.lock:
                    if campaign_id in self.active_campaigns:
                        self.active_campaigns[campaign_id]['status'] = CampaignStatus.COMPLETED
                return False
            
            # Generate context if using contextual bandit
            context = None
            if runner.use_contextual:
                # In real system, get context from current request/user data
                # For now, generate synthetic context
                import random
                from datetime import datetime, timedelta
                user_segments = [
                    {'age': 28, 'gender': 'male', 'location': 'us', 'device_type': 'mobile'},
                    {'age': 35, 'gender': 'female', 'location': 'eu', 'device_type': 'desktop'},
                ]
                context = {
                    'user_data': random.choice(user_segments),
                    'timestamp': datetime.now()
                }
            
            # Select arm
            if runner.use_contextual and hasattr(runner.agent, 'select_arm'):
                arm = runner.agent.select_arm(context=context)
            else:
                arm = runner.agent.select_arm()
            
            if not arm:
                logger.warning(f"No arm selected for campaign {campaign_id}")
                return False
            
            # Get impressions per round from config
            impressions = runner.config.get('impressions_per_round', 100)
            
            # Calculate spend amount
            arm_key = str(arm)
            allocated_budget = runner.agent.current_allocation.get(arm_key, 0)
            spend_amount = min(
                allocated_budget * 0.1, 
                runner.agent.total_budget * 0.05
            )
            
            # Step environment
            result = runner.environment.step(
                arm, 
                impressions=impressions, 
                spend_amount=spend_amount, 
                context=context
            )
            
            # Update agent
            if runner.use_contextual and hasattr(runner.agent, 'update'):
                runner.agent.update(arm, result, context=context)
            else:
                runner.agent.update(arm, result)
            
            # Track holdout metrics for IncrementalityAwareBandit
            if isinstance(runner.agent, IncrementalityAwareBandit):
                self._record_holdout_metrics(campaign_id, runner, result, impressions)

            # Detect allocation changes and push budgets / log changes
            self._handle_allocation_changes(campaign_id, runner, result)

            # Save agent state periodically (every 10 optimizations)
            with self.lock:
                opt_count = self.active_campaigns.get(campaign_id, {}).get('optimization_count', 0)
                if opt_count % 10 == 0:
                    self._save_agent_state(runner, campaign_id)

            return True
            
        except Exception as e:
            logger.error(f"Error in optimization step for campaign {campaign_id}: {str(e)}")
            return False
    
    def _record_holdout_metrics(self, campaign_id: int, runner: AdOptimizationRunner, 
                                 result: dict, impressions: int):
        """
        Record holdout and treatment metrics for incrementality experiments.
        
        Automatically records metrics to running incrementality experiments
        when using IncrementalityAwareBandit.
        
        Args:
            campaign_id: Campaign ID
            runner: AdOptimizationRunner instance
            result: Result from environment step
            impressions: Number of impressions in this round
        """
        try:
            agent = runner.agent
            if not isinstance(agent, IncrementalityAwareBandit):
                return
            
            # Get running experiments for this campaign
            experiments = get_experiments_by_campaign(campaign_id, status='running')
            if not experiments:
                return
            
            holdout_pct = agent.holdout_percentage
            
            # Calculate holdout (control) metrics - no ad spend, organic only
            # These represent users who were not shown ads
            holdout_users = int(impressions * holdout_pct)
            holdout_cvr = agent.holdout_arm.get_baseline_cvr() if agent.holdout_arm.organic_users > 0 else 0.02
            holdout_conversions = int(holdout_users * holdout_cvr)
            holdout_revenue = holdout_conversions * result.get('revenue_per_conversion', 50.0)
            
            # Treatment metrics from the actual optimization
            treatment_users = impressions - holdout_users
            treatment_conversions = result.get('conversions', 0)
            treatment_revenue = result.get('revenue', 0)
            treatment_spend = result.get('spend', 0)
            treatment_clicks = result.get('clicks', 0)
            
            # Record to agent's holdout arm
            agent.record_holdout_metrics(
                users=holdout_users,
                conversions=holdout_conversions,
                revenue=holdout_revenue
            )
            
            # Record to database for each running experiment
            from datetime import datetime
            now = datetime.utcnow()
            
            for experiment in experiments:
                try:
                    record_incrementality_metric(
                        experiment_id=experiment.id,
                        date=now,
                        treatment_users=treatment_users,
                        treatment_impressions=treatment_users,  # Simplification: users ≈ impressions
                        treatment_clicks=treatment_clicks,
                        treatment_conversions=treatment_conversions,
                        treatment_revenue=treatment_revenue,
                        treatment_spend=treatment_spend,
                        control_users=holdout_users,
                        control_conversions=holdout_conversions,
                        control_revenue=holdout_revenue
                    )
                except Exception as e:
                    logger.warning(f"Failed to record metric for experiment {experiment.id}: {e}")
            
            logger.debug(f"Recorded holdout metrics for campaign {campaign_id}: "
                        f"treatment={treatment_users} users, control={holdout_users} users")
                        
        except Exception as e:
            logger.warning(f"Error recording holdout metrics for campaign {campaign_id}: {e}")
    
    def _handle_allocation_changes(self, campaign_id: int, runner: AdOptimizationRunner, result: dict):
        """
        Detect allocation changes, push budgets to platforms, and log decisions.

        Compares current allocation with previous allocation. For arms that changed
        more than the threshold, pushes budget changes and logs the allocation change
        with the change tracker for explainability.
        """
        try:
            current_allocation = dict(runner.agent.current_allocation)
            prev_allocation = self.previous_allocations.get(campaign_id, {})

            # Detect significant changes
            changed_arms = {}
            for arm_key, new_alloc in current_allocation.items():
                old_alloc = prev_allocation.get(arm_key, 0.0)
                if abs(new_alloc - old_alloc) > self.allocation_change_threshold:
                    changed_arms[arm_key] = {'old': old_alloc, 'new': new_alloc}

            if not changed_arms:
                # Store current as previous for next comparison
                self.previous_allocations[campaign_id] = current_allocation
                return

            # Push budget changes to ad platforms
            if self.budget_push_enabled:
                from src.bandit_ads.api_connectors import push_budget_to_platform
                total_budget = runner.agent.total_budget
                for arm_key, change in changed_arms.items():
                    # Find the arm object
                    arm_obj = next((a for a in runner.agent.arms if str(a) == arm_key), None)
                    if arm_obj:
                        daily_budget = change['new'] * total_budget
                        push_budget_to_platform(
                            arm_obj, daily_budget,
                            dry_run=self.budget_push_dry_run
                        )

            # Log allocation changes for explainability
            if self.change_tracker:
                for arm_key, change in changed_arms.items():
                    try:
                        # Build optimizer state snapshot
                        optimizer_state = {
                            'alpha': runner.agent.alpha.get(arm_key, 1.0),
                            'beta': runner.agent.beta.get(arm_key, 1.0),
                            'risk_score': runner.agent.arm_risk_scores.get(arm_key, 0.0),
                            'trials': runner.agent.arm_trials.get(arm_key, 0)
                        }

                        self.change_tracker.log_allocation_change(
                            campaign_id=campaign_id,
                            arm_id=arm_key,
                            old_allocation=change['old'],
                            new_allocation=change['new'],
                            change_reason='optimization_cycle',
                            factors={'result': {k: v for k, v in result.items() if isinstance(v, (int, float, str))}},
                            optimizer_state=optimizer_state,
                            change_type='auto'
                        )
                    except Exception as e:
                        logger.debug(f"Failed to log allocation change for {arm_key}: {e}")

            # Store current as previous for next comparison
            self.previous_allocations[campaign_id] = current_allocation

            logger.info(f"Campaign {campaign_id}: {len(changed_arms)} allocation changes detected")

        except Exception as e:
            logger.warning(f"Error handling allocation changes for campaign {campaign_id}: {e}")

    def _save_agent_state(self, runner: AdOptimizationRunner, campaign_id: int):
        """Save agent state to database."""
        try:
            agent = runner.agent
            arms = agent.arms
            
            for arm in arms:
                arm_key = str(arm)
                
                # Get or create arm in database
                arms_db = get_arms_by_campaign(campaign_id)
                arm_db = next((a for a in arms_db if str(a) == arm_key), None)
                
                if not arm_db:
                    # Would need to create arm - skip for now
                    continue
                
                # Prepare state data
                state_data = {
                    'campaign_id': campaign_id,
                    'arm_id': arm_db.id,
                    'alpha': agent.alpha.get(arm_key, 1.0),
                    'beta': agent.beta.get(arm_key, 1.0),
                    'spending': agent.arm_spending.get(arm_key, 0.0),
                    'impressions': agent.arm_impressions.get(arm_key, 0),
                    'rewards': agent.arm_rewards.get(arm_key, 0.0),
                    'reward_variance': agent.arm_reward_variance.get(arm_key, 0.0),
                    'trials': agent.arm_trials.get(arm_key, 0),
                    'risk_score': agent.arm_risk_scores.get(arm_key, 0.0)
                }
                
                # Save contextual state if applicable
                if runner.use_contextual and hasattr(agent, 'arm_theta'):
                    contextual_state = {
                        'arm_theta': agent.arm_theta.get(arm_key),
                        'arm_A': agent.arm_A.get(arm_key),
                        'arm_b': agent.arm_b.get(arm_key)
                    }
                    state_data['contextual_state'] = json.dumps(contextual_state)
                
                # Update or create state using AgentStateUpdate model
                from src.bandit_ads.models import AgentStateUpdate
                state_update = AgentStateUpdate(
                    campaign_id=campaign_id,
                    arm_id=arm_db.id,
                    **state_data
                )
                update_agent_state(state_update)
            
            logger.debug(f"Saved agent state for campaign {campaign_id}")
            
        except Exception as e:
            logger.error(f"Error saving agent state: {str(e)}")
    
    def _restore_agent_state(self, runner: AdOptimizationRunner, campaign_id: int):
        """Restore agent state from database."""
        try:
            agent = runner.agent
            arms = agent.arms
            
            for arm in arms:
                arm_key = str(arm)
                
                # Get arm from database
                arms_db = get_arms_by_campaign(campaign_id)
                arm_db = next((a for a in arms_db if str(a) == arm_key), None)
                
                if not arm_db:
                    continue
                
                # Get saved state
                state = get_agent_state(campaign_id, arm_db.id)
                if not state:
                    continue
                
                # Restore state
                agent.alpha[arm_key] = state.alpha
                agent.beta[arm_key] = state.beta
                agent.arm_spending[arm_key] = state.spending
                agent.arm_impressions[arm_key] = state.impressions
                agent.arm_rewards[arm_key] = state.rewards
                agent.arm_reward_variance[arm_key] = state.reward_variance
                agent.arm_trials[arm_key] = state.trials
                agent.arm_risk_scores[arm_key] = state.risk_score
                
                # Restore contextual state if applicable
                if runner.use_contextual and state.contextual_state:
                    try:
                        contextual_state = json.loads(state.contextual_state)
                        if hasattr(agent, 'arm_theta'):
                            agent.arm_theta[arm_key] = contextual_state.get('arm_theta', [])
                            agent.arm_A[arm_key] = contextual_state.get('arm_A', {})
                            agent.arm_b[arm_key] = contextual_state.get('arm_b', [])
                    except Exception as e:
                        logger.warning(f"Error restoring contextual state: {str(e)}")
            
            logger.info(f"Restored agent state for campaign {campaign_id}")
            
        except Exception as e:
            logger.error(f"Error restoring agent state: {str(e)}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status and statistics."""
        with self.lock:
            return {
                'running': self.running,
                'optimization_interval_minutes': self.optimization_interval,
                'active_campaigns': len(self.active_campaigns),
                'campaigns': [
                    {
                        'id': info['id'],
                        'name': info['name'],
                        'status': info['status'].value,
                        'last_optimization': info['last_optimization'].isoformat() if info['last_optimization'] else None,
                        'optimization_count': info['optimization_count']
                    }
                    for info in self.active_campaigns.values()
                ],
                'statistics': self.stats.copy()
            }
    
    def get_campaign_status(self, campaign_id: int) -> Optional[Dict[str, Any]]:
        """Get status for a specific campaign."""
        with self.lock:
            if campaign_id not in self.active_campaigns:
                return None
            
            info = self.active_campaigns[campaign_id]
            runner = self.campaign_runners.get(campaign_id)
            
            status = {
                'id': info['id'],
                'name': info['name'],
                'status': info['status'].value,
                'last_optimization': info['last_optimization'].isoformat() if info['last_optimization'] else None,
                'optimization_count': info['optimization_count']
            }
            
            if runner and runner.agent:
                metrics = runner.agent.get_performance_metrics()
                status['performance'] = {
                    'total_spent': metrics['total_spent'],
                    'total_budget': metrics['total_budget'],
                    'budget_utilization': metrics['budget_utilization'],
                    'total_roas': metrics['total_roas']
                }
            
            return status


# Global service instance
_service_instance: Optional[ContinuousOptimizationService] = None


def get_optimization_service(
    config_manager: Optional[ConfigManager] = None,
    optimization_interval_minutes: int = 15
) -> ContinuousOptimizationService:
    """
    Get or create the global optimization service instance.
    
    Args:
        config_manager: Configuration manager
        optimization_interval_minutes: Optimization interval
    
    Returns:
        ContinuousOptimizationService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = ContinuousOptimizationService(
            config_manager=config_manager,
            optimization_interval_minutes=optimization_interval_minutes
        )
    return _service_instance
