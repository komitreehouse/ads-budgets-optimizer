"""
Helper functions for database operations.

Provides convenient functions for common database operations.
"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import func, and_, desc
from sqlalchemy.orm import Session

from src.bandit_ads.database import (
    Campaign, Arm, Metric, AgentState, APILog,
    get_db_manager
)
from src.bandit_ads.models import (
    CampaignCreate, ArmCreate, MetricCreate, AgentStateUpdate
)
from src.bandit_ads.utils import get_logger

logger = get_logger('db_helpers')


def create_campaign(campaign_data: CampaignCreate) -> Campaign:
    """Create a new campaign."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        campaign = Campaign(
            name=campaign_data.name,
            budget=campaign_data.budget,
            start_date=campaign_data.start_date,
            end_date=campaign_data.end_date,
            status=campaign_data.status
        )
        session.add(campaign)
        session.flush()
        logger.info(f"Created campaign: {campaign.name} (ID: {campaign.id})")
        return campaign


def get_campaign(campaign_id: int) -> Optional[Campaign]:
    """Get a campaign by ID."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        return session.query(Campaign).filter(Campaign.id == campaign_id).first()


def get_campaign_by_name(name: str) -> Optional[Campaign]:
    """Get a campaign by name."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        return session.query(Campaign).filter(Campaign.name == name).first()


def create_arm(arm_data: ArmCreate) -> Arm:
    """Create a new arm."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        # Convert platform_entity_ids dict to JSON string if provided
        platform_entity_ids_json = None
        if arm_data.platform_entity_ids:
            platform_entity_ids_json = json.dumps(arm_data.platform_entity_ids)
        
        arm = Arm(
            campaign_id=arm_data.campaign_id,
            platform=arm_data.platform,
            channel=arm_data.channel,
            creative=arm_data.creative,
            bid=arm_data.bid,
            platform_entity_ids=platform_entity_ids_json
        )
        session.add(arm)
        session.flush()
        logger.debug(f"Created arm: {arm}")
        return arm


def get_arms_by_campaign(campaign_id: int) -> List[Arm]:
    """Get all arms for a campaign."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        return session.query(Arm).filter(Arm.campaign_id == campaign_id).all()


def get_arm_by_attributes(campaign_id: int, platform: str, channel: str, 
                         creative: str, bid: float) -> Optional[Arm]:
    """Get an arm by its attributes."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        return session.query(Arm).filter(
            and_(
                Arm.campaign_id == campaign_id,
                Arm.platform == platform,
                Arm.channel == channel,
                Arm.creative == creative,
                Arm.bid == bid
            )
        ).first()


def get_arm(arm_id: int) -> Optional[Arm]:
    """Get an arm by ID."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        return session.query(Arm).filter(Arm.id == arm_id).first()


def get_arm_platform_entity_ids(arm_id: int) -> Optional[Dict[str, Any]]:
    """Get platform-specific entity IDs for an arm."""
    arm = get_arm(arm_id)
    if arm and arm.platform_entity_ids:
        try:
            return json.loads(arm.platform_entity_ids)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Invalid platform_entity_ids JSON for arm {arm_id}")
            return None
    return None


def update_arm_platform_entity_ids(arm_id: int, platform_entity_ids: Dict[str, Any]) -> bool:
    """Update platform-specific entity IDs for an arm."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        arm = session.query(Arm).filter(Arm.id == arm_id).first()
        if arm:
            arm.platform_entity_ids = json.dumps(platform_entity_ids)
            session.flush()
            logger.info(f"Updated platform_entity_ids for arm {arm_id}")
            return True
        return False


def update_arm_bid(arm_id: int, new_bid: float) -> bool:
    """Update bid for an arm in the database."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        arm = session.query(Arm).filter(Arm.id == arm_id).first()
        if arm:
            arm.bid = new_bid
            session.flush()
            logger.info(f"Updated bid for arm {arm_id} to ${new_bid}")
            return True
        return False


