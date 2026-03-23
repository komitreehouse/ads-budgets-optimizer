"""
Recommendations API endpoints.
"""

import json
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.bandit_ads.database import get_db_manager
from src.bandit_ads.utils import get_logger

logger = get_logger('api.recommendations')
router = APIRouter()


def _rec_to_dict(rec) -> Dict[str, Any]:
    """Convert a Recommendation ORM object to an API-friendly dict."""
    try:
        details = json.loads(rec.details) if rec.details else {}
    except Exception:
        details = {}

    return {
        "id": rec.id,
        "title": rec.title,
        "description": rec.description,
        "type": rec.recommendation_type,
        "campaign_id": rec.campaign_id,
        "campaign_name": f"Campaign {rec.campaign_id}",
        "status": rec.status,
        "confidence": details.get("confidence", 0.7),
        "current_value": details.get("current_value"),
        "proposed_value": details.get("proposed_value"),
        "expected_impact": details.get("expected_impact", ""),
        "explanation": details.get("explanation", rec.description),
        "created_at": rec.created_at.strftime("%b %d, %Y") if rec.created_at else "",
    }


@router.get("")
async def get_recommendations(
    status: str = Query("pending", description="Status: pending, approved, applied, rejected")
):
    """Get recommendations by status."""
    try:
        from src.bandit_ads.recommendations import Recommendation
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            recs = session.query(Recommendation).filter(
                Recommendation.status == status
            ).order_by(Recommendation.created_at.desc()).all()
            return [_rec_to_dict(r) for r in recs]
    except Exception as e:
        logger.error(f"Error getting recommendations: {str(e)}")
        return []


@router.get("/pending")
async def get_pending_recommendations():
    """Get pending recommendations."""
    try:
        from src.bandit_ads.recommendations import Recommendation
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            recs = session.query(Recommendation).filter(
                Recommendation.status == "pending"
            ).order_by(Recommendation.created_at.desc()).all()
            return [_rec_to_dict(r) for r in recs]
    except Exception as e:
        logger.error(f"Error getting pending recommendations: {str(e)}")
        return []


@router.post("")
async def create_recommendation(body: dict):
    """Create a new recommendation (e.g. from a scenario plan)."""
    try:
        from src.bandit_ads.recommendations import Recommendation
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            rec = Recommendation(
                campaign_id=body.get("campaign_id", 0),
                recommendation_type=body.get("type", "allocation_change"),
                title=body.get("title", "Scenario Plan"),
                description=body.get("description", ""),
                details=json.dumps(body.get("details", {})),
                status="pending",
            )
            session.add(rec)
            session.commit()
            session.refresh(rec)
            return {"id": rec.id, "success": True}
    except Exception as e:
        logger.error(f"Error creating recommendation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{recommendation_id}/approve")
async def approve_recommendation(recommendation_id: int):
    """Approve a recommendation."""
    try:
        from src.bandit_ads.recommendations import Recommendation
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            rec = session.query(Recommendation).filter(
                Recommendation.id == recommendation_id
            ).first()
            if not rec:
                raise HTTPException(status_code=404, detail="Recommendation not found")
            rec.status = "applied"
            rec.applied_at = datetime.utcnow()
            session.commit()
        return {"success": True, "message": "Recommendation applied"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving recommendation {recommendation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{recommendation_id}/reject")
async def reject_recommendation(recommendation_id: int):
    """Reject a recommendation."""
    try:
        from src.bandit_ads.recommendations import Recommendation
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            rec = session.query(Recommendation).filter(
                Recommendation.id == recommendation_id
            ).first()
            if not rec:
                raise HTTPException(status_code=404, detail="Recommendation not found")
            rec.status = "rejected"
            session.commit()
        return {"success": True, "message": "Recommendation rejected"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting recommendation {recommendation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
