# File: tests/unit/test_chunking.py
# Unit tests for chunk_text, normalization.

import pytest
from app.services.chunking import chunk_text
from app.utils.text import normalize_whitespace, clean_text_for_embedding

class TestChunking:
    
    def test_chunk_text_basic(self):
        """Test basic text chunking functionality."""
        text = "This is sentence one. This is sentence two. This is sentence three. This is sentence four."
        chunks = chunk_text(text, chunk_size=50, overlap=10)
        
        assert len(chunks) >= 1
        assert all("chunk_id" in chunk for chunk in chunks)
        assert all("text" in chunk for chunk in chunks)
        assert all("start" in chunk for chunk in chunks)
        assert all("end" in chunk for chunk in chunks)
    
    def test_chunk_deterministic_ids(self):
        """Test that chunk IDs are deterministic based on content."""
        text = "Identical content for testing deterministic hashing."
        chunks1 = chunk_text(text, chunk_size=100)
        chunks2 = chunk_text(text, chunk_size=100)
        
        assert len(chunks1) == len(chunks2)
        for c1, c2 in zip(chunks1, chunks2):
            assert c1["chunk_id"] == c2["chunk_id"]
    
    def test_chunk_overlap(self):
        """Test that overlapping chunks share content."""
        text = "Word one. Word two. Word three. Word four. Word five. Word six."
        chunks = chunk_text(text, chunk_size=30, overlap=15)
        
        if len(chunks) > 1:
            # Check that consecutive chunks have overlapping content
            chunk1_end = chunks[0]["text"][-15:]
            chunk2_start = chunks[1]["text"][:15]
            # Some overlap should exist (not exact due to word boundaries)
            assert len(set(chunk1_end.split()) & set(chunk2_start.split())) > 0
    
    def test_chunk_empty_text(self):
        """Test chunking with empty or whitespace-only text."""
        empty_chunks = chunk_text("", chunk_size=100)
        assert len(empty_chunks) == 0
        
        whitespace_chunks = chunk_text("   \n\t  ", chunk_size=100)
        assert len(whitespace_chunks) == 0
    
    def test_chunk_metadata_integrity(self):
        """Test that chunk metadata is consistent."""
        text = "This is a test document with multiple sentences. Each sentence should be tracked properly."
        chunks = chunk_text(text, chunk_size=40, overlap=10)
        
        for chunk in chunks:
            # Verify start/end positions
            assert chunk["start"] >= 0
            assert chunk["end"] <= len(text)
            assert chunk["start"] < chunk["end"]
            
            # Verify chunk text matches positions
            expected_text = text[chunk["start"]:chunk["end"]].strip()
            assert chunk["text"].strip() in expected_text or expected_text in chunk["text"].strip()

class TestTextUtils:
    
    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        messy_text = "This  has    multiple\n\n\nspaces\tand\ttabs."
        normalized = normalize_whitespace(messy_text)
        
        assert "  " not in normalized  # No double spaces
        assert "\n\n" not in normalized  # No double newlines
        assert "\t" not in normalized  # No tabs
        assert normalized.strip() == normalized  # No leading/trailing whitespace
    
    def test_clean_text_for_embedding(self):
        """Test text cleaning for embeddings."""
        dirty_text = "Text with\x00control\x01chars and ™special© symbols"
        clean = clean_text_for_embedding(dirty_text)
        
        # Should remove control characters
        assert "\x00" not in clean
        assert "\x01" not in clean
        
        # Should preserve readable content
        assert "Text with" in clean
        assert "control" in clean
        assert "chars" in clean
    
    def test_clean_preserves_meaningful_content(self):
        """Test that cleaning preserves meaningful text."""
        text = "Important business document with key findings."
        clean = clean_text_for_embedding(text)
        
        # All words should be preserved
        original_words = set(text.lower().split())
        clean_words = set(clean.lower().split())
        
        # Should preserve all meaningful words
        meaningful_words = original_words - {"with"}  # Minor words might be filtered
        preserved_words = meaningful_words & clean_words
        assert len(preserved_words) >= len(meaningful_words) * 0.8  # At least 80% preserved