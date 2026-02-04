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
