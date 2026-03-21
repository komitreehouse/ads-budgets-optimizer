"""
Incrementality Testing Background Jobs

Scheduled jobs for managing incrementality experiments:
- Auto-completing experiments when duration ends
- Syncing platform-native experiment results
"""

from typing import Optional
from datetime import datetime

from src.bandit_ads.utils import get_logger
from src.bandit_ads.db_helpers import (
    get_expired_experiments,
    auto_complete_experiment,
    get_all_experiments
)

logger = get_logger('incrementality_jobs')


def check_and_complete_expired_experiments() -> int:
    """
    Check for experiments that have passed their end date, complete them,
    and automatically apply significant results to the bandit agent.

    This closes the incrementality feedback loop: experiment results
    directly update Thompson Sampling priors without manual intervention.

    Returns:
        Number of experiments completed
    """
    logger.info("Checking for expired experiments...")

    try:
        expired = get_expired_experiments()

        if not expired:
            logger.info("No expired experiments found")
            return 0

        logger.info(f"Found {len(expired)} expired experiments to complete")

        completed_count = 0
        for experiment in expired:
            try:
                logger.info(f"Auto-completing experiment {experiment.id}: {experiment.name}")
                success = auto_complete_experiment(experiment.id)
                if success:
                    completed_count += 1
                    logger.info(f"Successfully completed experiment {experiment.id}")

                    # Auto-apply significant results to the bandit
                    _auto_apply_to_bandit(experiment.id, experiment.campaign_id)
                else:
                    logger.warning(f"Failed to complete experiment {experiment.id}")
            except Exception as e:
                logger.error(f"Error completing experiment {experiment.id}: {e}")

        logger.info(f"Completed {completed_count}/{len(expired)} expired experiments")
        return completed_count

    except Exception as e:
        logger.error(f"Error in check_and_complete_expired_experiments: {e}")
        return 0


def _auto_apply_to_bandit(experiment_id: int, campaign_id: int):
    """
    Automatically apply completed experiment results to the bandit agent.

    When an experiment is significant, calls incorporate_incrementality()
    on the campaign's IncrementalityAwareBandit to update priors.
    """
    try:
        from src.bandit_ads.database import get_db_manager, IncrementalityExperiment
        from src.bandit_ads.optimization_service import get_optimization_service
        from src.bandit_ads.agent import IncrementalityAwareBandit

        # Load the completed experiment from DB
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            experiment = session.query(IncrementalityExperiment).filter(
                IncrementalityExperiment.id == experiment_id
            ).first()

            if not experiment:
                return

            if not experiment.is_significant:
                logger.info(
                    f"Experiment {experiment_id} not significant "
                    f"(p={experiment.p_value}), skipping bandit update"
                )
                return

            # Build experiment result dict for incorporate_incrementality
            experiment_result = {
                'is_significant': True,
                'incremental_roas': experiment.incremental_roas or 0,
                'observed_roas': experiment.observed_roas or 0,
                'lift_percent': experiment.lift_percent or 0,
                'p_value': experiment.p_value or 1.0,
            }

        # Get the optimization service and campaign runner
        service = get_optimization_service()
        runner = service.campaign_runners.get(campaign_id)

        if not runner:
            logger.warning(
                f"No runner for campaign {campaign_id}, cannot auto-apply "
                f"incrementality results from experiment {experiment_id}"
            )
            return

        if not isinstance(runner.agent, IncrementalityAwareBandit):
            logger.info(f"Campaign {campaign_id} agent is not IncrementalityAwareBandit, skipping")
            return

        # Apply to all arms (experiment covers the whole campaign)
        applied_count = 0
        for arm in runner.agent.arms:
            arm_key = str(arm)
            try:
                runner.agent.incorporate_incrementality(arm_key, experiment_result)
                applied_count += 1
            except Exception as e:
                logger.warning(f"Failed to apply incrementality to arm {arm_key}: {e}")

        logger.info(
            f"Auto-applied incrementality results from experiment {experiment_id} "
            f"to {applied_count} arms in campaign {campaign_id} "
            f"(lift={experiment_result['lift_percent']:.1f}%, "
            f"iROAS={experiment_result['incremental_roas']:.2f})"
        )

    except Exception as e:
        logger.error(f"Error auto-applying incrementality for experiment {experiment_id}: {e}")


def sync_platform_native_experiments() -> int:
    """
    Sync results from platform-native incrementality studies.
    
    Checks for platform_native experiments that are running and attempts
    to fetch their results from the respective ad platforms.
    
    Returns:
        Number of experiments synced
    """
    logger.info("Syncing platform-native experiment results...")
    
    try:
        from src.bandit_ads.api_connectors import IncrementalityConnector
        
        experiments = get_all_experiments(
            status='running',
            experiment_type='platform_native'
        )
        
        if not experiments:
            logger.info("No platform-native experiments to sync")
            return 0
        
        synced_count = 0
        connector = IncrementalityConnector()
        
        for experiment in experiments:
            if not experiment.platform or not experiment.platform_study_id:
                continue
            
            try:
                results = connector.get_incrementality_results(
                    platform=experiment.platform,
                    study_id=experiment.platform_study_id
                )
                
                if results and results.get('status') == 'completed':
                    from src.bandit_ads.db_helpers import update_experiment_results
                    
                    update_experiment_results(
                        experiment_id=experiment.id,
                        lift_percent=results.get('lift_percent', 0),
                        confidence_lower=results.get('confidence_lower', 0),
                        confidence_upper=results.get('confidence_upper', 0),
                        p_value=results.get('p_value', 1.0),
                        is_significant=results.get('is_significant', False),
                        incremental_roas=results.get('incremental_roas', 0),
                        observed_roas=results.get('observed_roas', 0),
                        incremental_revenue=results.get('incremental_revenue', 0),
                        incremental_conversions=results.get('incremental_conversions', 0),
                        treatment_users=results.get('treatment_users', 0),
                        control_users=results.get('control_users', 0),
                        treatment_conversions=results.get('treatment_conversions', 0),
                        control_conversions=results.get('control_conversions', 0),
                        treatment_revenue=results.get('treatment_revenue', 0),
                        control_revenue=results.get('control_revenue', 0),
                        treatment_spend=results.get('treatment_spend', 0)
                    )
                    synced_count += 1
                    logger.info(f"Synced results for experiment {experiment.id}")
                    
            except Exception as e:
                logger.warning(f"Could not sync experiment {experiment.id}: {e}")
        
        logger.info(f"Synced {synced_count} platform-native experiments")
        return synced_count
        
    except ImportError:
        logger.warning("IncrementalityConnector not available, skipping platform sync")
        return 0
    except Exception as e:
        logger.error(f"Error in sync_platform_native_experiments: {e}")
        return 0


def register_incrementality_jobs(scheduler: 'DataScheduler'):
    """
    Register all incrementality-related scheduled jobs.
    
    Args:
        scheduler: DataScheduler instance to register jobs with
    """
    logger.info("Registering incrementality background jobs...")
    
    scheduler.add_hourly_job(
        func=check_and_complete_expired_experiments,
        job_id='incrementality_auto_complete',
        minute=5
    )
    
    scheduler.add_interval_job(
        func=sync_platform_native_experiments,
        job_id='incrementality_platform_sync',
        hours=4
    )
    
    logger.info("Incrementality jobs registered successfully")