def create_metric(metric_data: MetricCreate) -> Metric:
    """Create a new metric entry."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        # Calculate derived metrics
        ctr = metric_data.clicks / metric_data.impressions if metric_data.impressions > 0 else 0.0
        cvr = metric_data.conversions / metric_data.clicks if metric_data.clicks > 0 else 0.0
        roas = metric_data.roas if metric_data.roas is not None else (
            metric_data.revenue / metric_data.cost if metric_data.cost > 0 else 0.0
        )
        
        metric = Metric(
            campaign_id=metric_data.campaign_id,
            arm_id=metric_data.arm_id,
            timestamp=metric_data.timestamp,
            impressions=metric_data.impressions,
            clicks=metric_data.clicks,
            conversions=metric_data.conversions,
            revenue=metric_data.revenue,
            cost=metric_data.cost,
            roas=roas,
            ctr=ctr,
            cvr=cvr,
            source=metric_data.source
        )
        session.add(metric)
        session.flush()
        logger.debug(f"Created metric for arm {metric_data.arm_id}: ROAS={roas:.2f}")
        return metric


def get_metrics_by_arm(arm_id: int, start_date: Optional[datetime] = None,
                       end_date: Optional[datetime] = None) -> List[Metric]:
    """Get metrics for an arm within a date range."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        query = session.query(Metric).filter(Metric.arm_id == arm_id)
        
        if start_date:
            query = query.filter(Metric.timestamp >= start_date)
        if end_date:
            query = query.filter(Metric.timestamp <= end_date)
        
        return query.order_by(Metric.timestamp).all()


def get_aggregated_metrics(arm_id: int, start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None) -> Dict[str, Any]:
    """Get aggregated metrics for an arm."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        query = session.query(
            func.sum(Metric.impressions).label('total_impressions'),
            func.sum(Metric.clicks).label('total_clicks'),
            func.sum(Metric.conversions).label('total_conversions'),
            func.sum(Metric.revenue).label('total_revenue'),
            func.sum(Metric.cost).label('total_cost'),
            func.avg(Metric.roas).label('avg_roas'),
            func.avg(Metric.ctr).label('avg_ctr'),
            func.avg(Metric.cvr).label('avg_cvr')
        ).filter(Metric.arm_id == arm_id)
        
        if start_date:
            query = query.filter(Metric.timestamp >= start_date)
        if end_date:
            query = query.filter(Metric.timestamp <= end_date)
        
        result = query.first()
        
        if result and result.total_impressions:
            return {
                'arm_id': arm_id,
                'start_date': start_date,
                'end_date': end_date,
                'total_impressions': result.total_impressions or 0,
                'total_clicks': result.total_clicks or 0,
                'total_conversions': result.total_conversions or 0,
                'total_revenue': float(result.total_revenue or 0),
                'total_cost': float(result.total_cost or 0),
                'avg_roas': float(result.avg_roas or 0),
                'avg_ctr': float(result.avg_ctr or 0),
                'avg_cvr': float(result.avg_cvr or 0)
            }
        return {
            'arm_id': arm_id,
            'start_date': start_date,
            'end_date': end_date,
            'total_impressions': 0,
            'total_clicks': 0,
            'total_conversions': 0,
            'total_revenue': 0.0,
            'total_cost': 0.0,
            'avg_roas': 0.0,
            'avg_ctr': 0.0,
            'avg_cvr': 0.0
        }


def update_agent_state(state_data: AgentStateUpdate) -> AgentState:
    """Update or create agent state."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        # Try to find existing state
        state = session.query(AgentState).filter(
            and_(
                AgentState.campaign_id == state_data.campaign_id,
                AgentState.arm_id == state_data.arm_id
            )
        ).first()
        
        if state:
            # Update existing state
            state.alpha = state_data.alpha
            state.beta = state_data.beta
            state.spending = state_data.spending
            state.impressions = state_data.impressions
            state.rewards = state_data.rewards
            state.reward_variance = state_data.reward_variance
            state.trials = state_data.trials
            state.risk_score = state_data.risk_score
            state.contextual_state = json.dumps(state_data.contextual_state) if state_data.contextual_state else None
            state.last_updated = datetime.utcnow()
        else:
            # Create new state
            state = AgentState(
                campaign_id=state_data.campaign_id,
                arm_id=state_data.arm_id,
                alpha=state_data.alpha,
                beta=state_data.beta,
                spending=state_data.spending,
                impressions=state_data.impressions,
                rewards=state_data.rewards,
                reward_variance=state_data.reward_variance,
                trials=state_data.trials,
                risk_score=state_data.risk_score,
                contextual_state=json.dumps(state_data.contextual_state) if state_data.contextual_state else None
            )
            session.add(state)
        
        session.flush()
        return state


def get_agent_state(campaign_id: int, arm_id: int) -> Optional[AgentState]:
    """Get agent state for a campaign and arm."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        return session.query(AgentState).filter(
            and_(
                AgentState.campaign_id == campaign_id,
                AgentState.arm_id == arm_id
            )
        ).first()


def get_all_agent_states(campaign_id: int) -> List[AgentState]:
    """Get all agent states for a campaign."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        return session.query(AgentState).filter(
            AgentState.campaign_id == campaign_id
        ).all()


