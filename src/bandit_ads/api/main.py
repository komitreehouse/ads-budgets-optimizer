"""
FastAPI application for Ads Budget Optimizer API.

Provides REST endpoints for the frontend dashboard.
"""

import os
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import sys
from pathlib import Path
from starlette.exceptions import HTTPException as StarletteHTTPException

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.bandit_ads.api.routes import campaigns, dashboard, recommendations, optimizer, incrementality, ask, data, forecasting, scenarios, export, attribution, mmm
from src.bandit_ads.api.rate_limit import limiter
from src.bandit_ads.utils import get_logger

logger = get_logger('api')

# Create FastAPI app
app = FastAPI(
    title="Ads Budget Optimizer API",
    description="REST API for the Ads Budget Optimizer dashboard",
    version="1.0.0"
)

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGIN", "http://localhost:8501").split(",")
    if origin.strip()
]

# CORS middleware - allow frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include routers
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["recommendations"])
app.include_router(optimizer.router, prefix="/api/optimizer", tags=["optimizer"])
app.include_router(incrementality.router, prefix="/api/incrementality", tags=["incrementality"])
app.include_router(ask.router, prefix="/api/ask", tags=["ask"])
app.include_router(data.router, prefix="/api/data", tags=["data"])
app.include_router(forecasting.router, prefix="/api/forecasting", tags=["forecasting"])
app.include_router(scenarios.router, prefix="/api/scenarios", tags=["scenarios"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(attribution.router, prefix="/api/attribution", tags=["attribution"])
app.include_router(mmm.router, prefix="/api/mmm", tags=["mmm"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Ads Budget Optimizer API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    try:
        from src.bandit_ads.database import get_db_manager
        db_manager = get_db_manager()
        db_healthy = db_manager.health_check()
        
        return {
            "status": "healthy" if db_healthy else "degraded",
            "database": "connected" if db_healthy else "disconnected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": "Service temporarily unavailable",
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Sanitize server-side HTTP errors while preserving 4xx details."""
    if exc.status_code >= 500:
        logger.error(f"HTTP {exc.status_code}: {exc.detail}", exc_info=True)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "Internal server error",
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
