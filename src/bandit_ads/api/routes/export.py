"""
Export API routes — CSV and PDF download endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from typing import Optional

router = APIRouter()


@router.get("/{campaign_id}/csv")
async def export_csv(
    campaign_id: int,
    type: str = Query("metrics", description="metrics | allocation | decisions"),
    days: int = Query(30, description="lookback window for metrics/decisions"),
):
    """Download a CSV export for a campaign."""
    try:
        from src.bandit_ads.export import ExportService
        svc = ExportService()

        if type == "metrics":
            data = svc.metrics_csv(campaign_id, days=days)
            filename = f"campaign_{campaign_id}_metrics.csv"
        elif type == "allocation":
            data = svc.allocation_csv(campaign_id)
            filename = f"campaign_{campaign_id}_allocation.csv"
        elif type == "decisions":
            data = svc.decisions_csv(campaign_id, days=days)
            filename = f"campaign_{campaign_id}_decisions.csv"
        else:
            raise HTTPException(status_code=400, detail=f"Unknown type: {type}. Use metrics, allocation, or decisions.")

        return Response(
            content=data,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}/pdf")
async def export_pdf(campaign_id: int, campaign_name: Optional[str] = Query(None)):
    """Download a branded PDF report for a campaign."""
    try:
        from src.bandit_ads.export import ExportService
        from src.bandit_ads.database import get_db_manager, Campaign

        # Resolve campaign name if not provided
        if not campaign_name:
            try:
                db = get_db_manager()
                with db.get_session() as session:
                    camp = session.query(Campaign).filter(Campaign.id == campaign_id).first()
                    campaign_name = camp.name if camp else f"Campaign {campaign_id}"
            except Exception:
                campaign_name = f"Campaign {campaign_id}"

        svc = ExportService()
        data = svc.campaign_pdf(campaign_id, campaign_name=campaign_name)

        return Response(
            content=data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="ipsa_campaign_{campaign_id}.pdf"'
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