def log_api_call(platform: str, endpoint: str, method: str = 'GET',
                 status_code: Optional[int] = None, response_time: Optional[float] = None,
                 success: bool = True, error_message: Optional[str] = None,
                 request_data: Optional[Dict[str, Any]] = None,
                 response_data: Optional[Dict[str, Any]] = None) -> APILog:
    """Log an API call."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        # Truncate response data if too large
        response_data_str = None
        if response_data:
            response_data_str = json.dumps(response_data)
            if len(response_data_str) > 10000:  # Limit to 10KB
                response_data_str = response_data_str[:10000] + "... (truncated)"
        
        api_log = APILog(
            platform=platform,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time=response_time,
            success=success,
            error_message=error_message,
            request_data=json.dumps(request_data) if request_data else None,
            response_data=response_data_str
        )
        session.add(api_log)
        session.flush()
        return api_log


def get_recent_api_logs(platform: Optional[str] = None, limit: int = 100) -> List[APILog]:
    """Get recent API logs."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        query = session.query(APILog)
        if platform:
            query = query.filter(APILog.platform == platform)
        return query.order_by(desc(APILog.timestamp)).limit(limit).all()


def get_api_error_rate(platform: Optional[str] = None, hours: int = 24) -> float:
    """Get API error rate for the last N hours."""
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        query = session.query(APILog).filter(APILog.timestamp >= cutoff_time)
        
        if platform:
            query = query.filter(APILog.platform == platform)
        
        total_calls = query.count()
        if total_calls == 0:
            return 0.0
        
        failed_calls = query.filter(APILog.success == False).count()
        return failed_calls / total_calls


# =========================================================================
# Incrementality Experiment Helpers
# =========================================================================

def create_incrementality_experiment(
    campaign_id: int,
    name: str,
    experiment_type: str,
    start_date: datetime,
    holdout_percentage: float = 0.10,
    duration_days: int = 28,
    treatment_markets: Optional[List[str]] = None,
    control_markets: Optional[List[str]] = None,
    platform: Optional[str] = None,
    platform_study_id: Optional[str] = None,
    notes: Optional[str] = None
) -> 'IncrementalityExperiment':
    """
    Create a new incrementality experiment.
    
    Args:
        campaign_id: Campaign to run experiment on
        name: Experiment name
        experiment_type: 'holdout', 'geo_lift', or 'platform_native'
        start_date: When experiment starts
        holdout_percentage: Control group percentage (default 10%)
        duration_days: How long to run
        treatment_markets: List of treatment market codes (for geo-lift)
        control_markets: List of control market codes (for geo-lift)
        platform: Platform for native studies
        platform_study_id: External platform study ID
        notes: Optional notes
    
    Returns:
        Created experiment
    """
    from src.bandit_ads.database import IncrementalityExperiment
    
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        experiment = IncrementalityExperiment(
            campaign_id=campaign_id,
            name=name,
            experiment_type=experiment_type,
            holdout_percentage=holdout_percentage,
            treatment_markets=json.dumps(treatment_markets) if treatment_markets else None,
            control_markets=json.dumps(control_markets) if control_markets else None,
            platform=platform,
            platform_study_id=platform_study_id,
            start_date=start_date,
            end_date=start_date + timedelta(days=duration_days),
            status='running',
            notes=notes
        )
        session.add(experiment)
        session.flush()
        logger.info(f"Created incrementality experiment: {name} (ID: {experiment.id})")
        return experiment


def get_incrementality_experiment(experiment_id: int) -> Optional['IncrementalityExperiment']:
    """Get an incrementality experiment by ID."""
    from src.bandit_ads.database import IncrementalityExperiment
    
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        return session.query(IncrementalityExperiment).filter(
            IncrementalityExperiment.id == experiment_id
        ).first()


def get_experiments_by_campaign(
    campaign_id: int,
    status: Optional[str] = None
) -> List['IncrementalityExperiment']:
    """Get all incrementality experiments for a campaign."""
    from src.bandit_ads.database import IncrementalityExperiment
    
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        query = session.query(IncrementalityExperiment).filter(
            IncrementalityExperiment.campaign_id == campaign_id
        )
        if status:
            query = query.filter(IncrementalityExperiment.status == status)
        return query.order_by(desc(IncrementalityExperiment.created_at)).all()


def get_all_experiments(
    status: Optional[str] = None,
    experiment_type: Optional[str] = None,
    limit: int = 100
) -> List['IncrementalityExperiment']:
    """Get all incrementality experiments."""
    from src.bandit_ads.database import IncrementalityExperiment
    
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        query = session.query(IncrementalityExperiment)
        if status:
            query = query.filter(IncrementalityExperiment.status == status)
        if experiment_type:
            query = query.filter(IncrementalityExperiment.experiment_type == experiment_type)
        return query.order_by(desc(IncrementalityExperiment.created_at)).limit(limit).all()


