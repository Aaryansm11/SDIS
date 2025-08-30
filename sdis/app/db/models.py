# app/db/models.py
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, Boolean, JSON, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    admin_email = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    configs = Column(JSON, default=dict)  # Tenant-specific configuration
    is_active = Column(Boolean, default=True)
    
    # Relationships
    users = relationship("User", back_populates="tenant")
    documents = relationship("Document", back_populates="tenant")
    audit_events = relationship("AuditEvent", back_populates="tenant")

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Tenant relationship
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    tenant = relationship("Tenant", back_populates="users")
    
    # RBAC
    user_roles = relationship("UserRole", back_populates="user")
    audit_events = relationship("AuditEvent", back_populates="user")

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    permissions = Column(JSON, default=list)  # List of permission strings
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Tenant scoped
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    
    # Relationships
    user_roles = relationship("UserRole", back_populates="role")

class UserRole(Base):
    __tablename__ = "user_roles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    mime_type = Column(String(100))
    file_size = Column(Integer)  # bytes
    storage_path = Column(String(1000), nullable=False)
    text_length = Column(Integer)  # character count after extraction
    status = Column(String(50), default="processing")  # processing|completed|failed
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    
    # Tenant scoped
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    tenant = relationship("Tenant", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

class Chunk(Base):
    __tablename__ = "chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id = Column(String(64), nullable=False, unique=True)  # SHA256 hash
    text_hash = Column(String(64), nullable=False)  # SHA256 of original text
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)
    chunk_text = Column(Text)  # Store redacted version
    original_text = Column(Text)  # Store original for admin access
    redaction_metadata = Column(JSON, default=dict)  # PII spans and redaction info
    vector_id = Column(String(64))  # Reference to FAISS vector
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Document relationship
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    document = relationship("Document", back_populates="chunks")

class AuditEvent(Base):
    __tablename__ = "audit_events"
    
    audit_id = Column(String(64), primary_key=True)  # SHA256 hash
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    action = Column(String(100), nullable=False)  # upload|search|summarize|admin
    resource = Column(String(500))  # document_id, query hash, etc.
    resource_type = Column(String(50))  # document|query|tenant
    user_agent = Column(String(500))
    ip_address = Column(String(45))
    
    # Request/response data
    request_data = Column(JSON, default=dict)
    response_data = Column(JSON, default=dict)
    result_hash = Column(String(64))  # SHA256 of response payload
    
    # Relationships
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    tenant = relationship("Tenant", back_populates="audit_events")
    user = relationship("User", back_populates="audit_events")
    
    # Cryptographic signature
    signature = Column(Text, nullable=False)  # Base64 encoded signature
    signature_algorithm = Column(String(50), default="RS256")

class VectorMetadata(Base):
    __tablename__ = "vector_metadata"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vector_id = Column(String(64), nullable=False, unique=True)
    chunk_id = Column(String(64), ForeignKey("chunks.chunk_id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    faiss_index = Column(Integer, nullable=False)  # Index in FAISS
    embedding_version = Column(String(50), default="v1")  # Track embedding model version
    created_at = Column(DateTime, default=datetime.utcnow)