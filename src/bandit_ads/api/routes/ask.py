"""
Ask API endpoint — natural language query interface.

Routes user questions to the OrchestratorAgent for real-time,
explainable answers about campaigns, performance, and optimizer decisions.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

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
async def ask_question(request: AskRequest):
    """
    Ask a natural language question about campaigns and optimization.

    Uses the OrchestratorAgent to route queries to the appropriate tools
    (change tracker, explanation generator, metrics) and return a
    plain-language answer.
    """
    try:
        from src.bandit_ads.orchestrator import OrchestratorAgent
        orchestrator = OrchestratorAgent()

        result = orchestrator.process_query(
            query=request.query,
            campaign_id=request.campaign_id
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
            answer=f"I'm sorry, I couldn't process your question right now. Error: {str(e)}",
            error=str(e),
        )
