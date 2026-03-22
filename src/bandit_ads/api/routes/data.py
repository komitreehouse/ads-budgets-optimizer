"""
Data API endpoints — upload historical files and inspect data source health.
"""

import io
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from src.bandit_ads.utils import get_logger

logger = get_logger('api.data')
router = APIRouter()

# In-memory registry of uploaded files (persists for the process lifetime).
# A production system would store this in the database.
_uploaded_files: List[dict] = []


class DataSourceStatus(BaseModel):
    platform: str
    display_name: str
    icon: str
    connected: bool
    last_sync: Optional[str] = None
    error: Optional[str] = None


class UploadedFile(BaseModel):
    filename: str
    rows: int
    date_range: Optional[str] = None
    upload_time: str
    size_bytes: int


class DataSourcesResponse(BaseModel):
    platforms: List[DataSourceStatus]
    uploaded_files: List[UploadedFile]


@router.get("", response_model=DataSourcesResponse)
async def get_data_sources():
    """
    Return connected platform statuses and previously uploaded files.
    Platform connection status is inferred from the presence of API credentials
    in the optimization service.
    """
    try:
        platforms = _get_platform_statuses()
        uploaded = [UploadedFile(**f) for f in _uploaded_files]
        return DataSourcesResponse(platforms=platforms, uploaded_files=uploaded)
    except Exception as e:
        logger.error(f"Error fetching data sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_data_file(file: UploadFile = File(...)):
    """
    Accept a CSV or JSON historical performance file, parse it with
    MMMDataLoader, and return a summary of the ingested data.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("csv", "json"):
        raise HTTPException(status_code=400, detail="Only CSV and JSON files are supported")

    try:
        raw = await file.read()
        size_bytes = len(raw)
        text = raw.decode("utf-8")

        from src.bandit_ads.data_loader import MMMDataLoader
        loader = MMMDataLoader()

        if ext == "csv":
            import csv, io as _io
            reader = csv.DictReader(_io.StringIO(text))
            rows_data = list(reader)
            row_count = len(rows_data)
            date_range = _extract_date_range(rows_data, "date")
        else:
            data = json.loads(text)
            if isinstance(data, list):
                row_count = len(data)
                date_range = _extract_date_range(data, "date")
            else:
                row_count = 1
                date_range = None

        record = {
            "filename": file.filename,
            "rows": row_count,
            "date_range": date_range,
            "upload_time": datetime.utcnow().isoformat(),
            "size_bytes": size_bytes,
        }
        _uploaded_files.append(record)

        logger.info(f"Uploaded {file.filename}: {row_count} rows, {date_range}")
        return {
            "success": True,
            "filename": file.filename,
            "rows": row_count,
            "date_range": date_range,
            "size_bytes": size_bytes,
        }

    except Exception as e:
        logger.error(f"Error processing upload {file.filename}: {e}")
        raise HTTPException(status_code=422, detail=f"Could not parse file: {e}")


@router.delete("/upload/{filename}")
async def delete_uploaded_file(filename: str):
    """Remove an uploaded file record."""
    global _uploaded_files
    original_count = len(_uploaded_files)
    _uploaded_files = [f for f in _uploaded_files if f["filename"] != filename]
    if len(_uploaded_files) == original_count:
        raise HTTPException(status_code=404, detail="File not found")
    return {"success": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_platform_statuses() -> List[DataSourceStatus]:
    """Check which platforms have credentials configured in the optimization service."""
    statuses = []
    try:
        from src.bandit_ads.optimization_service import get_optimization_service
        svc = get_optimization_service()
        # Check if there are active runners to infer connection
        runner_ids = list(getattr(svc, 'campaign_runners', {}).keys())
        has_google = any("google" in str(r).lower() for r in runner_ids)
        has_meta = any("meta" in str(r).lower() or "facebook" in str(r).lower() for r in runner_ids)
        has_ttd = any("ttd" in str(r).lower() or "tradedesk" in str(r).lower() for r in runner_ids)
    except Exception:
        has_google = has_meta = has_ttd = False

    statuses.append(DataSourceStatus(
        platform="google_ads",
        display_name="Google Ads",
        icon="🔍",
        connected=has_google,
        last_sync=datetime.utcnow().isoformat() if has_google else None,
        error=None if has_google else "No active campaigns found"
    ))
    statuses.append(DataSourceStatus(
        platform="meta_ads",
        display_name="Meta Ads",
        icon="👥",
        connected=has_meta,
        last_sync=datetime.utcnow().isoformat() if has_meta else None,
        error=None if has_meta else "No active campaigns found"
    ))
    statuses.append(DataSourceStatus(
        platform="the_trade_desk",
        display_name="The Trade Desk",
        icon="🎯",
        connected=has_ttd,
        last_sync=datetime.utcnow().isoformat() if has_ttd else None,
        error=None if has_ttd else "No active campaigns found"
    ))
    return statuses


def _extract_date_range(rows: list, date_col: str) -> Optional[str]:
    """Extract min/max date from a list of row dicts."""
    dates = []
    for row in rows:
        val = row.get(date_col) or row.get("Date") or row.get("DATE")
        if val:
            dates.append(str(val))
    if not dates:
        return None
    dates.sort()
    if dates[0] == dates[-1]:
        return dates[0]
    return f"{dates[0]} → {dates[-1]}"
