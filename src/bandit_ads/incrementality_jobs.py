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
    Check for experiments that have passed their end date and complete them.
    
    This job should be run periodically (e.g., hourly) to automatically
    calculate final results for experiments that have finished.
    
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
                else:
                    logger.warning(f"Failed to complete experiment {experiment.id}")
            except Exception as e:
                logger.error(f"Error completing experiment {experiment.id}: {e}")
        
        logger.info(f"Completed {completed_count}/{len(expired)} expired experiments")
        return completed_count
        
    except Exception as e:
        logger.error(f"Error in check_and_complete_expired_experiments: {e}")
        return 0


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
