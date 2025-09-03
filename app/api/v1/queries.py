# File: app/api/v1/queries.py
# Search / summarize / retrieve endpoints. Uses vectorstore and embeddings and calls summarizer and audit.

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
from typing import List, Optional
import uuid
import json
from datetime import datetime

from ..models import SummarizeRequest, SummarizeResponse
from ...services.embeddings import get_embedding_batch
from ...services.vectorstore import search as vector_search
from ...services.rbac import check_permission
from ...services.redaction import redact_text, detect_pii
from ...services.auditlog import write_audit_event
from ...db.repository import get_document_chunks
from ...utils.validators import validate_tenant_id

logger = logging.getLogger(__name__)
security = HTTPBearer()

def get_router() -> APIRouter:
    router = APIRouter(prefix="/v1/queries", tags=["queries"])
    
    @router.post("/search")
    async def search_text(
        tenant_id: str,
        query: str,
        top_k: int = 5,
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> List[dict]:
        """
        Search documents using vector similarity.
        Returns redacted results based on user permissions.
        """
        try:
            # Validate tenant
            if not validate_tenant_id(tenant_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid tenant ID"
                )
            
            # Verify authentication
            from ...api.v1.auth import verify_token
            claims = verify_token(credentials.credentials)
            user_id = claims.get("user_id")
            token_tenant_id = claims.get("tenant_id")
            
            if token_tenant_id != tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied for this tenant"
                )
            
            # Check search permission
            if not check_permission(user_id, tenant_id, "document:search"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to search documents"
                )
            
            # Generate query embedding
            query_vectors = get_embedding_batch([query])
            if not query_vectors:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to generate query embedding"
                )
            
            # Search vector store
            search_results = vector_search(tenant_id, query_vectors[0], top_k)
            
            # Apply redaction based on user role
            redacted_results = []
            can_view_pii = check_permission(user_id, tenant_id, "pii:view")
            
            for result in search_results:
                chunk_text = result.get("text", "")
                
                if not can_view_pii:
                    # Detect and redact PII
                    pii_spans = detect_pii(chunk_text)
                    redacted_text, _ = redact_text(chunk_text, pii_spans, mode="mask")
                    result["text"] = redacted_text
                
                redacted_results.append({
                    "chunk_id": result["vector_id"],
                    "score": float(result["score"]),
                    "text": result["text"],
                    "metadata": result.get("metadata", {})
                })
            
            # Log search audit event
            audit_event = {
                "timestamp": datetime.utcnow().isoformat(),
                "tenant_id": tenant_id,
                "user_id": user_id,
                "action": "search",
                "resource": f"query:{query[:100]}",
                "metadata": {
                    "query_length": len(query),
                    "results_count": len(redacted_results),
                    "top_k": top_k
                }
            }
            write_audit_event(audit_event)
            
            return redacted_results
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Search operation failed"
            )
    
    @router.post("/summarize", response_model=SummarizeResponse)
    async def summarize_doc(
        request: SummarizeRequest,
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> SummarizeResponse:
        """
        Generate summary for a document or query-specific content.
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
            
            # Apply redaction if user cannot view PII
            can_view_pii = check_permission(user_id, request.tenant_id, "pii:view")
            processed_chunks = []
            
            for chunk in chunks:
                chunk_text = chunk.get("text", "")
                if not can_view_pii:
                    pii_spans = detect_pii(chunk_text)
                    redacted_text, _ = redact_text(chunk_text, pii_spans, mode="mask")
                    chunk_text = redacted_text
                processed_chunks.append(chunk_text)
            
            # Generate summary (simple concatenation for now - in production would use LLM)
            full_text = "\n\n".join(processed_chunks)
            
            # Basic extractive summary - take first few sentences
            sentences = full_text.split('. ')
            summary_sentences = sentences[:3]  # First 3 sentences
            summary = '. '.join(summary_sentences)
            if summary and not summary.endswith('.'):
                summary += '.'
            
            # Generate highlights (key phrases)
            highlights = []
            if request.query:
                # Find sentences containing query terms
                query_words = request.query.lower().split()
                for sentence in sentences[:10]:  # Check first 10 sentences
                    if any(word in sentence.lower() for word in query_words):
                        highlights.append(sentence.strip())
                        if len(highlights) >= 3:
                            break
            else:
                # Default highlights - sentences with certain keywords
                keywords = ["important", "key", "significant", "main", "primary"]
                for sentence in sentences[:10]:
                    if any(keyword in sentence.lower() for keyword in keywords):
                        highlights.append(sentence.strip())
                        if len(highlights) >= 3:
                            break
            
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
                    "pii_redacted": not can_view_pii
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
                detail="Summarization failed"
            )
    
    return router