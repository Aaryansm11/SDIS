# app/services/chunking.py
import hashlib
from typing import List, Dict, Any
from app.core.logging import get_logger

logger = get_logger(__name__)

class TextChunker:
    """Deterministic text chunking for embedding generation"""
    
    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk_text(self, text: str, document_id: str = None) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks with deterministic IDs
        
        Args:
            text: Input text to chunk
            document_id: Optional document ID for metadata
            
        Returns:
            List of chunk dictionaries with id, text, start, end positions
        """
        if not text or not text.strip():
            return []
        
        chunks = []
        text_length = len(text)
        start = 0
        chunk_index = 0
        
        while start < text_length:
            # Calculate end position
            end = min(start + self.chunk_size, text_length)
            
            # Try to break at sentence boundary if not at text end
            if end < text_length:
                # Look for sentence endings within last 100 chars
                last_part = text[max(start, end - 100):end]
                sentence_endings = ['.', '!', '?', '\n\n']
                
                best_break = -1
                for ending in sentence_endings:
                    pos = last_part.rfind(ending)
                    if pos > best_break and pos > len(last_part) // 2:
                        best_break = pos
                
                if best_break != -1:
                    end = max(start, end - 100) + best_break + 1
            
            # Extract chunk text
            chunk_text = text[start:end].strip()
            
            if chunk_text:  # Only add non-empty chunks
                # Generate deterministic chunk ID
                chunk_content = f"{document_id or 'doc'}:{start}:{end}:{chunk_text}"
                chunk_id = hashlib.sha256(chunk_content.encode()).hexdigest()
                
                chunks.append({
                    'chunk_id': chunk_id,
                    'text': chunk_text,
                    'start': start,
                    'end': end,
                    'length': len(chunk_text),
                    'index': chunk_index,
                    'document_id': document_id
                })
                
                chunk_index += 1
            
            # Move start position (with overlap)
            if end >= text_length:
                break
            
            start = max(start + 1, end - self.overlap)
            
            # Prevent infinite loops
            if start >= end:
                start = end
        
        logger.info(f"Created {len(chunks)} chunks from {text_length} characters")
        return chunks

# Utility functions
def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200, 
               document_id: str = None) -> List[Dict[str, Any]]:
    """Module-level function for text chunking"""
    chunker = TextChunker(chunk_size, overlap)
    return chunker.chunk_text(text, document_id)

def validate_chunks(chunks: List[Dict]) -> bool:
    """Validate that chunks have required fields and proper ordering"""
    if not chunks:
        return True
    
    required_fields = ['chunk_id', 'text', 'start', 'end']
    
    for i, chunk in enumerate(chunks):
        # Check required fields
        for field in required_fields:
            if field not in chunk:
                logger.error(f"Chunk {i} missing required field: {field}")
                return False
        
        # Check position ordering
        if chunk['start'] >= chunk['end']:
            logger.error(f"Chunk {i} has invalid positions: {chunk['start']} >= {chunk['end']}")
            return False
        
        # Check text length matches positions
        if len(chunk['text']) != (chunk['end'] - chunk['start']):
            logger.warning(f"Chunk {i} text length mismatch (after strip/normalization)")
    
    return True