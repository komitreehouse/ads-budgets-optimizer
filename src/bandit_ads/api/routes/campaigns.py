"""
Campaign API endpoints.
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy import func, and_, desc
import json
from pydantic import BaseModel

from src.bandit_ads.database import get_db_manager, Campaign, Arm, Metric, AgentState
from src.bandit_ads.db_helpers import (
    get_campaign, get_campaign_by_name, get_arms_by_campaign,
    get_arm_platform_entity_ids
)
from src.bandit_ads.utils import get_logger

logger = get_logger('api.campaigns')
router = APIRouter()


class CampaignSettingsUpdate(BaseModel):
    """Model for updating campaign settings."""
    primary_kpi: Optional[str] = None
    targets: Optional[Dict[str, Any]] = None
    benchmarks: Optional[Dict[str, Any]] = None
    thresholds: Optional[Dict[str, float]] = None


def _calculate_time_range(time_range: str) -> Tuple[datetime, datetime]:
    """Calculate start and end dates for a time range."""
    end_date = datetime.utcnow()
    
    if time_range == "7D":
        start_date = end_date - timedelta(days=7)
    elif time_range == "30D":
        start_date = end_date - timedelta(days=30)
    elif time_range == "90D":
        start_date = end_date - timedelta(days=90)
    elif time_range == "MTD":
        start_date = datetime(end_date.year, end_date.month, 1)
    elif time_range == "QTD":
        quarter = (end_date.month - 1) // 3
        start_date = datetime(end_date.year, quarter * 3 + 1, 1)
    elif time_range == "YTD":
        start_date = datetime(end_date.year, 1, 1)
    else:
        start_date = end_date - timedelta(days=7)  # Default to 7 days
    
    return start_date, end_date


@router.get("")
async def list_campaigns():
    """Get list of all campaigns."""
    try:
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            campaigns = session.query(Campaign).all()
            
            result = []
            for campaign in campaigns:
                # Get total metrics
                metrics = session.query(Metric).filter(
                    Metric.campaign_id == campaign.id
                ).all()
                
                total_spend = sum(m.cost for m in metrics)
                total_revenue = sum(m.revenue for m in metrics)
                roas = total_revenue / total_spend if total_spend > 0 else 0.0
                
                result.append({
                    "id": campaign.id,
                    "name": campaign.name,
                    "budget": campaign.budget,
                    "spend": total_spend,
                    "revenue": total_revenue,
                    "roas": roas,
                    "status": campaign.status,
                    "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
                    "end_date": campaign.end_date.isoformat() if campaign.end_date else None,
                    "created_at": campaign.created_at.isoformat() if campaign.created_at else None
                })
            
            return result
    except Exception as e:
        logger.error(f"Error listing campaigns: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}")
async def get_campaign_detail(campaign_id: int):
    """Get campaign details."""
    try:
        campaign = get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            metrics = session.query(Metric).filter(
                Metric.campaign_id == campaign_id
            ).all()
            
            total_spend = sum(m.cost for m in metrics)
            total_revenue = sum(m.revenue for m in metrics)
            total_impressions = sum(m.impressions for m in metrics)
            total_clicks = sum(m.clicks for m in metrics)
            total_conversions = sum(m.conversions for m in metrics)
            roas = total_revenue / total_spend if total_spend > 0 else 0.0
            
            return {
                "id": campaign.id,
                "name": campaign.name,
                "budget": campaign.budget,
                "spend": total_spend,
                "revenue": total_revenue,
                "impressions": total_impressions,
                "clicks": total_clicks,
                "conversions": total_conversions,
                "roas": roas,
                "status": campaign.status,
                "primary_kpi": campaign.primary_kpi or "ROAS",
                "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
                "end_date": campaign.end_date.isoformat() if campaign.end_date else None,
                "created_at": campaign.created_at.isoformat() if campaign.created_at else None
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign {campaign_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}/metrics")
async def get_campaign_metrics(
    campaign_id: int,
    time_range: str = Query("7D", description="Time range: 7D, 30D, 90D, MTD, QTD, YTD")
):
    """Get campaign metrics for a time range."""
    try:
        campaign = get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        start_date, end_date = _calculate_time_range(time_range)
        
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            metrics = session.query(Metric).filter(
                and_(
                    Metric.campaign_id == campaign_id,
                    Metric.timestamp >= start_date,
                    Metric.timestamp <= end_date
                )
            ).order_by(Metric.timestamp).all()
            
            total_spend = sum(m.cost for m in metrics)
            total_revenue = sum(m.revenue for m in metrics)
            total_impressions = sum(m.impressions for m in metrics)
            total_clicks = sum(m.clicks for m in metrics)
            total_conversions = sum(m.conversions for m in metrics)
            roas = total_revenue / total_spend if total_spend > 0 else 0.0
            ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
            cvr = total_conversions / total_clicks if total_clicks > 0 else 0.0
            
            return {
                "campaign_id": campaign_id,
                "time_range": time_range,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "impressions": total_impressions,
                "clicks": total_clicks,
                "conversions": total_conversions,
                "revenue": total_revenue,
                "cost": total_spend,
                "roas": roas,
                "ctr": ctr,
                "cvr": cvr
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metrics for campaign {campaign_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}/time-series")
async def get_performance_time_series(
    campaign_id: int,
    time_range: str = Query("7D", description="Time range: 7D, 30D, 90D, MTD, QTD, YTD")
):
    """Get time-series performance data."""
    try:
        campaign = get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        start_date, end_date = _calculate_time_range(time_range)
        
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            # Group metrics by day
            daily_metrics = session.query(
                func.date(Metric.timestamp).label('date'),
                func.sum(Metric.impressions).label('impressions'),
                func.sum(Metric.clicks).label('clicks'),
                func.sum(Metric.conversions).label('conversions'),
                func.sum(Metric.revenue).label('revenue'),
                func.sum(Metric.cost).label('cost')
            ).filter(
                and_(
                    Metric.campaign_id == campaign_id,
                    Metric.timestamp >= start_date,
                    Metric.timestamp <= end_date
                )
            ).group_by(func.date(Metric.timestamp)).order_by('date').all()
            
            result = []
            for row in daily_metrics:
                roas = row.revenue / row.cost if row.cost > 0 else 0.0
                result.append({
                    "date": row.date.isoformat(),
                    "impressions": int(row.impressions or 0),
                    "clicks": int(row.clicks or 0),
                    "conversions": int(row.conversions or 0),
                    "revenue": float(row.revenue or 0.0),
                    "cost": float(row.cost or 0.0),
                    "roas": roas
                })
            
            return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting time-series for campaign {campaign_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}/arms")
async def get_campaign_arms(campaign_id: int):
    """Get all arms for a campaign."""
    try:
        campaign = get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        arms = get_arms_by_campaign(campaign_id)
        
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            result = []
            for arm in arms:
                # Get metrics for this arm
                metrics = session.query(Metric).filter(
                    Metric.arm_id == arm.id
                ).all()
                
                total_spend = sum(m.cost for m in metrics)
                total_revenue = sum(m.revenue for m in metrics)
                total_impressions = sum(m.impressions for m in metrics)
                total_clicks = sum(m.clicks for m in metrics)
                total_conversions = sum(m.conversions for m in metrics)
                roas = total_revenue / total_spend if total_spend > 0 else 0.0
                
                # Get platform entity IDs
                platform_entity_ids = None
                if arm.platform_entity_ids:
                    try:
                        platform_entity_ids = json.loads(arm.platform_entity_ids)
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                # Get agent state
                agent_state = session.query(AgentState).filter(
                    and_(
                        AgentState.campaign_id == campaign_id,
                        AgentState.arm_id == arm.id
                    )
                ).first()
                
                result.append({
                    "id": arm.id,
                    "campaign_id": arm.campaign_id,
                    "platform": arm.platform,
                    "channel": arm.channel,
                    "creative": arm.creative,
                    "bid": arm.bid,
                    "platform_entity_ids": platform_entity_ids,
                    "impressions": total_impressions,
                    "clicks": total_clicks,
                    "conversions": total_conversions,
                    "revenue": total_revenue,
                    "cost": total_spend,
                    "roas": roas,
                    "trials": agent_state.trials if agent_state else 0,
                    "alpha": agent_state.alpha if agent_state else 1.0,
                    "beta": agent_state.beta if agent_state else 1.0,
                    "risk_score": agent_state.risk_score if agent_state else 0.0
                })
            
            return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting arms for campaign {campaign_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}/enhanced-metrics")
async def get_enhanced_campaign_metrics(
    campaign_id: int,
    primary_kpi: str = Query("ROAS", description="Primary KPI: ROAS, CPA, Revenue, Conversions")
):
    """Get enhanced campaign metrics with today/MTD spend, targets, and benchmarks."""
    try:
        campaign = get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            today = datetime.utcnow().date()
            mtd_start = datetime(today.year, today.month, 1)
            
            # Today's metrics
            today_metrics = session.query(Metric).filter(
                and_(
                    Metric.campaign_id == campaign_id,
                    func.date(Metric.timestamp) == today
                )
            ).all()
            
            # MTD metrics
            mtd_metrics = session.query(Metric).filter(
                and_(
                    Metric.campaign_id == campaign_id,
                    Metric.timestamp >= mtd_start
                )
            ).all()
            
            # Total metrics
            total_metrics = session.query(Metric).filter(
                Metric.campaign_id == campaign_id
            ).all()
            
            def calculate_metrics(metrics):
                if not metrics:
                    return {
                        "spend": 0.0, "revenue": 0.0, "impressions": 0, "clicks": 0,
                        "conversions": 0, "roas": 0.0, "cpa": 0.0, "cpc": 0.0,
                        "cvr": 0.0, "aov": 0.0
                    }
                
                total_spend = sum(m.cost for m in metrics)
                total_revenue = sum(m.revenue for m in metrics)
                total_impressions = sum(m.impressions for m in metrics)
                total_clicks = sum(m.clicks for m in metrics)
                total_conversions = sum(m.conversions for m in metrics)
                
                roas = total_revenue / total_spend if total_spend > 0 else 0.0
                cpa = total_spend / total_conversions if total_conversions > 0 else 0.0
                cpc = total_spend / total_clicks if total_clicks > 0 else 0.0
                cvr = total_conversions / total_clicks if total_clicks > 0 else 0.0
                aov = total_revenue / total_conversions if total_conversions > 0 else 0.0
                
                return {
                    "spend": total_spend,
                    "revenue": total_revenue,
                    "impressions": total_impressions,
                    "clicks": total_clicks,
                    "conversions": total_conversions,
                    "roas": roas,
                    "cpa": cpa,
                    "cpc": cpc,
                    "cvr": cvr,
                    "aov": aov
                }
            
            today_data = calculate_metrics(today_metrics)
            mtd_data = calculate_metrics(mtd_metrics)
            total_data = calculate_metrics(total_metrics)
            
            # Get targets/benchmarks from campaign settings or use defaults
            targets = {
                "roas": campaign.target_roas if campaign.target_roas else 2.0,
                "cpa": campaign.target_cpa if campaign.target_cpa else 50.0,
                "revenue": campaign.target_revenue if campaign.target_revenue else campaign.budget * 2,
                "conversions": campaign.target_conversions if campaign.target_conversions else 100
            }
            
            benchmarks = {
                "roas": campaign.benchmark_roas if campaign.benchmark_roas else 1.8,
                "cpa": campaign.benchmark_cpa if campaign.benchmark_cpa else 55.0,
                "revenue": campaign.benchmark_revenue if campaign.benchmark_revenue else campaign.budget * 1.8,
                "conversions": campaign.benchmark_conversions if campaign.benchmark_conversions else 90
            }
            
            # Get thresholds from campaign settings
            scaling_threshold = campaign.scaling_threshold if campaign.scaling_threshold else 1.1
            stable_threshold = campaign.stable_threshold if campaign.stable_threshold else 0.9
            
            # Calculate efficiency delta vs benchmark
            primary_value = today_data.get(primary_kpi.lower(), 0.0)
            benchmark_value = benchmarks.get(primary_kpi.lower(), 0.0)
            
            if benchmark_value > 0:
                efficiency_delta = ((primary_value - benchmark_value) / benchmark_value) * 100
            else:
                efficiency_delta = 0.0
            
            # Determine status using campaign thresholds
            target_value = targets.get(primary_kpi.lower(), 0.0)
            if target_value > 0:
                if primary_value >= target_value * scaling_threshold:
                    status = "scaling"  # 🟢
                elif primary_value >= target_value * stable_threshold:
                    status = "stable"  # 🟡
                else:
                    status = "underperforming"  # 🔴
            else:
                status = "stable"  # Default if no target set
            
            return {
                "campaign_id": campaign_id,
                "primary_kpi": primary_kpi,
                "today": today_data,
                "mtd": mtd_data,
                "total": total_data,
                "targets": targets,
                "benchmarks": benchmarks,
                "efficiency_delta": efficiency_delta,
                "status": status,
                "thresholds": {
                    "scaling": scaling_threshold,
                    "stable": stable_threshold
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting enhanced metrics for campaign {campaign_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}/channel-breakdown")
async def get_channel_breakdown(campaign_id: int):
    """Get channel and tactic breakdown with budget utilization and pacing."""
    try:
        campaign = get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        arms = get_arms_by_campaign(campaign_id)
        
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            # Group by channel
            channel_data = {}
            
            for arm in arms:
                channel_key = f"{arm.platform} - {arm.channel}"
                
                if channel_key not in channel_data:
                    channel_data[channel_key] = {
                        "platform": arm.platform,
                        "channel": arm.channel,
                        "arms": [],
                        "total_spend": 0.0,
                        "total_revenue": 0.0,
                        "total_impressions": 0,
                        "total_clicks": 0,
                        "total_conversions": 0
                    }
                
                # Get metrics for this arm
                metrics = session.query(Metric).filter(
                    Metric.arm_id == arm.id
                ).all()
                
                arm_spend = sum(m.cost for m in metrics)
                arm_revenue = sum(m.revenue for m in metrics)
                arm_impressions = sum(m.impressions for m in metrics)
                arm_clicks = sum(m.clicks for m in metrics)
                arm_conversions = sum(m.conversions for m in metrics)
                
                channel_data[channel_key]["total_spend"] += arm_spend
                channel_data[channel_key]["total_revenue"] += arm_revenue
                channel_data[channel_key]["total_impressions"] += arm_impressions
                channel_data[channel_key]["total_clicks"] += arm_clicks
                channel_data[channel_key]["total_conversions"] += arm_conversions
                
                channel_data[channel_key]["arms"].append({
                    "id": arm.id,
                    "creative": arm.creative,
                    "bid": arm.bid,
                    "spend": arm_spend,
                    "revenue": arm_revenue,
                    "roas": arm_revenue / arm_spend if arm_spend > 0 else 0.0
                })
            
            # Calculate budget utilization and pacing
            result = []
            total_campaign_spend = sum(c["total_spend"] for c in channel_data.values())
            
            for channel_key, data in channel_data.items():
                budget_allocation = (data["total_spend"] / campaign.budget) * 100 if campaign.budget > 0 else 0
                utilization = (data["total_spend"] / total_campaign_spend) * 100 if total_campaign_spend > 0 else 0
                
                # Calculate pacing (spend vs time elapsed)
                days_elapsed = (datetime.utcnow() - campaign.start_date).days if campaign.start_date else 1
                expected_spend = (campaign.budget / 30) * days_elapsed  # Assuming 30-day month
                pacing = (data["total_spend"] / expected_spend) * 100 if expected_spend > 0 else 0
                
                result.append({
                    "channel": channel_key,
                    "platform": data["platform"],
                    "channel_type": data["channel"],
                    "spend": data["total_spend"],
                    "revenue": data["total_revenue"],
                    "roas": data["total_revenue"] / data["total_spend"] if data["total_spend"] > 0 else 0.0,
                    "impressions": data["total_impressions"],
                    "clicks": data["total_clicks"],
                    "conversions": data["total_conversions"],
                    "budget_allocation": budget_allocation,
                    "utilization": utilization,
                    "pacing": pacing,
                    "arms": data["arms"]
                })
            
            return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting channel breakdown for campaign {campaign_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}/settings")
async def get_campaign_settings(campaign_id: int):
    """Get campaign settings including targets, benchmarks, and thresholds."""
    try:
        campaign = get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        return {
            "campaign_id": campaign_id,
            "primary_kpi": campaign.primary_kpi or "ROAS",
            "targets": {
                "roas": campaign.target_roas,
                "cpa": campaign.target_cpa,
                "revenue": campaign.target_revenue,
                "conversions": campaign.target_conversions
            },
            "benchmarks": {
                "roas": campaign.benchmark_roas,
                "cpa": campaign.benchmark_cpa,
                "revenue": campaign.benchmark_revenue,
                "conversions": campaign.benchmark_conversions
            },
            "thresholds": {
                "scaling": campaign.scaling_threshold or 1.1,
                "stable": campaign.stable_threshold or 0.9
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting settings for campaign {campaign_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{campaign_id}/settings")
async def update_campaign_settings(
    campaign_id: int,
    settings: CampaignSettingsUpdate
):
    """Update campaign settings including targets, benchmarks, and thresholds."""
    try:
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            campaign = session.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                raise HTTPException(status_code=404, detail="Campaign not found")
            
            # Update primary KPI
            if settings.primary_kpi is not None:
                campaign.primary_kpi = settings.primary_kpi
            
            # Update targets
            if settings.targets is not None:
                if "roas" in settings.targets:
                    campaign.target_roas = settings.targets["roas"]
                if "cpa" in settings.targets:
                    campaign.target_cpa = settings.targets["cpa"]
                if "revenue" in settings.targets:
                    campaign.target_revenue = settings.targets["revenue"]
                if "conversions" in settings.targets:
                    campaign.target_conversions = settings.targets["conversions"]
            
            # Update benchmarks
            if settings.benchmarks is not None:
                if "roas" in settings.benchmarks:
                    campaign.benchmark_roas = settings.benchmarks["roas"]
                if "cpa" in settings.benchmarks:
                    campaign.benchmark_cpa = settings.benchmarks["cpa"]
                if "revenue" in settings.benchmarks:
                    campaign.benchmark_revenue = settings.benchmarks["revenue"]
                if "conversions" in settings.benchmarks:
                    campaign.benchmark_conversions = settings.benchmarks["conversions"]
            
            # Update thresholds
            if settings.thresholds is not None:
                if "scaling" in settings.thresholds:
                    campaign.scaling_threshold = settings.thresholds["scaling"]
                if "stable" in settings.thresholds:
                    campaign.stable_threshold = settings.thresholds["stable"]
            
            campaign.updated_at = datetime.utcnow()
            session.commit()
            
            return {
                "campaign_id": campaign_id,
                "message": "Settings updated successfully",
                "settings": {
                    "primary_kpi": campaign.primary_kpi,
                    "targets": {
                        "roas": campaign.target_roas,
                        "cpa": campaign.target_cpa,
                        "revenue": campaign.target_revenue,
                        "conversions": campaign.target_conversions
                    },
                    "benchmarks": {
                        "roas": campaign.benchmark_roas,
                        "cpa": campaign.benchmark_cpa,
                        "revenue": campaign.benchmark_revenue,
                        "conversions": campaign.benchmark_conversions
                    },
                    "thresholds": {
                        "scaling": campaign.scaling_threshold,
                        "stable": campaign.stable_threshold
                    }
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating settings for campaign {campaign_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}/allocation")
async def get_campaign_allocation(campaign_id: int):
    """Get current allocation for campaign."""
    try:
        campaign = get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        arms = get_arms_by_campaign(campaign_id)
        
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            result = []
            for arm in arms:
                # Get metrics for this arm
                metrics = session.query(Metric).filter(
                    Metric.arm_id == arm.id
                ).all()
                
                total_spend = sum(m.cost for m in metrics)
                total_revenue = sum(m.revenue for m in metrics)
                
                # Get agent state for allocation
                agent_state = session.query(AgentState).filter(
                    and_(
                        AgentState.campaign_id == campaign_id,
                        AgentState.arm_id == arm.id
                    )
                ).first()
                
                # Calculate allocation percentage (based on spend or agent state)
                total_campaign_spend = sum(m.cost for m in session.query(Metric).filter(
                    Metric.campaign_id == campaign_id
                ).all())
                
                allocation = (total_spend / total_campaign_spend * 100) if total_campaign_spend > 0 else 0
                
                result.append({
                    "id": arm.id,
                    "name": f"{arm.platform} - {arm.channel} - {arm.creative}",
                    "platform": arm.platform,
                    "channel": arm.channel,
                    "creative": arm.creative,
                    "allocation": allocation / 100,  # As decimal
                    "spend": total_spend,
                    "revenue": total_revenue,
                    "roas": total_revenue / total_spend if total_spend > 0 else 0.0,
                    "change": 0.0  # TODO: Calculate change from previous period
                })
            
            return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting allocation for campaign {campaign_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
