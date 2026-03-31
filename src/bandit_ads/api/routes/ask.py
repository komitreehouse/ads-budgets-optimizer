"""
Ask API endpoint — natural language query interface.

Routes user questions to the OrchestratorAgent for real-time,
explainable answers about campaigns, performance, and optimizer decisions.
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional

from src.bandit_ads.api.rate_limit import limiter
from src.bandit_ads.utils import get_logger

logger = get_logger('api.ask')
router = APIRouter()


class AskRequest(BaseModel):
    query: str
    campaign_id: Optional[int] = None


class AskResponse(BaseModel):
    answer: str
    query_type: Optional[str] = None
    model_used: Optional[str] = None
    tools_used: Optional[list] = None
    error: Optional[str] = None


@router.post("", response_model=AskResponse)
@limiter.limit("30/minute")
async def ask_question(request: Request, payload: AskRequest):
    """
    Ask a natural language question about campaigns and optimization.

    Uses the OrchestratorAgent to route queries to the appropriate tools
    (change tracker, explanation generator, metrics) and return a
    plain-language answer.
    """
    try:
        from src.bandit_ads.orchestrator import OrchestratorAgent
        orchestrator = OrchestratorAgent()

        result = await orchestrator.process_query(
            query=payload.query,
            campaign_id=payload.campaign_id
        )

        return AskResponse(
            answer=result.get('answer', result.get('response', str(result))),
            query_type=result.get('query_type'),
            model_used=result.get('model_used'),
            tools_used=result.get('tools_used', []),
        )

    except Exception as e:
        logger.error(f"Error processing ask query: {e}")
        return AskResponse(
            answer="I'm sorry, I couldn't process your question right now.",
            error="Internal server error",
        )
