"""
Incrementality Testing API endpoints.

Provides REST endpoints for managing incrementality experiments.
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel

from src.bandit_ads.database import get_db_manager
from src.bandit_ads.db_helpers import (
    create_incrementality_experiment,
    get_incrementality_experiment,
    get_experiments_by_campaign,
    get_all_experiments,
    update_experiment_status,
    update_experiment_results,
    record_incrementality_metric,
    get_experiment_metrics,
    calculate_experiment_results
)
from src.bandit_ads.utils import get_logger

logger = get_logger('api.incrementality')
router = APIRouter()


class ExperimentCreate(BaseModel):
    """Model for creating an incrementality experiment."""
    campaign_id: int
    name: str
    experiment_type: str  # 'holdout', 'geo_lift', 'platform_native'
    holdout_percentage: float = 0.10
    duration_days: int = 28
    treatment_markets: Optional[List[str]] = None
    control_markets: Optional[List[str]] = None
    platform: Optional[str] = None
    platform_study_id: Optional[str] = None
    notes: Optional[str] = None


class MetricRecord(BaseModel):
    """Model for recording daily metrics."""
    date: str  # ISO format
    treatment_users: int
    treatment_impressions: int
    treatment_clicks: int
    treatment_conversions: int
    treatment_revenue: float
    treatment_spend: float
    control_users: int
    control_conversions: int
    control_revenue: float


class ApplyTobanditRequest(BaseModel):
    """Model for applying results to bandit."""
    experiment_id: int
    campaign_id: int


@router.get("/experiments")
async def list_experiments(
    status: Optional[str] = Query(None, description="Filter by status"),
    experiment_type: Optional[str] = Query(None, description="Filter by type"),
    campaign_id: Optional[int] = Query(None, description="Filter by campaign"),
    limit: int = Query(100, description="Maximum results")
):
    """
    Get list of incrementality experiments.
    
    Optionally filter by status, type, or campaign.
    """
    try:
        if campaign_id:
            experiments = get_experiments_by_campaign(campaign_id, status=status)
        else:
            experiments = get_all_experiments(status=status, experiment_type=experiment_type, limit=limit)
        
        result = []
        for exp in experiments:
            exp_dict = {
                'id': exp.id,
                'campaign_id': exp.campaign_id,
                'name': exp.name,
                'experiment_type': exp.experiment_type,
                'holdout_percentage': exp.holdout_percentage,
                'treatment_markets': exp.treatment_markets,
                'control_markets': exp.control_markets,
                'platform': exp.platform,
                'platform_study_id': exp.platform_study_id,
                'start_date': exp.start_date.isoformat() if exp.start_date else None,
                'end_date': exp.end_date.isoformat() if exp.end_date else None,
                'status': exp.status,
                'lift_percent': exp.lift_percent,
                'confidence_lower': exp.confidence_lower,
                'confidence_upper': exp.confidence_upper,
                'p_value': exp.p_value,
                'is_significant': exp.is_significant,
                'incremental_roas': exp.incremental_roas,
                'observed_roas': exp.observed_roas,
                'incremental_revenue': exp.incremental_revenue,
                'incremental_conversions': exp.incremental_conversions,
                'treatment_users': exp.treatment_users,
                'control_users': exp.control_users,
                'treatment_conversions': exp.treatment_conversions,
                'control_conversions': exp.control_conversions,
                'treatment_revenue': exp.treatment_revenue,
                'control_revenue': exp.control_revenue,
                'treatment_spend': exp.treatment_spend,
                'created_at': exp.created_at.isoformat() if exp.created_at else None,
                'notes': exp.notes
            }
            
            # Add computed fields
            if exp.start_date:
                exp_dict['days_running'] = (datetime.now() - exp.start_date).days
                exp_dict['duration_days'] = (exp.end_date - exp.start_date).days if exp.end_date else 28
            
            if exp.confidence_lower is not None and exp.confidence_upper is not None:
                exp_dict['confidence_interval'] = (exp.confidence_lower, exp.confidence_upper)
            
            if exp.incremental_roas and exp.observed_roas and exp.observed_roas > 0:
                exp_dict['roas_inflation'] = ((exp.observed_roas / exp.incremental_roas) - 1) * 100 if exp.incremental_roas > 0 else 0
            
            result.append(exp_dict)
        
        return result
        
    except Exception as e:
        logger.error(f"Error listing experiments: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/experiments")
async def create_experiment(experiment: ExperimentCreate):
    """Create a new incrementality experiment."""
    try:
        exp = create_incrementality_experiment(
            campaign_id=experiment.campaign_id,
            name=experiment.name,
            experiment_type=experiment.experiment_type,
            start_date=datetime.now(),
            holdout_percentage=experiment.holdout_percentage,
            duration_days=experiment.duration_days,
            treatment_markets=experiment.treatment_markets,
            control_markets=experiment.control_markets,
            platform=experiment.platform,
            platform_study_id=experiment.platform_study_id,
            notes=experiment.notes
        )
        
        return {
            'id': exp.id,
            'name': exp.name,
            'status': exp.status,
            'created': True
        }
        
    except Exception as e:
        logger.error(f"Error creating experiment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: int):
    """Get details for a specific experiment."""
    try:
        exp = get_incrementality_experiment(experiment_id)
        
        if not exp:
            raise HTTPException(status_code=404, detail="Experiment not found")
        
        result = {
            'id': exp.id,
            'campaign_id': exp.campaign_id,
            'name': exp.name,
            'experiment_type': exp.experiment_type,
            'holdout_percentage': exp.holdout_percentage,
            'treatment_markets': exp.treatment_markets,
            'control_markets': exp.control_markets,
            'platform': exp.platform,
            'platform_study_id': exp.platform_study_id,
            'start_date': exp.start_date.isoformat() if exp.start_date else None,
            'end_date': exp.end_date.isoformat() if exp.end_date else None,
            'status': exp.status,
            'lift_percent': exp.lift_percent,
            'confidence_interval': (exp.confidence_lower, exp.confidence_upper) if exp.confidence_lower else None,
            'p_value': exp.p_value,
            'is_significant': exp.is_significant,
            'incremental_roas': exp.incremental_roas,
            'observed_roas': exp.observed_roas,
            'incremental_revenue': exp.incremental_revenue,
            'treatment_users': exp.treatment_users,
            'control_users': exp.control_users,
            'treatment_spend': exp.treatment_spend,
            'notes': exp.notes
        }
        
        if exp.start_date:
            result['days_running'] = (datetime.now() - exp.start_date).days
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting experiment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/experiments/{experiment_id}/status")
async def update_status(
    experiment_id: int,
    status: str = Body(..., embed=True)
):
    """Update experiment status."""
    try:
        valid_statuses = ['designing', 'running', 'completed', 'aborted']
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {valid_statuses}"
            )
        
        success = update_experiment_status(experiment_id, status)
        
        if not success:
            raise HTTPException(status_code=404, detail="Experiment not found")
        
        return {'success': True, 'status': status}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/experiments/{experiment_id}/metrics")
async def record_metric(experiment_id: int, metric: MetricRecord):
    """Record daily metrics for an experiment."""
    try:
        date = datetime.fromisoformat(metric.date)
        
        record = record_incrementality_metric(
            experiment_id=experiment_id,
            date=date,
            treatment_users=metric.treatment_users,
            treatment_impressions=metric.treatment_impressions,
            treatment_clicks=metric.treatment_clicks,
            treatment_conversions=metric.treatment_conversions,
            treatment_revenue=metric.treatment_revenue,
            treatment_spend=metric.treatment_spend,
            control_users=metric.control_users,
            control_conversions=metric.control_conversions,
            control_revenue=metric.control_revenue
        )
        
        return {
            'id': record.id,
            'date': date.isoformat(),
            'daily_lift_percent': record.daily_lift_percent,
            'recorded': True
        }
        
    except Exception as e:
        logger.error(f"Error recording metric: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/experiments/{experiment_id}/metrics")
async def get_metrics(
    experiment_id: int,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """Get daily metrics for an experiment."""
    try:
        start = datetime.fromisoformat(start_date) if start_date else None
        end = datetime.fromisoformat(end_date) if end_date else None
        
        metrics = get_experiment_metrics(experiment_id, start_date=start, end_date=end)
        
        return [
            {
                'date': m.date.isoformat(),
                'treatment_users': m.treatment_users,
                'treatment_impressions': m.treatment_impressions,
                'treatment_clicks': m.treatment_clicks,
                'treatment_conversions': m.treatment_conversions,
                'treatment_revenue': m.treatment_revenue,
                'treatment_spend': m.treatment_spend,
                'control_users': m.control_users,
                'control_conversions': m.control_conversions,
                'control_revenue': m.control_revenue,
                'treatment_cvr': m.treatment_cvr,
                'control_cvr': m.control_cvr,
                'daily_lift_percent': m.daily_lift_percent,
                'daily_incremental_roas': m.daily_incremental_roas,
                'cumulative_treatment_users': m.cumulative_treatment_users,
                'cumulative_control_users': m.cumulative_control_users
            }
            for m in metrics
        ]
        
    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/experiments/{experiment_id}/complete")
async def complete_experiment(experiment_id: int):
    """
    Complete an experiment and calculate final results.
    
    Calculates lift, confidence intervals, and iROAS from recorded metrics.
    """
    try:
        # Calculate results from metrics
        results = calculate_experiment_results(experiment_id)
        
        if not results:
            raise HTTPException(
                status_code=400,
                detail="Insufficient data to calculate results"
            )
        
        # Update experiment with results
        success = update_experiment_results(
            experiment_id=experiment_id,
            **results
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Experiment not found")
        
        return {
            'success': True,
            'results': results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing experiment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply")
async def apply_to_bandit(request: ApplyTobanditRequest):
    """
    Apply incrementality results to bandit priors.
    
    This updates the Thompson Sampling agent's alpha/beta distributions
    based on the incrementality experiment results.
    """
    try:
        # Get experiment results
        exp = get_incrementality_experiment(request.experiment_id)
        
        if not exp:
            raise HTTPException(status_code=404, detail="Experiment not found")
        
        if exp.status != 'completed':
            raise HTTPException(
                status_code=400,
                detail="Experiment must be completed before applying results"
            )
        
        if not exp.is_significant:
            logger.warning(
                f"Applying non-significant results for experiment {request.experiment_id}"
            )
        
        # Get the optimization service and update bandit
        from src.bandit_ads.optimization_service import get_optimization_service
        
        service = get_optimization_service()
        runner = service.campaign_runners.get(request.campaign_id)
        
        if not runner:
            raise HTTPException(
                status_code=404,
                detail=f"Campaign {request.campaign_id} not found in optimizer"
            )
        
        # Check if using IncrementalityAwareBandit
        from src.bandit_ads.agent import IncrementalityAwareBandit
        
        if isinstance(runner.agent, IncrementalityAwareBandit):
            # Prepare experiment results
            experiment_result = {
                'lift_percent': exp.lift_percent,
                'incremental_roas': exp.incremental_roas,
                'observed_roas': exp.observed_roas,
                'is_significant': exp.is_significant,
                'confidence_interval': (exp.confidence_lower, exp.confidence_upper)
            }
            
            # Apply to all arms (in production, you'd apply per-arm results)
            for arm in runner.agent.arms:
                arm_key = str(arm)
                runner.agent.incorporate_incrementality(arm_key, experiment_result)
            
            logger.info(
                f"Applied incrementality results to campaign {request.campaign_id}: "
                f"lift={exp.lift_percent:.1f}%, iROAS={exp.incremental_roas:.2f}"
            )
            
            return {
                'success': True,
                'message': 'Incrementality results applied to bandit priors',
                'lift_percent': exp.lift_percent,
                'incremental_roas': exp.incremental_roas
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="Campaign is not using IncrementalityAwareBandit. "
                       "Upgrade the agent type to apply incrementality results."
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying to bandit: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sample-size")
async def calculate_sample_size(
    baseline_cvr: float = Query(..., description="Baseline conversion rate (0-1)"),
    minimum_detectable_effect: float = Query(..., description="Minimum lift to detect (0-1)"),
    power: float = Query(0.80, description="Statistical power"),
    significance_level: float = Query(0.05, description="Alpha level")
):
    """Calculate required sample size for an experiment."""
    try:
        from src.bandit_ads.incrementality import calculate_sample_size as calc_sample
        
        result = calc_sample(
            baseline_cvr=baseline_cvr,
            minimum_detectable_effect=minimum_detectable_effect,
            power=power,
            significance_level=significance_level
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error calculating sample size: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