def update_experiment_status(
    experiment_id: int,
    status: str,
    **kwargs
) -> bool:
    """
    Update experiment status and optionally other fields.
    
    Args:
        experiment_id: Experiment ID
        status: New status ('running', 'completed', 'aborted')
        **kwargs: Additional fields to update (lift_percent, p_value, etc.)
    
    Returns:
        True if successful
    """
    from src.bandit_ads.database import IncrementalityExperiment
    
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        experiment = session.query(IncrementalityExperiment).filter(
            IncrementalityExperiment.id == experiment_id
        ).first()
        
        if not experiment:
            return False
        
        experiment.status = status
        
        # Update any additional fields
        for key, value in kwargs.items():
            if hasattr(experiment, key):
                setattr(experiment, key, value)
        
        session.commit()
        logger.info(f"Updated experiment {experiment_id} status to {status}")
        return True


def update_experiment_results(
    experiment_id: int,
    lift_percent: float,
    confidence_lower: float,
    confidence_upper: float,
    p_value: float,
    is_significant: bool,
    incremental_roas: float,
    observed_roas: float,
    incremental_revenue: float,
    incremental_conversions: int,
    treatment_users: int,
    control_users: int,
    treatment_conversions: int,
    control_conversions: int,
    treatment_revenue: float,
    control_revenue: float,
    treatment_spend: float
) -> bool:
    """Update experiment with final results."""
    return update_experiment_status(
        experiment_id,
        status='completed',
        lift_percent=lift_percent,
        confidence_lower=confidence_lower,
        confidence_upper=confidence_upper,
        p_value=p_value,
        is_significant=is_significant,
        incremental_roas=incremental_roas,
        observed_roas=observed_roas,
        incremental_revenue=incremental_revenue,
        incremental_conversions=incremental_conversions,
        treatment_users=treatment_users,
        control_users=control_users,
        treatment_conversions=treatment_conversions,
        control_conversions=control_conversions,
        treatment_revenue=treatment_revenue,
        control_revenue=control_revenue,
        treatment_spend=treatment_spend
    )


def record_incrementality_metric(
    experiment_id: int,
    date: datetime,
    treatment_users: int,
    treatment_impressions: int,
    treatment_clicks: int,
    treatment_conversions: int,
    treatment_revenue: float,
    treatment_spend: float,
    control_users: int,
    control_conversions: int,
    control_revenue: float
) -> 'IncrementalityMetric':
    """
    Record daily metrics for an incrementality experiment.
    
    Calculates CVR and lift automatically.
    """
    from src.bandit_ads.database import IncrementalityMetric, IncrementalityExperiment
    
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        # Calculate rates
        treatment_cvr = treatment_conversions / treatment_users if treatment_users > 0 else 0
        control_cvr = control_conversions / control_users if control_users > 0 else 0
        
        # Calculate daily lift
        if control_cvr > 0:
            daily_lift = (treatment_cvr - control_cvr) / control_cvr * 100
        else:
            daily_lift = 0 if treatment_cvr == 0 else None
        
        # Calculate daily iROAS
        if treatment_spend > 0 and control_users > 0:
            control_rpu = control_revenue / control_users
            expected_organic = control_rpu * treatment_users
            incremental_rev = treatment_revenue - expected_organic
            daily_iroas = incremental_rev / treatment_spend
        else:
            daily_iroas = None
        
        # Get cumulative totals
        prev_metrics = session.query(IncrementalityMetric).filter(
            IncrementalityMetric.experiment_id == experiment_id,
            IncrementalityMetric.date < date
        ).order_by(desc(IncrementalityMetric.date)).first()
        
        if prev_metrics:
            cumulative_treatment = prev_metrics.cumulative_treatment_users + treatment_users
            cumulative_control = prev_metrics.cumulative_control_users + control_users
        else:
            cumulative_treatment = treatment_users
            cumulative_control = control_users
        
        metric = IncrementalityMetric(
            experiment_id=experiment_id,
            date=date,
            treatment_users=treatment_users,
            treatment_impressions=treatment_impressions,
            treatment_clicks=treatment_clicks,
            treatment_conversions=treatment_conversions,
            treatment_revenue=treatment_revenue,
            treatment_spend=treatment_spend,
            control_users=control_users,
            control_conversions=control_conversions,
            control_revenue=control_revenue,
            treatment_cvr=treatment_cvr,
            control_cvr=control_cvr,
            daily_lift_percent=daily_lift,
            daily_incremental_roas=daily_iroas,
            cumulative_treatment_users=cumulative_treatment,
            cumulative_control_users=cumulative_control
        )
        session.add(metric)
        session.flush()
        
        # Update experiment totals
        experiment = session.query(IncrementalityExperiment).filter(
            IncrementalityExperiment.id == experiment_id
        ).first()
        
        if experiment:
            experiment.treatment_users = cumulative_treatment
            experiment.control_users = cumulative_control
            experiment.treatment_conversions = (experiment.treatment_conversions or 0) + treatment_conversions
            experiment.control_conversions = (experiment.control_conversions or 0) + control_conversions
            experiment.treatment_revenue = (experiment.treatment_revenue or 0) + treatment_revenue
            experiment.control_revenue = (experiment.control_revenue or 0) + control_revenue
            experiment.treatment_spend = (experiment.treatment_spend or 0) + treatment_spend
        
        return metric


