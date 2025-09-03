# File: app/api/v1/audit.py
# Audit log retrieval and verification endpoints.

from fastapi import APIRouter, Depends, HTTPException, status, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import logging
from typing import Dict, Any

from ...services.auditlog import read_audit_event
from ...services.rbac import check_permission
from ...utils.validators import validate_tenant_id

logger = logging.getLogger(__name__)
security = HTTPBearer()

class AuditEventResponse(BaseModel):
    audit_event: Dict[str, Any]
    signature_valid: bool
    verification_timestamp: str

def get_router() -> APIRouter:
    router = APIRouter(prefix="/v1/audit", tags=["audit"])
    
    @router.get("/{audit_id}", response_model=AuditEventResponse)
    async def get_audit_event(
        audit_id: str = Path(..., description="Audit event ID"),
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> AuditEventResponse:
        """
        Retrieve and verify an audit event by ID.
        Requires audit:read permission for the tenant.
        """
        try:
            # Verify authentication
            from ...api.v1.auth import verify_token
            claims = verify_token(credentials.credentials)
            user_id = claims.get("user_id")
            
            # Read audit event
            audit_data = read_audit_event(audit_id)
            
            if not audit_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Audit event not found"
                )
            
            # Extract tenant from audit event for permission check
            event_tenant_id = audit_data.get("audit_event", {}).get("tenant_id")
            
            if not event_tenant_id:
                # System-level audit event, requires system admin
                roles = claims.get("roles", [])
                if "system_admin" not in roles:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="System admin role required"
                    )
            else:
                # Tenant-specific audit event
                if not check_permission(user_id, event_tenant_id, "audit:read"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient permissions to read audit events"
                    )
            
            logger.info("Audit event retrieved", extra={
                "audit_id": audit_id,
                "user_id": user_id,
                "signature_valid": audit_data["signature_valid"]
            })
            
            from datetime import datetime
            return AuditEventResponse(
                audit_event=audit_data["audit_event"],
                signature_valid=audit_data["signature_valid"],
                verification_timestamp=datetime.utcnow().isoformat()
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Audit retrieval failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve audit event"
            )
    
    return router