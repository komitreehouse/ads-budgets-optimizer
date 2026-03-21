"""
Optimizer API endpoints for real-time ML optimization status,
explainable decisions, and factor attribution.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from src.bandit_ads.utils import get_logger

logger = get_logger('api.optimizer')
router = APIRouter()


@router.get("/status")
async def get_optimizer_status():
    """Get real-time optimization service status."""
    try:
        from src.bandit_ads.optimization_service import get_optimization_service
        service = get_optimization_service()
        return service.get_status()
    except Exception as e:
        logger.error(f"Error getting optimizer status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decisions")
async def get_recent_decisions(
    limit: int = Query(20, description="Number of recent decisions to return"),
    campaign_id: Optional[int] = Query(None, description="Filter by campaign ID"),
):
    """Get recent optimization decisions with explanations."""
    try:
        from src.bandit_ads.change_tracker import get_change_tracker
        tracker = get_change_tracker()

        # Get allocation changes
        changes = tracker.get_allocation_history(
            campaign_id=campaign_id,
            limit=limit
        )

        decisions = []
        for change in changes:
            decisions.append({
                'id': change.id if hasattr(change, 'id') else None,
                'campaign_id': change.campaign_id,
                'arm_id': change.arm_id,
                'old_allocation': change.old_allocation,
                'new_allocation': change.new_allocation,
                'change_reason': change.change_reason,
                'change_type': change.change_type,
                'factors': change.factors if hasattr(change, 'factors') else {},
                'mmm_factors': change.mmm_factors if hasattr(change, 'mmm_factors') else {},
                'optimizer_state': change.optimizer_state if hasattr(change, 'optimizer_state') else {},
                'explanation_text': getattr(change, 'explanation_text', None),
                'timestamp': change.timestamp.isoformat() if hasattr(change, 'timestamp') and change.timestamp else None,
            })

        return decisions
    except Exception as e:
        logger.error(f"Error getting decisions: {str(e)}")
        # Return empty list on error (e.g. change tracker not available)
        return []


@router.get("/factor-attribution")
async def get_factor_attribution(
    campaign_id: Optional[int] = Query(None, description="Filter by campaign ID"),
    limit: int = Query(50, description="Number of recent changes to aggregate"),
):
    """Get aggregated factor attribution from recent decisions."""
    try:
        from src.bandit_ads.change_tracker import get_change_tracker
        tracker = get_change_tracker()

        changes = tracker.get_allocation_history(
            campaign_id=campaign_id,
            limit=limit
        )

        # Aggregate factor counts and impacts
        factor_counts: Dict[str, int] = {}
        factor_impacts: Dict[str, float] = {}

        for change in changes:
            factors = getattr(change, 'factors', None)
            if not factors or not isinstance(factors, dict):
                continue
            alloc_delta = abs(
                (change.new_allocation or 0) - (change.old_allocation or 0)
            )
            for factor_name in factors:
                factor_counts[factor_name] = factor_counts.get(factor_name, 0) + 1
                factor_impacts[factor_name] = factor_impacts.get(factor_name, 0.0) + alloc_delta

        attribution = [
            {
                'factor': name,
                'count': factor_counts[name],
                'total_impact': round(factor_impacts.get(name, 0), 4),
            }
            for name in sorted(factor_counts, key=lambda n: factor_counts[n], reverse=True)
        ]

        return attribution
    except Exception as e:
        logger.error(f"Error getting factor attribution: {str(e)}")
        return []


@router.get("/explanation/{campaign_id}")
async def get_latest_explanation(campaign_id: int):
    """Get the latest plain-language explanation for a campaign's allocation decisions."""
    try:
        from src.bandit_ads.change_tracker import get_change_tracker
        tracker = get_change_tracker()

        # Get the most recent change for this campaign
        changes = tracker.get_allocation_history(
            campaign_id=campaign_id,
            limit=5
        )

        if not changes:
            return {
                'campaign_id': campaign_id,
                'explanation': None,
                'message': 'No allocation changes recorded yet. The optimizer will generate explanations as it runs.'
            }

        # Return the most recent changes with any stored explanations
        latest = changes[0]
        explanation_text = getattr(latest, 'explanation_text', None)

        # If no stored explanation, try generating one on the fly
        if not explanation_text:
            try:
                from src.bandit_ads.explanation_generator import ExplanationGenerator
                generator = ExplanationGenerator()
                explanation_text = generator.explain_allocation_change(
                    change_id=latest.id if hasattr(latest, 'id') else None
                )
            except Exception:
                explanation_text = None

        return {
            'campaign_id': campaign_id,
            'explanation': explanation_text,
            'latest_change': {
                'arm_id': latest.arm_id,
                'old_allocation': latest.old_allocation,
                'new_allocation': latest.new_allocation,
                'change_reason': latest.change_reason,
                'timestamp': latest.timestamp.isoformat() if hasattr(latest, 'timestamp') and latest.timestamp else None,
            },
            'recent_changes_count': len(changes),
        }
    except Exception as e:
        logger.error(f"Error getting explanation for campaign {campaign_id}: {str(e)}")
        return {
            'campaign_id': campaign_id,
            'explanation': None,
            'message': f'Error: {str(e)}'
        }