def get_experiment_metrics(
    experiment_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List['IncrementalityMetric']:
    """Get daily metrics for an experiment."""
    from src.bandit_ads.database import IncrementalityMetric
    
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        query = session.query(IncrementalityMetric).filter(
            IncrementalityMetric.experiment_id == experiment_id
        )
        if start_date:
            query = query.filter(IncrementalityMetric.date >= start_date)
        if end_date:
            query = query.filter(IncrementalityMetric.date <= end_date)
        return query.order_by(IncrementalityMetric.date).all()


def calculate_experiment_results(experiment_id: int) -> Optional[Dict[str, Any]]:
    """
    Calculate final results for an experiment from its metrics.
    
    Returns:
        Dictionary with calculated results or None if insufficient data
    """
    from src.bandit_ads.database import IncrementalityExperiment, IncrementalityMetric
    from src.bandit_ads.incrementality import calculate_incrementality, calculate_incremental_roas
    
    db_manager = get_db_manager()
    with db_manager.get_session() as session:
        experiment = session.query(IncrementalityExperiment).filter(
            IncrementalityExperiment.id == experiment_id
        ).first()
        
        if not experiment:
            return None
        
        # Get aggregated metrics
        metrics = session.query(IncrementalityMetric).filter(
            IncrementalityMetric.experiment_id == experiment_id
        ).all()
        
        if not metrics:
            return None
        
        # Aggregate
        total_treatment_users = sum(m.treatment_users for m in metrics)
        total_control_users = sum(m.control_users for m in metrics)
        total_treatment_conversions = sum(m.treatment_conversions for m in metrics)
        total_control_conversions = sum(m.control_conversions for m in metrics)
        total_treatment_revenue = sum(m.treatment_revenue for m in metrics)
        total_control_revenue = sum(m.control_revenue for m in metrics)
        total_treatment_spend = sum(m.treatment_spend for m in metrics)
        
        # Calculate CVRs
        treatment_cvr = total_treatment_conversions / total_treatment_users if total_treatment_users > 0 else 0
        control_cvr = total_control_conversions / total_control_users if total_control_users > 0 else 0
        
        # Calculate lift
        lift_result = calculate_incrementality(
            treatment_cvr=treatment_cvr,
            control_cvr=control_cvr,
            treatment_users=total_treatment_users,
            control_users=total_control_users,
            treatment_conversions=total_treatment_conversions,
            control_conversions=total_control_conversions
        )
        
        # Calculate iROAS
        roas_result = calculate_incremental_roas(
            treatment_revenue=total_treatment_revenue,
            control_revenue=total_control_revenue,
            treatment_spend=total_treatment_spend,
            treatment_users=total_treatment_users,
            control_users=total_control_users
        )
        
        ci = lift_result.get('confidence_interval', (0, 0))
        
        return {
            'lift_percent': lift_result['lift_percent'],
            'confidence_lower': ci[0] if ci else 0,
            'confidence_upper': ci[1] if ci else 0,
            'p_value': lift_result.get('p_value', 1.0),
            'is_significant': lift_result.get('is_significant', False),
            'incremental_roas': roas_result['incremental_roas'],
            'observed_roas': roas_result['observed_roas'],
            'incremental_revenue': roas_result['incremental_revenue'],
            'incremental_conversions': int(total_treatment_conversions - (control_cvr * total_treatment_users)),
            'treatment_users': total_treatment_users,
            'control_users': total_control_users,
            'treatment_conversions': total_treatment_conversions,
            'control_conversions': total_control_conversions,
            'treatment_revenue': total_treatment_revenue,
            'control_revenue': total_control_revenue,
            'treatment_spend': total_treatment_spend,
            'roas_inflation': roas_result['roas_inflation']
        }
