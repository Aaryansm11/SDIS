# app/services/ingestion.py
import os
import hashlib
from typing import Dict, Any, Optional
from uuid import uuid4
import tempfile

from app.core.config import get_settings
from app.utils.text import normalize_whitespace, clean_text_for_embedding
from app.core.logging import get_logger

logger = get_logger(__name__)

class FileProcessor:
    """Handles file storage and text extraction"""
    
    def __init__(self):
        self.settings = get_settings()
        
        # Ensure storage directory exists
        if self.settings.storage_backend == "local":
            os.makedirs(self.settings.local_storage_path, exist_ok=True)
    
    def save_file_raw(self, tenant_id: str, file_bytes: bytes, filename: str) -> str:
        """Save raw file bytes to storage backend"""
        
        # Generate unique storage path
        file_id = str(uuid4())
        safe_filename = self._sanitize_filename(filename)
        
        if self.settings.storage_backend == "local":
            storage_path = os.path.join(
                self.settings.local_storage_path,
                tenant_id,
                f"{file_id}_{safe_filename}"
            )
            
            # Ensure tenant directory exists
            os.makedirs(os.path.dirname(storage_path), exist_ok=True)
            
            # Write file
            with open(storage_path, 'wb') as f:
                f.write(file_bytes)
            
            logger.info(f"Saved file to local storage: {storage_path}")
            return storage_path
            
        elif self.settings.storage_backend == "s3":
            # S3 implementation would go here
            raise NotImplementedError("S3 storage not yet implemented")
        
        else:
            raise ValueError(f"Unknown storage backend: {self.settings.storage_backend}")
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage"""
        import re
        
        # Remove dangerous characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
        
        # Limit length
        if len(filename) > 100:
            name, ext = os.path.splitext(filename)
            filename = name[:95] + ext
        
        return filename or "unnamed_file"
    
    def extract_text_from_pdf(self, storage_path: str) -> str:
        """Extract text from PDF file"""
        try:
            import fitz  # PyMuPDF
            
            with fitz.open(storage_path) as doc:
                text_parts = []
                for page in doc:
                    text_parts.append(page.get_text())
                
                raw_text = '\n'.join(text_parts)
                
            logger.info(f"Extracted {len(raw_text)} chars from PDF")
            return normalize_whitespace(raw_text)
            
        except ImportError:
            logger.error("PyMuPDF not installed, trying pdfplumber")
            return self._extract_text_with_pdfplumber(storage_path)
        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            raise RuntimeError(f"Cannot extract text from PDF: {e}")
    
    def _extract_text_with_pdfplumber(self, storage_path: str) -> str:
        """Fallback PDF extraction with pdfplumber"""
        try:
            import pdfplumber
            
            text_parts = []
            with pdfplumber.open(storage_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
            
            raw_text = '\n'.join(text_parts)
            return normalize_whitespace(raw_text)
            
        except ImportError:
            raise RuntimeError("Neither PyMuPDF nor pdfplumber is installed")
        except Exception as e:
            raise RuntimeError(f"PDF extraction failed: {e}")
    
    def extract_text_from_docx(self, storage_path: str) -> str:
        """Extract text from DOCX file"""
        try:
            from docx import Document
            
            doc = Document(storage_path)
            text_parts = []
            
            for paragraph in doc.paragraphs:
                text_parts.append(paragraph.text)
            
            raw_text = '\n'.join(text_parts)
            
            logger.info(f"Extracted {len(raw_text)} chars from DOCX")
            return normalize_whitespace(raw_text)
            
        except ImportError:
            raise RuntimeError("python-docx not installed")
        except Exception as e:
            logger.error(f"DOCX text extraction failed: {e}")
            raise RuntimeError(f"Cannot extract text from DOCX: {e}")
    
    def extract_text_from_txt(self, storage_path: str) -> str:
        """Extract text from plain text file"""
        try:
            # Try UTF-8 first, then fall back to other encodings
            encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
            
            for encoding in encodings:
                try:
                    with open(storage_path, 'r', encoding=encoding) as f:
                        text = f.read()
                    
                    logger.info(f"Extracted {len(text)} chars from TXT ({encoding})")
                    return normalize_whitespace(text)
                    
                except UnicodeDecodeError:
                    continue
            
            raise RuntimeError("Could not decode text file with any encoding")
            
        except Exception as e:
            logger.error(f"TXT extraction failed: {e}")
            raise RuntimeError(f"Cannot extract text from file: {e}")
    
    def ingest_document(self, tenant_id: str, storage_path: str, 
                       filename: str, mime_type: str = None) -> Dict[str, Any]:
        """
        Complete document ingestion pipeline
        
        Returns metadata about processed document
        """
        
        # Determine file type and extract text
        if mime_type == "application/pdf" or filename.lower().endswith('.pdf'):
            text = self.extract_text_from_pdf(storage_path)
        elif (mime_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
                           "application/msword"] or 
              filename.lower().endswith(('.docx', '.doc'))):
            text = self.extract_text_from_docx(storage_path)
        elif mime_type == "text/plain" or filename.lower().endswith(('.txt', '.md')):
            text = self.extract_text_from_txt(storage_path)
        else:
            raise ValueError(f"Unsupported file type: {mime_type or 'unknown'}")
        
        # Clean text for processing
        cleaned_text = clean_text_for_embedding(text)
        
        # Generate document metadata
        document_id = str(uuid4())
        text_hash = hashlib.sha256(cleaned_text.encode()).hexdigest()
        
        result = {
            'document_id': document_id,
            'tenant_id': tenant_id,
            'filename': filename,
            'storage_path': storage_path,
            'text_length': len(cleaned_text),
            'text_hash': text_hash,
            'status': 'text_extracted',
            'mime_type': mime_type
        }
        
        # Save extracted text to separate file for chunking
        text_path = storage_path + '.txt'
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_text)
        
        result['text_path'] = text_path
        
        logger.info(f"Ingested document {document_id}: {len(cleaned_text)} chars")
        return result

# Module-level functions
def save_file_raw(tenant_id: str, file_bytes: bytes, filename: str) -> str:
    """Module-level function to save file"""
    processor = FileProcessor()
    return processor.save_file_raw(tenant_id, file_bytes, filename)

def extract_text_from_pdf(storage_path: str) -> str:
    """Module-level function for PDF extraction"""
    processor = FileProcessor()
    return processor.extract_text_from_pdf(storage_path)

def extract_text_from_docx(storage_path: str) -> str:
    """Module-level function for DOCX extraction"""
    processor = FileProcessor()
    return processor.extract_text_from_docx(storage_path)

def ingest_document(tenant_id: str, storage_path: str, filename: str) -> Dict[str, Any]:
    """Module-level function for document ingestion"""
    processor = FileProcessor()
    return processor.ingest_document(tenant_id, storage_path, filename)