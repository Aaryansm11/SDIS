# app/services/vectorstore.py
import os
import pickle
import tempfile
import shutil
from typing import List, Dict, Any, Optional
import numpy as np
import faiss
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.repository import VectorRepository
from app.core.logging import get_logger

logger = get_logger(__name__)

class FAISSVectorStore:
    """Per-tenant FAISS vector store manager"""
    
    def __init__(self, db_session: Session):
        self.settings = get_settings()
        self.db = db_session
        self.vector_repo = VectorRepository(db_session)
        self.base_path = self.settings.vectorstore_path
        
        # Ensure base directory exists
        os.makedirs(self.base_path, exist_ok=True)
    
    def _get_index_path(self, tenant_id: str) -> str:
        """Get file path for tenant's FAISS index"""
        return os.path.join(self.base_path, f"{tenant_id}.faiss")
    
    def _get_metadata_path(self, tenant_id: str) -> str:
        """Get file path for tenant's metadata pickle"""
        return os.path.join(self.base_path, f"{tenant_id}_meta.pkl")
    
    def create_index(self, tenant_id: str, dim: int) -> None:
        """Create empty FAISS index for tenant"""
        
        # Create flat L2 index (could be upgraded to IVF for larger datasets)
        index = faiss.IndexFlatL2(dim)
        
        # Save empty index
        index_path = self._get_index_path(tenant_id)
        faiss.write_index(index, index_path)
        
        # Save empty metadata
        metadata_path = self._get_metadata_path(tenant_id)
        with open(metadata_path, 'wb') as f:
            pickle.dump({}, f)
        
        logger.info(f"Created FAISS index for tenant {tenant_id} (dim={dim})")
    
    def _load_index(self, tenant_id: str) -> Optional[faiss.Index]:
        """Load FAISS index for tenant"""
        index_path = self._get_index_path(tenant_id)
        
        if not os.path.exists(index_path):
            return None
        
        try:
            return faiss.read_index(index_path)
        except Exception as e:
            logger.error(f"Failed to load FAISS index for {tenant_id}: {e}")
            return None
    
    def _load_metadata(self, tenant_id: str) -> Dict[int, str]:
        """Load metadata mapping faiss_index -> vector_id"""
        metadata_path = self._get_metadata_path(tenant_id)
        
        if not os.path.exists(metadata_path):
            return {}
        
        try:
            with open(metadata_path, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"Failed to load metadata for {tenant_id}: {e}")
            return {}
    
    def _save_index(self, tenant_id: str, index: faiss.Index, 
                   metadata: Dict[int, str]) -> None:
        """Atomically save index and metadata"""
        
        # Write to temporary files first
        index_path = self._get_index_path(tenant_id)
        metadata_path = self._get_metadata_path(tenant_id)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.faiss') as tmp_index:
            faiss.write_index(index, tmp_index.name)
            tmp_index_path = tmp_index.name
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as tmp_meta:
            pickle.dump(metadata, tmp_meta)
            tmp_meta_path = tmp_meta.name
        
        # Atomic move
        try:
            shutil.move(tmp_index_path, index_path)
            shutil.move(tmp_meta_path, metadata_path)
        except Exception as e:
            # Cleanup on failure
            for path in [tmp_index_path, tmp_meta_path]:
                if os.path.exists(path):
                    os.unlink(path)
            raise e
    
    def add_vectors(self, tenant_id: str, vectors: List[List[float]], 
                   metadata: List[Dict[str, Any]]) -> List[str]:
        """Add vectors to tenant's index"""
        
        if not vectors or not metadata:
            return []
        
        if len(vectors) != len(metadata):
            raise ValueError("Vectors and metadata must have same length")
        
        # Load existing index and metadata
        index = self._load_index(tenant_id)
        if index is None:
            # Create new index
            dim = len(vectors[0])
            self.create_index(tenant_id, dim)
            index = self._load_index(tenant_id)
        
        index_metadata = self._load_metadata(tenant_id)
        
        # Convert to numpy array
        vectors_np = np.array(vectors, dtype=np.float32)
        
        # Generate vector IDs and update metadata
        vector_ids = []
        start_idx = index.ntotal
        
        for i, meta in enumerate(metadata):
            vector_id = meta.get('chunk_id', f"vec_{start_idx + i}")
            vector_ids.append(vector_id)
            index_metadata[start_idx + i] = vector_id
            
            # Save to DB
            self.vector_repo.save_vector_metadata(
                vector_id=vector_id,
                chunk_id=meta['chunk_id'],
                tenant_id=tenant_id,
                faiss_index=start_idx + i
            )
        
        # Add to FAISS index
        index.add(vectors_np)
        
        # Save updated index and metadata
        self._save_index(tenant_id, index, index_metadata)
        
        logger.info(f"Added {len(vectors)} vectors to {tenant_id} index")
        return vector_ids
    
    def search(self, tenant_id: str, query_vector: List[float], 
              top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar vectors"""
        
        index = self._load_index(tenant_id)
        if index is None or index.ntotal == 0:
            return []
        
        index_metadata = self._load_metadata(tenant_id)
        
        # Convert query to numpy
        query_np = np.array([query_vector], dtype=np.float32)
        
        # Search
        scores, indices = index.search(query_np, min(top_k, index.ntotal))
        
        # Build results
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for not found
                continue
            
            vector_id = index_metadata.get(idx)
            if vector_id:
                results.append({
                    'vector_id': vector_id,
                    'score': float(score),
                    'faiss_index': int(idx)
                })
        
        return results
    
    def get_index_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get statistics about tenant's index"""
        index = self._load_index(tenant_id)
        
        if index is None:
            return {
                'exists': False,
                'total_vectors': 0,
                'dimension': 0
            }
        
        return {
            'exists': True,
            'total_vectors': index.ntotal,
            'dimension': index.d,
            'index_type': type(index).__name__
        }
    
    def delete_index(self, tenant_id: str) -> bool:
        """Delete tenant's index files"""
        index_path = self._get_index_path(tenant_id)
        metadata_path = self._get_metadata_path(tenant_id)
        
        deleted = False
        for path in [index_path, metadata_path]:
            if os.path.exists(path):
                try:
                    os.unlink(path)
                    deleted = True
                except Exception as e:
                    logger.error(f"Failed to delete {path}: {e}")
        
        return deleted

# Module-level service
_vectorstore_service: Optional[FAISSVectorStore] = None

def get_vectorstore_service(db: Session) -> FAISSVectorStore:
    """Get vectorstore service instance"""
    return FAISSVectorStore(db)

def create_index(db: Session, tenant_id: str, dim: int) -> None:
    """Module-level function to create index"""
    service = get_vectorstore_service(db)
    return service.create_index(tenant_id, dim)

def add_vectors(db: Session, tenant_id: str, vectors: List[List[float]], 
               metadata: List[Dict[str, Any]]) -> List[str]:
    """Module-level function to add vectors"""
    service = get_vectorstore_service(db)
    return service.add_vectors(tenant_id, vectors, metadata)

def search(db: Session, tenant_id: str, vector: List[float], top_k: int) -> List[Dict[str, Any]]:
    """Module-level function to search vectors"""
    service = get_vectorstore_service(db)
    return service.search(tenant_id, vector, top_k)