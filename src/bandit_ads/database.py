"""
Database models and connection management for the ads budget optimizer.

Supports SQLite (development) and PostgreSQL (production).
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager

from src.bandit_ads.utils import get_logger

Base = declarative_base()
logger = get_logger('database')


class Campaign(Base):
    """Campaign model for storing campaign information."""
    __tablename__ = 'campaigns'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    budget = Column(Float, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    status = Column(String(50), default='active')  # active, paused, completed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    arms = relationship("Arm", back_populates="campaign", cascade="all, delete-orphan")
    metrics = relationship("Metric", back_populates="campaign", cascade="all, delete-orphan")
    agent_states = relationship("AgentState", back_populates="campaign", cascade="all, delete-orphan")


class Arm(Base):
    """Arm model for storing ad configuration arms."""
    __tablename__ = 'arms'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False)
    platform = Column(String(100), nullable=False)
    channel = Column(String(100), nullable=False)
    creative = Column(String(255), nullable=False)
    bid = Column(Float, nullable=False)
    # Platform-specific entity IDs (e.g., Google Ads campaign_id, ad_group_id, keyword_id)
    # Stored as JSON string: {"campaign_id": "123", "ad_group_id": "456", "keyword_id": "789"}
    platform_entity_ids = Column(Text, nullable=True)  # JSON string for platform-specific IDs
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="arms")
    metrics = relationship("Metric", back_populates="arm", cascade="all, delete-orphan")
    agent_states = relationship("AgentState", back_populates="arm", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"Arm(id={self.id}, platform={self.platform}, channel={self.channel}, creative={self.creative}, bid={self.bid})"


class Metric(Base):
    """Time-series metrics for arms."""
    __tablename__ = 'metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False)
    arm_id = Column(Integer, ForeignKey('arms.id'), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    # Performance metrics
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)
    cost = Column(Float, default=0.0)
    roas = Column(Float, default=0.0)
    
    # Derived metrics
    ctr = Column(Float, default=0.0)  # Click-through rate
    cvr = Column(Float, default=0.0)  # Conversion rate
    
    # Metadata
    source = Column(String(50), default='api')  # api, webhook, simulated
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="metrics")
    arm = relationship("Arm", back_populates="metrics")
    
    def __repr__(self):
        return f"Metric(arm_id={self.arm_id}, timestamp={self.timestamp}, roas={self.roas:.2f})"


class AgentState(Base):
    """Agent state for persistence across restarts."""
    __tablename__ = 'agent_states'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False)
    arm_id = Column(Integer, ForeignKey('arms.id'), nullable=False)
    
    # Beta distribution parameters
    alpha = Column(Float, default=1.0)
    beta = Column(Float, default=1.0)
    
    # Performance tracking
    spending = Column(Float, default=0.0)
    impressions = Column(Integer, default=0)
    rewards = Column(Float, default=0.0)
    reward_variance = Column(Float, default=0.0)
    trials = Column(Integer, default=0)
    risk_score = Column(Float, default=0.0)
    
    # Contextual bandit state (stored as JSON string)
    contextual_state = Column(Text, nullable=True)  # JSON string for linear model params
    
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="agent_states")
    arm = relationship("Arm", back_populates="agent_states")


class APILog(Base):
    """Log of API calls for monitoring and debugging."""
    __tablename__ = 'api_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False, index=True)
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), default='GET')
    status_code = Column(Integer, nullable=True)
    response_time = Column(Float, nullable=True)  # seconds
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    request_data = Column(Text, nullable=True)  # JSON string
    response_data = Column(Text, nullable=True)  # JSON string (truncated)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class DatabaseManager:
    """Manages database connections and operations."""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager.
        
        Args:
            database_url: Database URL (e.g., 'sqlite:///data.db' or 'postgresql://user:pass@host/db')
                         If None, uses SQLite in project data directory
        """
        if database_url is None:
            # Default to SQLite in data directory
            data_dir = Path(__file__).parent.parent.parent / 'data'
            data_dir.mkdir(exist_ok=True)
            db_path = data_dir / 'bandit_ads.db'
            database_url = f'sqlite:///{db_path}'
        
        self.database_url = database_url
        self.is_sqlite = database_url.startswith('sqlite')
        
        # Configure engine
        if self.is_sqlite:
            # SQLite-specific configuration
            self.engine = create_engine(
                database_url,
                connect_args={'check_same_thread': False},
                poolclass=StaticPool,
                echo=False  # Set to True for SQL debugging
            )
        else:
            # PostgreSQL or other databases
            self.engine = create_engine(
                database_url,
                pool_size=10,
                max_overflow=20,
                echo=False
            )
        
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        logger.info(f"Database initialized: {database_url}")
    
    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created")
    
    def drop_tables(self):
        """Drop all database tables (use with caution!)."""
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("Database tables dropped")
    
    @contextmanager
    def get_session(self) -> Session:
        """
        Get a database session context manager.
        
        Usage:
            with db_manager.get_session() as session:
                # Use session
                pass
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {str(e)}")
            raise
        finally:
            session.close()
    
    def get_session(self) -> Session:
        """
        Get a database session (non-context manager version).
        
        Note: You must call session.close() when done.
        
        Usage:
            session = db_manager.get_session()
            try:
                # Use session
                pass
            finally:
                session.close()
        """
        return self.SessionLocal()
    
    def health_check(self) -> bool:
        """Check if database connection is healthy."""
        try:
            from sqlalchemy import text
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager(database_url: Optional[str] = None) -> DatabaseManager:
    """
    Get or create the global database manager instance.
    
    Args:
        database_url: Optional database URL (only used on first call)
    
    Returns:
        DatabaseManager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(database_url)
    return _db_manager


def init_database(database_url: Optional[str] = None, create_tables: bool = True):
    """
    Initialize the database.
    
    Args:
        database_url: Optional database URL
        create_tables: Whether to create tables if they don't exist
    """
    db_manager = get_db_manager(database_url)
    if create_tables:
        db_manager.create_tables()
    return db_manager
