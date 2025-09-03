# File: app/api/v1/health.py
# Health check endpoints for monitoring and load balancer probes.

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import logging
from datetime import datetime
from typing import Dict, Any
import os

from ...core.config import get_settings
from ...db.models import get_db_session

logger = logging.getLogger(__name__)

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    checks: Dict[str, Any]

def get_router() -> APIRouter:
    router = APIRouter(tags=["health"])
    
    @router.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        """
        Comprehensive health check for the service.
        Returns status of all critical dependencies.
        """
        settings = get_settings()
        checks = {}
        overall_status = "healthy"
        
        # Database connectivity check
        try:
            with get_db_session() as session:
                session.execute("SELECT 1")
            checks["database"] = {"status": "healthy", "message": "Connected"}
        except Exception as e:
            checks["database"] = {"status": "unhealthy", "message": f"Connection failed: {str(e)}"}
            overall_status = "unhealthy"
        
        # Vector store directory check
        try:
            vectorstore_path = settings.VECTORSTORE_PATH
            if os.path.exists(vectorstore_path) and os.access(vectorstore_path, os.W_OK):
                checks["vectorstore"] = {"status": "healthy", "message": "Directory accessible"}
            else:
                checks["vectorstore"] = {"status": "warning", "message": "Directory not found or not writable"}
                if overall_status == "healthy":
                    overall_status = "degraded"
        except Exception as e:
            checks["vectorstore"] = {"status": "unhealthy", "message": str(e)}
            overall_status = "unhealthy"
        
        # Audit log file check
        try:
            audit_path = settings.AUDIT_LOG_PATH
            audit_dir = os.path.dirname(audit_path)
            if os.path.exists(audit_dir) and os.access(audit_dir, os.W_OK):
                checks["audit_log"] = {"status": "healthy", "message": "Audit directory writable"}
            else:
                checks["audit_log"] = {"status": "warning", "message": "Audit directory not accessible"}
                if overall_status == "healthy":
                    overall_status = "degraded"
        except Exception as e:
            checks["audit_log"] = {"status": "unhealthy", "message": str(e)}
            overall_status = "unhealthy"
        
        # Embedding provider check
        try:
            if settings.EMBEDDING_PROVIDER == "openai":
                if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.startswith("sk-"):
                    checks["embeddings"] = {"status": "healthy", "message": "OpenAI API key configured"}
                else:
                    checks["embeddings"] = {"status": "warning", "message": "OpenAI API key not configured"}
                    if overall_status == "healthy":
                        overall_status = "degraded"
            else:
                checks["embeddings"] = {"status": "healthy", "message": f"Provider: {settings.EMBEDDING_PROVIDER}"}
        except Exception as e:
            checks["embeddings"] = {"status": "unhealthy", "message": str(e)}
            overall_status = "unhealthy"
        
        # Signing keys check
        try:
            if settings.SIGNING_PRIVATE_KEY and settings.SIGNING_PUBLIC_KEY:
                checks["crypto_signing"] = {"status": "healthy", "message": "Signing keys configured"}
            else:
                checks["crypto_signing"] = {"status": "warning", "message": "Signing keys not configured"}
                if overall_status == "healthy":
                    overall_status = "degraded"
        except Exception as e:
            checks["crypto_signing"] = {"status": "unhealthy", "message": str(e)}
            overall_status = "unhealthy"
        
        response = HealthResponse(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat(),
            version="1.0.0",
            checks=checks
        )
        
        # Return appropriate HTTP status
        if overall_status == "unhealthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=response.dict()
            )
        
        return response
    
    @router.get("/health/liveness")
    async def liveness_probe() -> Dict[str, str]:
        """
        Simple liveness probe for Kubernetes/container orchestration.
        Returns 200 if the service is running.
        """
        return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}
    
    @router.get("/health/readiness")
    async def readiness_probe() -> Dict[str, str]:
        """
        Readiness probe - checks if service is ready to handle requests.
        Performs minimal dependency checks.
        """
        try:
            # Quick database check
            with get_db_session() as session:
                session.execute("SELECT 1")
            
            return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
            
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"status": "not_ready", "error": str(e)}
            )
    
    return router