"""
Recommendation System with Approval Workflow

Provides recommendations to analysts with option to approve/override.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum

from src.bandit_ads.database import get_db_manager, Base
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from src.bandit_ads.utils import get_logger
from src.bandit_ads.optimization_service import get_optimization_service

logger = get_logger('recommendations')


class RecommendationStatus(Enum):
    """Recommendation status."""
    PENDING = "pending"  # Waiting for user approval
    APPROVED = "approved"  # User approved, will be applied
    REJECTED = "rejected"  # User rejected
    APPLIED = "applied"  # Recommendation has been applied
    EXPIRED = "expired"  # Recommendation expired


class RecommendationType(Enum):
    """Recommendation type."""
    ALLOCATION_CHANGE = "allocation_change"
    BUDGET_ADJUSTMENT = "budget_adjustment"
    CAMPAIGN_PAUSE = "campaign_pause"
    CAMPAIGN_RESUME = "campaign_resume"
    ARM_DISABLE = "arm_disable"
    ARM_ENABLE = "arm_enable"


# Database model for recommendations
class Recommendation(Base):
    """Recommendation model."""
    __tablename__ = 'recommendations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Who created/requested
    
    recommendation_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    
    # Recommendation details (JSON)
    details = Column(Text, nullable=False)  # JSON string
    
    # Status tracking
    status = Column(String(50), default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    applied_at = Column(DateTime, nullable=True)
    
    # Approval tracking
    approved_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Auto-apply settings
    auto_apply = Column(Boolean, default=False)
    auto_apply_after_hours = Column(Integer, nullable=True)  # Auto-apply after N hours if not reviewed
    
    # Relationships
    campaign = relationship("Campaign")
    creator = relationship("User", foreign_keys=[user_id])
    approver = relationship("User", foreign_keys=[approved_by])


class RecommendationEngine:
    """Generates recommendations based on optimizer state."""
    
    def __init__(self):
        """Initialize recommendation engine."""
        self.optimization_service = get_optimization_service()
        logger.info("Recommendation engine initialized")
    
    def generate_allocation_recommendation(
        self,
        campaign_id: int,
        arm_id: int,
        suggested_allocation: float,
        reason: str,
        confidence: float = 0.7
    ) -> Dict[str, Any]:
        """
        Generate an allocation change recommendation.
        
        Args:
            campaign_id: Campaign ID
            arm_id: Arm ID
            suggested_allocation: Suggested allocation (0.0-1.0)
            reason: Reason for recommendation
            confidence: Confidence score (0.0-1.0)
        
        Returns:
            Recommendation dictionary
        """
        # Get current state
        campaign_status = self.optimization_service.get_campaign_status(campaign_id)
        if not campaign_status:
            return {"error": "Campaign not found"}
        
        current_allocation = 0.0  # TODO: Get from optimizer state
        
        recommendation = {
            "type": RecommendationType.ALLOCATION_CHANGE.value,
            "title": f"Allocation Change Recommendation: Arm {arm_id}",
            "description": reason,
            "campaign_id": campaign_id,
            "arm_id": arm_id,
            "current_allocation": current_allocation,
            "suggested_allocation": suggested_allocation,
            "change_percent": ((suggested_allocation - current_allocation) / current_allocation * 100) if current_allocation > 0 else 0,
            "confidence": confidence,
            "estimated_impact": {
                "additional_spend": 0,  # TODO: Calculate
                "expected_revenue": 0,  # TODO: Calculate
                "roas_impact": 0  # TODO: Calculate
            }
        }
        
        return recommendation
    
    def generate_budget_recommendation(
        self,
        campaign_id: int,
        suggested_budget: float,
        reason: str
    ) -> Dict[str, Any]:
        """Generate a budget adjustment recommendation."""
        campaign_status = self.optimization_service.get_campaign_status(campaign_id)
        if not campaign_status:
            return {"error": "Campaign not found"}
        
        current_budget = campaign_status.get('performance', {}).get('total_budget', 0)
        
        recommendation = {
            "type": RecommendationType.BUDGET_ADJUSTMENT.value,
            "title": f"Budget Adjustment Recommendation",
            "description": reason,
            "campaign_id": campaign_id,
            "current_budget": current_budget,
            "suggested_budget": suggested_budget,
            "change_percent": ((suggested_budget - current_budget) / current_budget * 100) if current_budget > 0 else 0
        }
        
        return recommendation


class RecommendationManager:
    """Manages recommendations and approval workflow."""
    
    def __init__(self):
        """Initialize recommendation manager."""
        self.db_manager = get_db_manager()
        self.engine = RecommendationEngine()
        logger.info("Recommendation manager initialized")
    
    def create_recommendation(
        self,
        campaign_id: int,
        recommendation_type: str,
        title: str,
        description: str,
        details: Dict[str, Any],
        user_id: Optional[int] = None,
        auto_apply: bool = False,
        expires_in_hours: Optional[int] = 24
    ) -> Optional[Recommendation]:
        """
        Create a recommendation.
        
        Args:
            campaign_id: Campaign ID
            recommendation_type: Type of recommendation
            title: Recommendation title
            description: Recommendation description
            details: Recommendation details (dict)
            user_id: User who created/requested
            auto_apply: Whether to auto-apply if not reviewed
            expires_in_hours: Hours until expiration
        
        Returns:
            Recommendation object
        """
        try:
            import json
            
            expires_at = None
            if expires_in_hours:
                expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
            
            with self.db_manager.get_session() as session:
                recommendation = Recommendation(
                    campaign_id=campaign_id,
                    user_id=user_id,
                    recommendation_type=recommendation_type,
                    title=title,
                    description=description,
                    details=json.dumps(details),
                    status=RecommendationStatus.PENDING.value,
                    auto_apply=auto_apply,
                    expires_at=expires_at
                )
                session.add(recommendation)
                session.commit()
                session.refresh(recommendation)
                
                logger.info(f"Created recommendation: {recommendation.id} for campaign {campaign_id}")
                return recommendation
        except Exception as e:
            logger.error(f"Error creating recommendation: {str(e)}")
            return None
    
    def approve_recommendation(
        self,
        recommendation_id: int,
        user_id: int
    ) -> bool:
        """Approve a recommendation."""
        try:
            with self.db_manager.get_session() as session:
                recommendation = session.query(Recommendation).filter(
                    Recommendation.id == recommendation_id,
                    Recommendation.status == RecommendationStatus.PENDING.value
                ).first()
                
                if not recommendation:
                    return False
                
                # Apply recommendation
                success = self._apply_recommendation(recommendation)
                
                if success:
                    recommendation.status = RecommendationStatus.APPROVED.value
                    recommendation.approved_by = user_id
                    recommendation.approved_at = datetime.utcnow()
                    recommendation.applied_at = datetime.utcnow()
                    session.commit()
                    logger.info(f"Approved recommendation: {recommendation_id}")
                    return True
                else:
                    return False
        except Exception as e:
            logger.error(f"Error approving recommendation: {str(e)}")
            return False
    
    def reject_recommendation(
        self,
        recommendation_id: int,
        user_id: int,
        reason: str
    ) -> bool:
        """Reject a recommendation."""
        try:
            with self.db_manager.get_session() as session:
                recommendation = session.query(Recommendation).filter(
                    Recommendation.id == recommendation_id,
                    Recommendation.status == RecommendationStatus.PENDING.value
                ).first()
                
                if not recommendation:
                    return False
                
                recommendation.status = RecommendationStatus.REJECTED.value
                recommendation.approved_by = user_id
                recommendation.rejection_reason = reason
                session.commit()
                
                logger.info(f"Rejected recommendation: {recommendation_id}")
                return True
        except Exception as e:
            logger.error(f"Error rejecting recommendation: {str(e)}")
            return False
    
    def _apply_recommendation(self, recommendation: Recommendation) -> bool:
        """Apply a recommendation."""
        import json
        
        try:
            details = json.loads(recommendation.details)
            rec_type = RecommendationType(recommendation.recommendation_type)
            
            if rec_type == RecommendationType.ALLOCATION_CHANGE:
                # Apply allocation change
                # TODO: Implement allocation override
                logger.info(f"Applying allocation change: {details}")
                return True
            elif rec_type == RecommendationType.BUDGET_ADJUSTMENT:
                # Apply budget adjustment
                # TODO: Implement budget update
                logger.info(f"Applying budget adjustment: {details}")
                return True
            elif rec_type == RecommendationType.CAMPAIGN_PAUSE:
                self.optimization_service.pause_campaign(recommendation.campaign_id)
                return True
            elif rec_type == RecommendationType.CAMPAIGN_RESUME:
                self.optimization_service.resume_campaign(recommendation.campaign_id)
                return True
            else:
                logger.warning(f"Unknown recommendation type: {rec_type}")
                return False
        except Exception as e:
            logger.error(f"Error applying recommendation: {str(e)}")
            return False
    
    def get_pending_recommendations(
        self,
        campaign_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> List[Recommendation]:
        """Get pending recommendations."""
        try:
            with self.db_manager.get_session() as session:
                query = session.query(Recommendation).filter(
                    Recommendation.status == RecommendationStatus.PENDING.value
                )
                
                if campaign_id:
                    query = query.filter(Recommendation.campaign_id == campaign_id)
                if user_id:
                    query = query.filter(Recommendation.user_id == user_id)
                
                return query.all()
        except Exception as e:
            logger.error(f"Error getting pending recommendations: {str(e)}")
            return []


# Global recommendation manager instance
_recommendation_manager_instance: Optional[RecommendationManager] = None


def get_recommendation_manager() -> RecommendationManager:
    """Get or create global recommendation manager instance."""
    global _recommendation_manager_instance
    if _recommendation_manager_instance is None:
        _recommendation_manager_instance = RecommendationManager()
    return _recommendation_manager_instance
