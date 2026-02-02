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
    get_agent_state, update_agent_state
)
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
        
        # Statistics
        self.stats = {
            'total_cycles': 0,
            'successful_cycles': 0,
            'failed_cycles': 0,
            'last_cycle_time': None,
            'campaigns_optimized': 0
        }
        
        logger.info(f"Optimization service initialized (interval: {optimization_interval_minutes} min)")
    
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
        """Load active campaigns from database."""
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            from src.bandit_ads.database import Campaign
            campaigns = session.query(Campaign).filter(
                Campaign.status == 'active'
            ).all()
            
            for campaign in campaigns:
                self.active_campaigns[campaign.id] = {
                    'id': campaign.id,
                    'name': campaign.name,
                    'budget': campaign.budget,
                    'status': CampaignStatus.ACTIVE,
                    'last_optimization': None,
                    'optimization_count': 0
                }
        
        logger.info(f"Loaded {len(self.active_campaigns)} active campaigns")
    
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
            with self.lock:
                runner = self.campaign_runners.get(campaign_id)
                if not runner:
                    # Try to load campaign
                    campaign = get_campaign(campaign_id)
                    if not campaign:
                        return False
                    
                    # Create runner (would need campaign config from database)
                    # For now, skip if runner doesn't exist
                    logger.warning(f"Runner not found for campaign {campaign_id}")
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
            
            # Save agent state periodically (every 10 optimizations)
            with self.lock:
                opt_count = self.active_campaigns.get(campaign_id, {}).get('optimization_count', 0)
                if opt_count % 10 == 0:
                    self._save_agent_state(runner, campaign_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error in optimization step for campaign {campaign_id}: {str(e)}")
            return False
    
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
