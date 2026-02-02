"""
Change Tracking System

Logs every allocation change, decision, and modification with full context.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from src.bandit_ads.database import get_db_manager, Base
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship

from src.bandit_ads.utils import get_logger

# Import User to ensure it's registered with SQLAlchemy before relationships are set up
try:
    from src.bandit_ads.auth import User
except ImportError:
    User = None  # Auth module not loaded yet

logger = get_logger('change_tracker')


class AllocationChange(Base):
    """Tracks allocation changes with full context."""
    __tablename__ = 'allocation_changes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False)
    arm_id = Column(Integer, ForeignKey('arms.id'), nullable=False)
    
    # Change details
    old_allocation = Column(Float, nullable=False)
    new_allocation = Column(Float, nullable=False)
    change_percent = Column(Float, nullable=False)
    
    # Context
    change_reason = Column(Text, nullable=True)  # Human-readable reason
    factors = Column(JSON, nullable=True)  # Contributing factors (JSON)
    mmm_factors = Column(JSON, nullable=True)  # MMM factor contributions
    
    # Optimizer state at time of change
    optimizer_state = Column(JSON, nullable=True)  # Alpha, beta, risk scores, etc.
    
    # Performance context
    performance_before = Column(JSON, nullable=True)  # ROAS, CTR, etc. before change
    performance_after = Column(JSON, nullable=True)  # ROAS, CTR, etc. after change
    
    # Metadata
    change_type = Column(String(50), nullable=False)  # auto, manual, override
    initiated_by = Column(Integer, ForeignKey('users.id'), nullable=True)  # User ID if manual
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    campaign = relationship("Campaign")
    arm = relationship("Arm")
    user = relationship("User", foreign_keys=[initiated_by])


class DecisionLog(Base):
    """Logs all optimizer decisions and reasoning."""
    __tablename__ = 'decision_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False)
    
    # Decision details
    decision_type = Column(String(50), nullable=False)  # allocation, pause, resume, etc.
    decision_data = Column(JSON, nullable=False)  # Decision details
    
    # Reasoning
    reasoning = Column(Text, nullable=True)  # Why this decision was made
    factors_considered = Column(JSON, nullable=True)  # Factors that influenced decision
    confidence_score = Column(Float, nullable=True)  # 0.0-1.0
    
    # Context
    optimizer_state = Column(JSON, nullable=True)
    performance_context = Column(JSON, nullable=True)
    
    # Metadata
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    campaign = relationship("Campaign")


class ChangeTracker:
    """Tracks all changes and decisions."""
    
    def __init__(self):
        """Initialize change tracker."""
        self.db_manager = get_db_manager()
        logger.info("Change tracker initialized")
    
    def log_allocation_change(
        self,
        campaign_id: int,
        arm_id: int,
        old_allocation: float,
        new_allocation: float,
        change_type: str = "auto",
        change_reason: Optional[str] = None,
        factors: Optional[Dict[str, Any]] = None,
        mmm_factors: Optional[Dict[str, Any]] = None,
        optimizer_state: Optional[Dict[str, Any]] = None,
        performance_before: Optional[Dict[str, Any]] = None,
        performance_after: Optional[Dict[str, Any]] = None,
        initiated_by: Optional[int] = None
    ) -> Optional[AllocationChange]:
        """
        Log an allocation change.
        
        Args:
            campaign_id: Campaign ID
            arm_id: Arm ID
            old_allocation: Previous allocation
            new_allocation: New allocation
            change_type: "auto", "manual", "override"
            change_reason: Human-readable reason
            factors: Contributing factors
            mmm_factors: MMM factor contributions
            optimizer_state: Optimizer state at time of change
            performance_before: Performance metrics before change
            performance_after: Performance metrics after change
            initiated_by: User ID if manual change
        
        Returns:
            AllocationChange object
        """
        try:
            change_percent = ((new_allocation - old_allocation) / old_allocation * 100) if old_allocation > 0 else 0
            
            with self.db_manager.get_session() as session:
                change = AllocationChange(
                    campaign_id=campaign_id,
                    arm_id=arm_id,
                    old_allocation=old_allocation,
                    new_allocation=new_allocation,
                    change_percent=change_percent,
                    change_reason=change_reason,
                    factors=factors,
                    mmm_factors=mmm_factors,
                    optimizer_state=optimizer_state,
                    performance_before=performance_before,
                    performance_after=performance_after,
                    change_type=change_type,
                    initiated_by=initiated_by,
                    timestamp=datetime.utcnow()
                )
                session.add(change)
                session.commit()
                session.refresh(change)
                
                logger.info(
                    f"Logged allocation change: campaign {campaign_id}, arm {arm_id}, "
                    f"{old_allocation:.2%} -> {new_allocation:.2%} ({change_type})"
                )
                return change
        except Exception as e:
            logger.error(f"Error logging allocation change: {str(e)}")
            return None
    
    def log_decision(
        self,
        campaign_id: int,
        decision_type: str,
        decision_data: Dict[str, Any],
        reasoning: Optional[str] = None,
        factors_considered: Optional[Dict[str, Any]] = None,
        confidence_score: Optional[float] = None,
        optimizer_state: Optional[Dict[str, Any]] = None,
        performance_context: Optional[Dict[str, Any]] = None
    ) -> Optional[DecisionLog]:
        """
        Log an optimizer decision.
        
        Args:
            campaign_id: Campaign ID
            decision_type: Type of decision
            decision_data: Decision details
            reasoning: Why this decision was made
            factors_considered: Factors that influenced decision
            confidence_score: Confidence score (0.0-1.0)
            optimizer_state: Optimizer state
            performance_context: Performance context
        
        Returns:
            DecisionLog object
        """
        try:
            with self.db_manager.get_session() as session:
                decision = DecisionLog(
                    campaign_id=campaign_id,
                    decision_type=decision_type,
                    decision_data=decision_data,
                    reasoning=reasoning,
                    factors_considered=factors_considered,
                    confidence_score=confidence_score,
                    optimizer_state=optimizer_state,
                    performance_context=performance_context,
                    timestamp=datetime.utcnow()
                )
                session.add(decision)
                session.commit()
                session.refresh(decision)
                
                logger.info(f"Logged decision: campaign {campaign_id}, type {decision_type}")
                return decision
        except Exception as e:
            logger.error(f"Error logging decision: {str(e)}")
            return None
    
    def get_allocation_history(
        self,
        campaign_id: int,
        days: int = 7,
        arm_id: Optional[int] = None
    ) -> List[AllocationChange]:
        """Get allocation change history."""
        try:
            from datetime import timedelta
            
            start_date = datetime.utcnow() - timedelta(days=days)
            
            with self.db_manager.get_session() as session:
                query = session.query(AllocationChange).filter(
                    AllocationChange.campaign_id == campaign_id,
                    AllocationChange.timestamp >= start_date
                )
                
                if arm_id:
                    query = query.filter(AllocationChange.arm_id == arm_id)
                
                return query.order_by(AllocationChange.timestamp.desc()).all()
        except Exception as e:
            logger.error(f"Error getting allocation history: {str(e)}")
            return []
    
    def get_decision_history(
        self,
        campaign_id: int,
        days: int = 7,
        decision_type: Optional[str] = None
    ) -> List[DecisionLog]:
        """Get decision history."""
        try:
            from datetime import timedelta
            
            start_date = datetime.utcnow() - timedelta(days=days)
            
            with self.db_manager.get_session() as session:
                query = session.query(DecisionLog).filter(
                    DecisionLog.campaign_id == campaign_id,
                    DecisionLog.timestamp >= start_date
                )
                
                if decision_type:
                    query = query.filter(DecisionLog.decision_type == decision_type)
                
                return query.order_by(DecisionLog.timestamp.desc()).all()
        except Exception as e:
            logger.error(f"Error getting decision history: {str(e)}")
            return []


# Global change tracker instance
_change_tracker_instance: Optional[ChangeTracker] = None


def get_change_tracker() -> ChangeTracker:
    """Get or create global change tracker instance."""
    global _change_tracker_instance
    if _change_tracker_instance is None:
        _change_tracker_instance = ChangeTracker()
    return _change_tracker_instance
