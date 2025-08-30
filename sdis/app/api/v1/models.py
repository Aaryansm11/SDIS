# app/api/v1/models.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

# Auth models
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user_id: str
    tenant_id: str

class TokenClaims(BaseModel):
    user_id: str
    tenant_id: str
    roles: List[str]
    exp: int

# Document upload models
class UploadResponse(BaseModel):
    document_id: UUID
    tenant_id: str
    status: str
    filename: str
    file_size: int

# Search models
class SearchRequest(BaseModel):
    tenant_id: str
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=50)
    include_metadata: bool = Field(default=True)

class SearchResult(BaseModel):
    chunk_id: str
    score: float
    text: str
    metadata: Dict[str, Any]
    document_id: UUID
    redaction_applied: bool

class SearchResponse(BaseModel):
    results: List[SearchResult]
    total_found: int
    query_id: str
    processing_time_ms: float

# Summarize models
class SummarizeRequest(BaseModel):
    tenant_id: str
    document_id: UUID
    query: Optional[str] = Field(default=None, max_length=1000)
    max_length: int = Field(default=500, ge=100, le=2000)

class SummarizeResponse(BaseModel):
    summary: str
    highlights: List[str]
    confidence_score: float
    signed_audit_id: str
    document_title: str

# Admin models
class CreateTenantRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    admin_email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')

class CreateTenantResponse(BaseModel):
    tenant_id: UUID
    name: str
    admin_user_id: UUID
    status: str

class ReindexRequest(BaseModel):
    tenant_id: str
    force: bool = Field(default=False)

class ReindexResponse(BaseModel):
    status: str
    job_id: str
    estimated_documents: int

# Audit models
class AuditEventResponse(BaseModel):
    audit_id: str
    timestamp: datetime
    action: str
    resource: str
    user_id: Optional[str]
    tenant_id: str
    signature_valid: bool
    request_data: Dict[str, Any]
    response_data: Dict[str, Any]

# Error models
class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None

# Health check
class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    services: Dict[str, str]  # service_name -> status