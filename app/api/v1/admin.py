# File: app/api/v1/admin.py
# Admin router for tenant management and reindex jobs.

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import logging
from typing import Dict, Any

from ...services.rbac import create_role, assign_role, check_permission
from ...services.vectorstore import create_index
from ...services.embeddings import get_embedding_batch
from ...db.repository import create_tenant as db_create_tenant, get_document_chunks
from ...utils.validators import validate_tenant_id

logger = logging.getLogger(__name__)
security = HTTPBearer()

class CreateTenantRequest(BaseModel):
    name: str
    admin_email: EmailStr

class CreateTenantResponse(BaseModel):
    tenant_id: str
    name: str
    admin_email: str
    status: str

class ReindexRequest(BaseModel):
    tenant_id: str

class ReindexResponse(BaseModel):
    status: str
    tenant_id: str
    message: str

def get_router() -> APIRouter:
    router = APIRouter(prefix="/v1/admin", tags=["admin"])
    
    @router.post("/tenants", response_model=CreateTenantResponse)
    async def create_tenant(
        request: CreateTenantRequest,
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> CreateTenantResponse:
        """
        Create a new tenant with default roles and admin user.
        Requires system admin permissions.
        """
        try:
            # Verify authentication and system admin role
            from ...api.v1.auth import verify_token
            claims = verify_token(credentials.credentials)
            user_id = claims.get("user_id")
            roles = claims.get("roles", [])
            
            if "system_admin" not in roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="System admin role required to create tenants"
                )
            
            # Create tenant in database
            tenant_record = db_create_tenant(request.name, request.admin_email)
            tenant_id = tenant_record["id"]
            
            # Create default roles for the tenant
            default_roles = [
                ("admin", ["document:upload", "document:search", "document:summarize", "pii:view", "tenant:manage"]),
                ("editor", ["document:upload", "document:search", "document:summarize"]),
                ("viewer", ["document:search", "document:summarize"]),
                ("analyst", ["document:search", "document:summarize", "pii:view"])
            ]
            
            for role_name, permissions in default_roles:
                create_role(tenant_id, role_name, permissions)
            
            # Create vector index for tenant (dimension 1536 for OpenAI embeddings)
            create_index(tenant_id, dim=1536)
            
            logger.info("Tenant created successfully", extra={
                "tenant_id": tenant_id,
                "tenant_name": request.name,
                "admin_email": request.admin_email,
                "created_by": user_id
            })
            
            return CreateTenantResponse(
                tenant_id=tenant_id,
                name=request.name,
                admin_email=request.admin_email,
                status="created"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Tenant creation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create tenant"
            )
    
    @router.post("/reindex", response_model=ReindexResponse)
    async def reindex_tenant(
        request: ReindexRequest,
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> ReindexResponse:
        """
        Trigger reindexing of all documents for a tenant.
        Rebuilds the vector store from scratch.
        """
        try:
            # Validate tenant
            if not validate_tenant_id(request.tenant_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid tenant ID"
                )
            
            # Verify authentication
            from ...api.v1.auth import verify_token
            claims = verify_token(credentials.credentials)
            user_id = claims.get("user_id")
            token_tenant_id = claims.get("tenant_id")
            
            # Check if user has admin access to this tenant or is system admin
            roles = claims.get("roles", [])
            is_system_admin = "system_admin" in roles
            is_tenant_admin = (token_tenant_id == request.tenant_id and 
                             check_permission(user_id, request.tenant_id, "tenant:manage"))
            
            if not (is_system_admin or is_tenant_admin):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to reindex tenant"
                )
            
            # Get all document chunks for tenant
            from ...db.repository import get_all_tenant_chunks
            all_chunks = get_all_tenant_chunks(request.tenant_id)
            
            if not all_chunks:
                return ReindexResponse(
                    status="completed",
                    tenant_id=request.tenant_id,
                    message="No documents found to reindex"
                )
            
            # Recreate vector index
            create_index(request.tenant_id, dim=1536)
            
            # Extract texts and generate embeddings
            chunk_texts = [chunk["text"] for chunk in all_chunks]
            embeddings = get_embedding_batch(chunk_texts)
            
            # Add vectors to index
            from ...services.vectorstore import add_vectors
            metadata_list = [{
                "chunk_id": chunk["id"],
                "document_id": chunk["document_id"],
                "start": chunk["start"],
                "end": chunk["end"]
            } for chunk in all_chunks]
            
            vector_ids = add_vectors(request.tenant_id, embeddings, metadata_list)
            
            logger.info("Tenant reindexed successfully", extra={
                "tenant_id": request.tenant_id,
                "chunks_reindexed": len(vector_ids),
                "initiated_by": user_id
            })
            
            return ReindexResponse(
                status="completed",
                tenant_id=request.tenant_id,
                message=f"Reindexed {len(vector_ids)} chunks successfully"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Reindexing failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Reindexing operation failed"
            )
    
    @router.post("/summarize", response_model=SummarizeResponse)
    async def summarize_doc(
        request: SummarizeRequest,
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> SummarizeResponse:
        """
        Generate summary for a document with optional query focus.
        Creates signed audit log entry.
        """
        try:
            # Validate tenant
            if not validate_tenant_id(request.tenant_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid tenant ID"
                )
            
            # Verify authentication
            from ...api.v1.auth import verify_token
            claims = verify_token(credentials.credentials)
            user_id = claims.get("user_id")
            token_tenant_id = claims.get("tenant_id")
            
            if token_tenant_id != request.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied for this tenant"
                )
            
            # Check summarize permission
            if not check_permission(user_id, request.tenant_id, "document:summarize"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to summarize documents"
                )
            
            # Get document chunks
            chunks = get_document_chunks(request.tenant_id, str(request.document_id))
            if not chunks:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found"
                )
            
            # Apply redaction based on permissions
            can_view_pii = check_permission(user_id, request.tenant_id, "pii:view")
            processed_chunks = []
            
            for chunk in chunks:
                chunk_text = chunk.get("text", "")
                if not can_view_pii:
                    pii_spans = detect_pii(chunk_text)
                    redacted_text, _ = redact_text(chunk_text, pii_spans, mode="mask")
                    chunk_text = redacted_text
                processed_chunks.append(chunk_text)
            
            # Generate summary
            full_text = "\n\n".join(processed_chunks)
            
            if request.query:
                # Query-focused summary
                query_words = request.query.lower().split()
                relevant_sentences = []
                
                for sentence in full_text.split('.'):
                    if any(word in sentence.lower() for word in query_words):
                        relevant_sentences.append(sentence.strip())
                        if len(relevant_sentences) >= 5:
                            break
                
                summary = '. '.join(relevant_sentences[:3])
                if summary and not summary.endswith('.'):
                    summary += '.'
                
                highlights = relevant_sentences[:3]
            else:
                # General document summary
                sentences = full_text.split('.')
                summary = '. '.join(sentences[:3])
                if summary and not summary.endswith('.'):
                    summary += '.'
                
                # Extract key sentences as highlights
                highlights = [s.strip() for s in sentences[1:4] if s.strip()]
            
            # Create audit event
            audit_event = {
                "timestamp": datetime.utcnow().isoformat(),
                "tenant_id": request.tenant_id,
                "user_id": user_id,
                "action": "summarize",
                "resource": f"document:{request.document_id}",
                "metadata": {
                    "query": request.query,
                    "summary_length": len(summary),
                    "chunks_processed": len(processed_chunks),
                    "pii_redacted": not can_view_pii,
                    "result_hash": hash(summary + str(highlights))
                }
            }
            
            # Write and sign audit event
            signed_audit_id = write_audit_event(audit_event)
            
            logger.info("Document summarized", extra={
                "tenant_id": request.tenant_id,
                "document_id": str(request.document_id),
                "user_id": user_id,
                "audit_id": signed_audit_id
            })
            
            return SummarizeResponse(
                summary=summary,
                highlights=highlights,
                signed_audit_id=signed_audit_id
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document summarization failed"
            )
    
    return router