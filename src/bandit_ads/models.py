"""
Pydantic models for data validation and serialization.

These models provide type-safe interfaces for database operations
and API responses.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


class CampaignCreate(BaseModel):
    """Model for creating a new campaign."""
    name: str = Field(..., min_length=1, max_length=255)
    budget: float = Field(..., gt=0)
    start_date: datetime
    end_date: Optional[datetime] = None
    status: str = Field(default='active', pattern='^(active|paused|completed|cancelled)$')


class CampaignResponse(BaseModel):
    """Model for campaign response."""
    id: int
    name: str
    budget: float
    start_date: datetime
    end_date: Optional[datetime]
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ArmCreate(BaseModel):
    """Model for creating a new arm."""
    campaign_id: int
    platform: str = Field(..., min_length=1, max_length=100)
    channel: str = Field(..., min_length=1, max_length=100)
    creative: str = Field(..., min_length=1, max_length=255)
    bid: float = Field(..., gt=0)
    platform_entity_ids: Optional[Dict[str, Any]] = None  # Platform-specific IDs (e.g., {"campaign_id": "123", "ad_group_id": "456"})


class ArmResponse(BaseModel):
    """Model for arm response."""
    id: int
    campaign_id: int
    platform: str
    channel: str
    creative: str
    bid: float
    platform_entity_ids: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class MetricCreate(BaseModel):
    """Model for creating a new metric."""
    campaign_id: int
    arm_id: int
    timestamp: datetime
    impressions: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    conversions: int = Field(default=0, ge=0)
    revenue: float = Field(default=0.0, ge=0)
    cost: float = Field(default=0.0, ge=0)
    roas: Optional[float] = None
    source: str = Field(default='api', pattern='^(api|webhook|simulated)$')
    
    @validator('roas', always=True)
    def calculate_roas(cls, v, values):
        """Calculate ROAS if not provided."""
        if v is None:
            cost = values.get('cost', 0.0)
            revenue = values.get('revenue', 0.0)
            if cost > 0:
                return revenue / cost
            return 0.0
        return v
    
    @validator('clicks')
    def validate_clicks(cls, v, values):
        """Ensure clicks don't exceed impressions."""
        impressions = values.get('impressions', 0)
        if v > impressions:
            raise ValueError('clicks cannot exceed impressions')
        return v
    
    @validator('conversions')
    def validate_conversions(cls, v, values):
        """Ensure conversions don't exceed clicks."""
        clicks = values.get('clicks', 0)
        if v > clicks:
            raise ValueError('conversions cannot exceed clicks')
        return v


class MetricResponse(BaseModel):
    """Model for metric response."""
    id: int
    campaign_id: int
    arm_id: int
    timestamp: datetime
    impressions: int
    clicks: int
    conversions: int
    revenue: float
    cost: float
    roas: float
    ctr: float
    cvr: float
    source: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class AgentStateUpdate(BaseModel):
    """Model for updating agent state."""
    campaign_id: int
    arm_id: int
    alpha: float = Field(default=1.0, gt=0)
    beta: float = Field(default=1.0, gt=0)
    spending: float = Field(default=0.0, ge=0)
    impressions: int = Field(default=0, ge=0)
    rewards: float = Field(default=0.0)
    reward_variance: float = Field(default=0.0, ge=0)
    trials: int = Field(default=0, ge=0)
    risk_score: float = Field(default=0.0)
    contextual_state: Optional[Dict[str, Any]] = None


class AgentStateResponse(BaseModel):
    """Model for agent state response."""
    id: int
    campaign_id: int
    arm_id: int
    alpha: float
    beta: float
    spending: float
    impressions: int
    rewards: float
    reward_variance: float
    trials: int
    risk_score: float
    contextual_state: Optional[Dict[str, Any]]
    last_updated: datetime
    
    class Config:
        from_attributes = True


class APILogCreate(BaseModel):
    """Model for creating an API log entry."""
    platform: str = Field(..., min_length=1, max_length=50)
    endpoint: str = Field(..., min_length=1, max_length=255)
    method: str = Field(default='GET', pattern='^(GET|POST|PUT|DELETE|PATCH)$')
    status_code: Optional[int] = None
    response_time: Optional[float] = Field(None, ge=0)
    success: bool = True
    error_message: Optional[str] = None
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None


class APILogResponse(BaseModel):
    """Model for API log response."""
    id: int
    platform: str
    endpoint: str
    method: str
    status_code: Optional[int]
    response_time: Optional[float]
    success: bool
    error_message: Optional[str]
    timestamp: datetime
    
    class Config:
        from_attributes = True


class MetricAggregation(BaseModel):
    """Model for aggregated metrics."""
    arm_id: int
    start_date: datetime
    end_date: datetime
    total_impressions: int
    total_clicks: int
    total_conversions: int
    total_revenue: float
    total_cost: float
    avg_roas: float
    avg_ctr: float
    avg_cvr: float
