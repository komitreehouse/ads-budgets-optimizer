"""
Authentication and Access Control

Multi-user support with role-based access control.
"""

from typing import Optional, Dict, List
from enum import Enum
from datetime import datetime, timedelta
import hashlib
import secrets

from src.bandit_ads.database import get_db_manager, Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from src.bandit_ads.utils import get_logger

logger = get_logger('auth')


class UserRole(Enum):
    """User roles."""
    ADMIN = "admin"  # Full access
    ANALYST = "analyst"  # Read + write (overrides)
    VIEWER = "viewer"  # Read only


# Database models for authentication
class User(Base):
    """User model."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default='viewer')  # admin, analyst, viewer
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    campaign_access = relationship("CampaignAccess", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class CampaignAccess(Base):
    """Campaign access control."""
    __tablename__ = 'campaign_access'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False)
    can_read = Column(Boolean, default=True)
    can_write = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="campaign_access")
    campaign = relationship("Campaign")


class Session(Base):
    """User session."""
    __tablename__ = 'sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="sessions")


class AuthManager:
    """Manages authentication and authorization."""
    
    def __init__(self):
        """Initialize auth manager."""
        self.db_manager = get_db_manager()
        logger.info("Auth manager initialized")
    
    def hash_password(self, password: str) -> str:
        """Hash a password."""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def create_user(
        self,
        email: str,
        username: str,
        password: str,
        role: str = "viewer"
    ) -> Optional[User]:
        """Create a new user."""
        try:
            with self.db_manager.get_session() as session:
                # Check if user exists
                existing = session.query(User).filter(
                    (User.email == email) | (User.username == username)
                ).first()
                
                if existing:
                    logger.warning(f"User already exists: {email}")
                    return None
                
                # Create user
                user = User(
                    email=email,
                    username=username,
                    password_hash=self.hash_password(password),
                    role=role,
                    active=True
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                
                logger.info(f"Created user: {email} ({role})")
                return user
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return None
    
    def authenticate(self, email: str, password: str) -> Optional[Session]:
        """Authenticate user and create session."""
        try:
            with self.db_manager.get_session() as session:
                user = session.query(User).filter(
                    User.email == email,
                    User.active == True
                ).first()
                
                if not user:
                    logger.warning(f"Authentication failed: user not found {email}")
                    return None
                
                # Check password
                password_hash = self.hash_password(password)
                if user.password_hash != password_hash:
                    logger.warning(f"Authentication failed: invalid password for {email}")
                    return None
                
                # Create session
                token = secrets.token_urlsafe(32)
                expires_at = datetime.utcnow() + timedelta(days=7)
                
                session_obj = Session(
                    user_id=user.id,
                    token=token,
                    expires_at=expires_at
                )
                session.add(session_obj)
                
                # Update last login
                user.last_login = datetime.utcnow()
                
                session.commit()
                session.refresh(session_obj)
                
                logger.info(f"User authenticated: {email}")
                return session_obj
        except Exception as e:
            logger.error(f"Error authenticating: {str(e)}")
            return None
    
    def get_user_from_token(self, token: str) -> Optional[User]:
        """Get user from session token."""
        try:
            with self.db_manager.get_session() as session:
                session_obj = session.query(Session).filter(
                    Session.token == token,
                    Session.expires_at > datetime.utcnow()
                ).first()
                
                if not session_obj:
                    return None
                
                return session_obj.user
        except Exception as e:
            logger.error(f"Error getting user from token: {str(e)}")
            return None
    
    def check_access(
        self,
        user: User,
        campaign_id: int,
        operation: str = "read"
    ) -> bool:
        """
        Check if user has access to campaign operation.
        
        Args:
            user: User object
            campaign_id: Campaign ID
            operation: "read" or "write"
        
        Returns:
            True if access granted
        """
        # Admin has full access
        if user.role == "admin":
            return True
        
        # Check campaign-specific access
        with self.db_manager.get_session() as session:
            access = session.query(CampaignAccess).filter(
                CampaignAccess.user_id == user.id,
                CampaignAccess.campaign_id == campaign_id
            ).first()
            
            if not access:
                # Default: viewer can read, analyst can read+write
                if operation == "read":
                    return user.role in ["viewer", "analyst"]
                else:
                    return user.role == "analyst"
            
            if operation == "read":
                return access.can_read
            else:
                return access.can_write
    
    def grant_campaign_access(
        self,
        user_id: int,
        campaign_id: int,
        can_read: bool = True,
        can_write: bool = False
    ) -> bool:
        """Grant campaign access to user."""
        try:
            with self.db_manager.get_session() as session:
                access = CampaignAccess(
                    user_id=user_id,
                    campaign_id=campaign_id,
                    can_read=can_read,
                    can_write=can_write
                )
                session.add(access)
                session.commit()
                logger.info(f"Granted access: user {user_id} -> campaign {campaign_id}")
                return True
        except Exception as e:
            logger.error(f"Error granting access: {str(e)}")
            return False


# Global auth manager instance
_auth_manager_instance: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """Get or create global auth manager instance."""
    global _auth_manager_instance
    if _auth_manager_instance is None:
        _auth_manager_instance = AuthManager()
    return _auth_manager_instance
