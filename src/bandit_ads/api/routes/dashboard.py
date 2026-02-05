"""
Dashboard API endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_, desc

from src.bandit_ads.database import get_db_manager, Campaign, Metric
from src.bandit_ads.utils import get_logger

logger = get_logger('api.dashboard')
router = APIRouter()


@router.get("/summary")
async def get_dashboard_summary():
    """Get dashboard summary metrics."""
    try:
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            # Get all active campaigns
            campaigns = session.query(Campaign).filter(
                Campaign.status == 'active'
            ).all()
            
            # Calculate today's metrics
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_metrics = session.query(Metric).filter(
                Metric.timestamp >= today_start
            ).all()
            
            total_spend_today = sum(m.cost for m in today_metrics)
            
            # Calculate yesterday for trend
            yesterday_start = today_start - timedelta(days=1)
            yesterday_end = today_start
            yesterday_metrics = session.query(Metric).filter(
                and_(
                    Metric.timestamp >= yesterday_start,
                    Metric.timestamp < yesterday_end
                )
            ).all()
            total_spend_yesterday = sum(m.cost for m in yesterday_metrics)
            
            spend_trend = ((total_spend_today - total_spend_yesterday) / total_spend_yesterday * 100) if total_spend_yesterday > 0 else 0.0
            
            # Calculate average ROAS
            total_revenue = sum(m.revenue for m in today_metrics)
            avg_roas = total_revenue / total_spend_today if total_spend_today > 0 else 0.0
            
            # Calculate ROAS trend
            revenue_yesterday = sum(m.revenue for m in yesterday_metrics)
            roas_yesterday = revenue_yesterday / total_spend_yesterday if total_spend_yesterday > 0 else 0.0
            roas_trend = ((avg_roas - roas_yesterday) / roas_yesterday * 100) if roas_yesterday > 0 else 0.0
            
            # Get pending recommendations count (placeholder - will be implemented)
            pending_recommendations = 0  # TODO: Get from recommendations service
            
            return {
                "total_spend_today": total_spend_today,
                "spend_trend": spend_trend,
                "avg_roas": avg_roas,
                "roas_trend": roas_trend,
                "active_campaigns": len(campaigns),
                "pending_recommendations": pending_recommendations
            }
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/brand-budget")
async def get_brand_budget_overview(
    time_range: str = Query("MTD", description="Time range: MTD, QTD, YTD, FY")
):
    """Get brand budget overview."""
    try:
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            # Calculate date range
            end_date = datetime.utcnow()
            
            if time_range == "MTD":
                start_date = datetime(end_date.year, end_date.month, 1)
                period_label = end_date.strftime("%B %Y")
            elif time_range == "QTD":
                quarter = (end_date.month - 1) // 3
                start_date = datetime(end_date.year, quarter * 3 + 1, 1)
                period_label = f"Q{quarter + 1} {end_date.year}"
            elif time_range == "YTD":
                start_date = datetime(end_date.year, 1, 1)
                period_label = f"{end_date.year}"
            elif time_range == "FY":
                # Fiscal year (assuming April to March)
                if end_date.month >= 4:
                    start_date = datetime(end_date.year, 4, 1)
                    period_label = f"FY {end_date.year} (Apr {end_date.year} - Mar {end_date.year + 1})"
                else:
                    start_date = datetime(end_date.year - 1, 4, 1)
                    period_label = f"FY {end_date.year - 1} (Apr {end_date.year - 1} - Mar {end_date.year})"
            else:
                start_date = datetime(end_date.year, end_date.month, 1)
                period_label = end_date.strftime("%B %Y")
            
            # Get total budget from all campaigns
            campaigns = session.query(Campaign).filter(
                and_(
                    Campaign.start_date <= end_date,
                    or_(Campaign.end_date.is_(None), Campaign.end_date >= start_date)
                )
            ).all()
            
            total_budget = sum(c.budget for c in campaigns)
            
            # Get spent amount
            metrics = session.query(Metric).filter(
                and_(
                    Metric.timestamp >= start_date,
                    Metric.timestamp <= end_date
                )
            ).all()
            
            spent = sum(m.cost for m in metrics)
            remaining = total_budget - spent
            pacing_percent = (spent / total_budget * 100) if total_budget > 0 else 0.0
            
            return {
                "total_budget": total_budget,
                "spent": spent,
                "remaining": remaining,
                "pacing_percent": pacing_percent,
                "period_label": period_label,
                "time_range": time_range
            }
    except Exception as e:
        logger.error(f"Error getting brand budget overview: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/channel-splits")
async def get_channel_splits(
    time_range: str = Query("MTD", description="Time range: MTD, QTD, YTD, FY")
):
    """Get budget allocation by channel."""
    try:
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            # Calculate date range
            end_date = datetime.utcnow()
            
            if time_range == "MTD":
                start_date = datetime(end_date.year, end_date.month, 1)
            elif time_range == "QTD":
                quarter = (end_date.month - 1) // 3
                start_date = datetime(end_date.year, quarter * 3 + 1, 1)
            elif time_range == "YTD":
                start_date = datetime(end_date.year, 1, 1)
            elif time_range == "FY":
                if end_date.month >= 4:
                    start_date = datetime(end_date.year, 4, 1)
                else:
                    start_date = datetime(end_date.year - 1, 4, 1)
            else:
                start_date = datetime(end_date.year, end_date.month, 1)
            
            # Get metrics grouped by channel
            from src.bandit_ads.database import Arm
            metrics = session.query(
                Arm.channel,
                func.sum(Metric.cost).label('spent'),
                func.sum(Metric.revenue).label('revenue'),
                func.count(func.distinct(Metric.campaign_id)).label('campaign_count')
            ).join(
                Metric, Arm.id == Metric.arm_id
            ).filter(
                and_(
                    Metric.timestamp >= start_date,
                    Metric.timestamp <= end_date
                )
            ).group_by(Arm.channel).all()
            
            # Calculate total for allocation percentages
            total_spent = sum(row.spent for row in metrics)
            
            # Map channels to display info
            channel_info = {
                "Search": {"id": "search", "name": "Search (Google/Bing)", "icon": "🔍", "color": "#22C55E"},
                "Display": {"id": "programmatic", "name": "Programmatic (TTD)", "icon": "🎯", "color": "#6366F1"},
                "Social": {"id": "social", "name": "Social (Meta)", "icon": "👥", "color": "#3B82F6"},
            }
            
            result = []
            for row in metrics:
                channel = row.channel
                info = channel_info.get(channel, {
                    "id": channel.lower().replace(" ", "_"),
                    "name": channel,
                    "icon": "📊",
                    "color": "#737373"
                })
                
                roas = row.revenue / row.spent if row.spent > 0 else 0.0
                allocation_percent = (row.spent / total_spent) if total_spent > 0 else 0.0
                
                result.append({
                    "id": info["id"],
                    "name": info["name"],
                    "icon": info["icon"],
                    "color": info["color"],
                    "budget": row.spent,  # Using spent as budget for now
                    "spent": row.spent,
                    "allocation_percent": allocation_percent,
                    "campaign_count": row.campaign_count,
                    "roas": roas,
                    "roas_trend": 0.0  # TODO: Calculate trend
                })
            
            return result
    except Exception as e:
        logger.error(f"Error getting channel splits: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
