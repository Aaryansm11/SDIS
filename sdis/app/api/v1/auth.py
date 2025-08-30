# app/api/v1/auth.py
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import hashlib
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.api.v1.models import LoginRequest, LoginResponse, TokenClaims
from app.db.models import User
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def get_router() -> APIRouter:
    """Create and configure auth router"""
    router = APIRouter(prefix="/auth", tags=["authentication"])
    
    @router.post("/login", response_model=LoginResponse)
    async def login(request: LoginRequest, db: Session = Depends(get_database)):
        """Authenticate user and return JWT token"""
        return await authenticate_user(request.username, request.password, db)
    
    @router.post("/refresh")
    async def refresh_token(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_database)
    ):
        """Refresh an existing JWT token"""
        try:
            claims = verify_token(credentials.credentials)
            
            # Generate new token with extended expiration
            new_token = create_access_token(
                user_id=claims['user_id'],
                tenant_id=claims['tenant_id'],
                roles=claims['roles']
            )
            
            return {"access_token": new_token, "token_type": "bearer"}
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    @router.get("/me")
    async def get_current_user(
        current_user: Dict = Depends(get_current_user_dependency)
    ):
        """Get current user information"""
        return {
            "user_id": current_user["user_id"],
            "tenant_id": current_user["tenant_id"],
            "roles": current_user["roles"]
        }
    
    return router

async def authenticate_user(username: str, password: str, db: Session) -> LoginResponse:
    """Authenticate user credentials and return token"""
    
    # Find user by email (username)
    user = db.query(User).filter(User.email == username, User.is_active == True).first()
    
    if not user or not verify_password(password, user.password_hash):
        logger.warning(f"Failed login attempt for {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Get user roles (simplified - would use RBAC service)
    roles = ["viewer"]  # Default role for now
    
    # Create JWT token
    access_token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        roles=roles
    )
    
    settings = get_settings()
    
    logger.info(f"Successful login for user {user.id}")
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expiration_hours * 3600,
        user_id=str(user.id),
        tenant_id=str(user.tenant_id)
    )

def create_access_token(user_id: str, tenant_id: str, roles: List[str]) -> str:
    """Create JWT access token"""
    settings = get_settings()
    
    # Token expiration
    expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)
    
    # JWT payload
    payload = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "roles": roles,
        "exp": expire,
        "iat": datetime.utcnow(),
        "iss": settings.app_name
    }
    
    # Encode token
    token = jwt.encode(
        payload, 
        settings.jwt_secret, 
        algorithm=settings.jwt_algorithm
    )
    
    return token

def verify_token(token: str) -> Dict[str, Any]:
    """Verify and decode JWT token"""
    settings = get_settings()
    
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        
        # Validate required claims
        required_claims = ["user_id", "tenant_id", "roles", "exp"]
        for claim in required_claims:
            if claim not in payload:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Missing claim: {claim}"
                )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}"
        )

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)

# Dependencies for FastAPI
def get_current_user_dependency(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """FastAPI dependency to get current authenticated user"""
    return verify_token(credentials.credentials)

def require_permission(permission: str):
    """Decorator factory for permission-based route protection"""
    def permission_dependency(
        current_user: Dict = Depends(get_current_user_dependency),
        db: Session = Depends(get_database)
    ):
        from app.services.rbac import check_permission
        
        if not check_permission(
            db, 
            current_user["user_id"], 
            current_user["tenant_id"], 
            permission
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: {permission}"
            )
        
        return current_user
    
    return permission_dependency

# Placeholder for database dependency (would be defined in main.py)
def get_database():
    """Database session dependency placeholder"""
    pass