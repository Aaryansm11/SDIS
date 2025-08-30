# app/db/repository.py
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.models import Tenant, User, Document, Chunk, AuditEvent, VectorMetadata
from app.services.rbac import RBACService
from app.core.logging import get_logger

logger = get_logger(__name__)

class TenantRepository:
    """Repository for tenant operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.rbac = RBACService(db)
    
    def create_tenant(self, name: str, admin_email: str) -> Dict[str, Any]:
        """Create a new tenant with default admin user and roles"""
        try:
            # Create tenant
            tenant = Tenant(
                name=name,
                admin_email=admin_email,
                configs={}
            )
            
            self.db.add(tenant)
            self.db.flush()  # Get tenant ID without committing
            
            # Create default roles
            roles = self.rbac.create_default_roles(str(tenant.id))
            
            # Create admin user (placeholder - would integrate with auth service)
            admin_user = User(
                email=admin_email,
                password_hash="placeholder_hash",  # Set by auth service
                full_name="System Admin",
                tenant_id=tenant.id
            )
            
            self.db.add(admin_user)
            self.db.flush()
            
            # Assign admin role
            self.rbac.assign_role(str(admin_user.id), str(tenant.id), "admin")
            
            self.db.commit()
            
            logger.info(f"Created tenant '{name}' with admin user")
            
            return {
                'tenant_id': str(tenant.id),
                'name': tenant.name,
                'admin_email': tenant.admin_email,
                'admin_user_id': str(admin_user.id),
                'roles_created': len(roles),
                'created_at': tenant.created_at.isoformat()
            }
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Tenant creation failed: {e}")
            raise ValueError(f"Tenant with name '{name}' already exists")
    
    def get_tenant(self, tenant_id: str) -> Optional[Dict]:
        """Get tenant by ID"""
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return None
        
        return {
            'tenant_id': str(tenant.id),
            'name': tenant.name,
            'admin_email': tenant.admin_email,
            'is_active': tenant.is_active,
            'created_at': tenant.created_at.isoformat(),
            'configs': tenant.configs
        }

class DocumentRepository:
    """Repository for document operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def save_document_meta(self, tenant_id: str, document_id: str, 
                          filename: str, storage_path: str, 
                          file_size: int, mime_type: str = None,
                          uploaded_by: str = None) -> Dict[str, Any]:
        """Save document metadata"""
        
        document = Document(
            id=UUID(document_id),
            filename=filename,
            original_filename=filename,
            mime_type=mime_type,
            file_size=file_size,
            storage_path=storage_path,
            tenant_id=UUID(tenant_id),
            uploaded_by=UUID(uploaded_by) if uploaded_by else None,
            status="processing"
        )
        
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        
        logger.info(f"Saved document metadata: {document_id}")
        
        return {
            'document_id': str(document.id),
            'filename': document.filename,
            'storage_path': document.storage_path,
            'status': document.status,
            'created_at': document.created_at.isoformat()
        }
    
    def update_document_status(self, document_id: str, status: str, 
                              text_length: int = None) -> bool:
        """Update document processing status"""
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return False
        
        document.status = status
        if text_length is not None:
            document.text_length = text_length
        
        if status == "completed":
            document.processed_at = datetime.utcnow()
        
        self.db.commit()
        return True
    
    def get_document(self, tenant_id: str, document_id: str) -> Optional[Dict]:
        """Get document by ID within tenant"""
        document = (
            self.db.query(Document)
            .filter(Document.id == document_id)
            .filter(Document.tenant_id == tenant_id)
            .first()
        )
        
        if not document:
            return None
        
        return {
            'document_id': str(document.id),
            'filename': document.filename,
            'file_size': document.file_size,
            'text_length': document.text_length,
            'status': document.status,
            'created_at': document.created_at.isoformat(),
            'processed_at': document.processed_at.isoformat() if document.processed_at else None
        }
    
    def list_documents(self, tenant_id: str, limit: int = 100, 
                      offset: int = 0) -> List[Dict]:
        """List documents for a tenant"""
        documents = (
            self.db.query(Document)
            .filter(Document.tenant_id == tenant_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        
        return [
            {
                'document_id': str(doc.id),
                'filename': doc.filename,
                'file_size': doc.file_size,
                'status': doc.status,
                'created_at': doc.created_at.isoformat()
            }
            for doc in documents
        ]

class ChunkRepository:
    """Repository for chunk operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def save_chunk_meta(self, document_id: str, chunk_id: str, 
                       start: int, end: int, text: str, 
                       original_text: str = None,
                       redaction_metadata: Dict = None) -> None:
        """Save chunk metadata"""
        
        chunk = Chunk(
            chunk_id=chunk_id,
            text_hash=chunk_id,  # Using chunk_id as text hash for now
            start_char=start,
            end_char=end,
            chunk_text=text,
            original_text=original_text or text,
            redaction_metadata=redaction_metadata or {},
            document_id=UUID(document_id)
        )
        
        self.db.add(chunk)
        self.db.commit()
    
    def get_document_chunks(self, tenant_id: str, document_id: str) -> List[Dict]:
        """Get all chunks for a document"""
        chunks = (
            self.db.query(Chunk)
            .join(Document, Chunk.document_id == Document.id)
            .filter(Document.id == document_id)
            .filter(Document.tenant_id == tenant_id)
            .order_by(Chunk.start_char)
            .all()
        )
        
        return [
            {
                'chunk_id': chunk.chunk_id,
                'start': chunk.start_char,
                'end': chunk.end_char,
                'text': chunk.chunk_text,
                'length': len(chunk.chunk_text),
                'redaction_applied': bool(chunk.redaction_metadata),
                'vector_id': chunk.vector_id
            }
            for chunk in chunks
        ]
    
    def get_chunk_by_id(self, chunk_id: str, include_original: bool = False) -> Optional[Dict]:
        """Get chunk by ID"""
        chunk = self.db.query(Chunk).filter(Chunk.chunk_id == chunk_id).first()
        if not chunk:
            return None
        
        result = {
            'chunk_id': chunk.chunk_id,
            'text': chunk.chunk_text,
            'start': chunk.start_char,
            'end': chunk.end_char,
            'document_id': str(chunk.document_id),
            'redaction_metadata': chunk.redaction_metadata
        }
        
        if include_original:
            result['original_text'] = chunk.original_text
        
        return result

class VectorRepository:
    """Repository for vector metadata operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def save_vector_metadata(self, vector_id: str, chunk_id: str, 
                           tenant_id: str, faiss_index: int) -> None:
        """Save vector metadata mapping"""
        
        metadata = VectorMetadata(
            vector_id=vector_id,
            chunk_id=chunk_id,
            tenant_id=UUID(tenant_id),
            faiss_index=faiss_index
        )
        
        self.db.add(metadata)
        self.db.commit()
    
    def get_chunks_by_vector_ids(self, vector_ids: List[str]) -> Dict[str, Dict]:
        """Get chunk metadata for multiple vector IDs"""
        
        results = (
            self.db.query(VectorMetadata, Chunk, Document)
            .join(Chunk, VectorMetadata.chunk_id == Chunk.chunk_id)
            .join(Document, Chunk.document_id == Document.id)
            .filter(VectorMetadata.vector_id.in_(vector_ids))
            .all()
        )
        
        chunk_map = {}
        for vector_meta, chunk, document in results:
            chunk_map[vector_meta.vector_id] = {
                'chunk_id': chunk.chunk_id,
                'text': chunk.chunk_text,
                'document_id': str(document.id),
                'document_name': document.filename,
                'start': chunk.start_char,
                'end': chunk.end_char,
                'redaction_metadata': chunk.redaction_metadata
            }
        
        return chunk_map

# Module-level helper functions
def create_tenant(db: Session, name: str, admin_email: str) -> Dict[str, Any]:
    """Create a new tenant"""
    repo = TenantRepository(db)
    return repo.create_tenant(name, admin_email)

def save_document_meta(db: Session, tenant_id: str, document_id: str, 
                      storage_path: str, length: int, **kwargs) -> Dict[str, Any]:
    """Save document metadata"""
    repo = DocumentRepository(db)
    return repo.save_document_meta(
        tenant_id, document_id, storage_path, length, **kwargs
    )

def save_chunk_meta(db: Session, tenant_id: str, document_id: str, 
                   chunk_id: str, metadata: Dict[str, Any]) -> None:
    """Save chunk metadata"""
    repo = ChunkRepository(db)
    return repo.save_chunk_meta(
        document_id, chunk_id, 
        metadata['start'], metadata['end'], 
        metadata['text'], metadata.get('original_text'),
        metadata.get('redaction_metadata')
    )

def get_document_chunks(db: Session, tenant_id: str, document_id: str) -> List[Dict]:
    """Get document chunks"""
    repo = ChunkRepository(db)
    return repo.get_document_chunks(tenant_id, document_id)