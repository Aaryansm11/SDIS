# File: app/api/v1/docs.py
# Document upload endpoint (multipart). Saves raw file and triggers ingestion.

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uuid
import logging
from typing import Optional

from ..models import UploadResponse
from ...services.ingestion import save_file_raw, ingest_document
from ...services.rbac import check_permission
from ...utils.validators import validate_tenant_id, validate_file_size
from ...core.config import get_settings

logger = logging.getLogger(__name__)
security = HTTPBearer()
settings = get_settings()

def get_router() -> APIRouter:
    router = APIRouter(prefix="/v1/docs", tags=["documents"])
    
    @router.post("/upload", response_model=UploadResponse)
    async def upload_document(
        tenant_id: str = Form(...),
        file: UploadFile = File(...),
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> UploadResponse:
        """
        Upload and ingest a document for a tenant.
        Validates file, extracts text, chunks, detects PII, and stores metadata.
        """
        try:
            # Validate tenant
            if not validate_tenant_id(tenant_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid tenant ID format"
                )
            
            # Verify JWT and extract user info
            from ...api.v1.auth import verify_token
            try:
                claims = verify_token(credentials.credentials)
                user_id = claims.get("user_id")
                token_tenant_id = claims.get("tenant_id")
                
                # Ensure user belongs to the tenant
                if token_tenant_id != tenant_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied for this tenant"
                    )
                
                # Check upload permission
                if not check_permission(user_id, tenant_id, "document:upload"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient permissions to upload documents"
                    )
                    
            except Exception as e:
                logger.error(f"Auth validation failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token"
                )
            
            # Read and validate file
            file_bytes = await file.read()
            
            if not validate_file_size(file_bytes, max_mb=50):
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="File size exceeds 50MB limit"
                )
            
            # Validate file type
            allowed_types = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain"}
            if file.content_type not in allowed_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unsupported file type. Only PDF, DOCX, and TXT files are allowed"
                )
            
            # Generate document ID
            document_id = str(uuid.uuid4())
            
            # Save raw file
            storage_path = save_file_raw(tenant_id, file_bytes, file.filename or "unnamed")
            
            # Trigger document ingestion
            ingest_result = ingest_document(tenant_id, storage_path, file.filename or "unnamed")
            
            logger.info(f"Document uploaded successfully", extra={
                "tenant_id": tenant_id,
                "document_id": document_id,
                "filename": file.filename,
                "file_size": len(file_bytes),
                "user_id": user_id
            })
            
            return UploadResponse(
                document_id=uuid.UUID(ingest_result["document_id"]),
                tenant_id=tenant_id,
                status="processing"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Upload failed: {e}", extra={
                "tenant_id": tenant_id,
                "filename": getattr(file, 'filename', 'unknown'),
                "error": str(e)
            })
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document upload failed"
            )
    
    return router