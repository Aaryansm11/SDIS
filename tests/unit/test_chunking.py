"""
Unit tests for chunking.
"""
def test_chunk_text_basic():
    from app.services.chunking import chunk_text
    text = "a" * 2500
    chunks = chunk_text(text, chunk_size=1000, overlap=200)
    assert len(chunks) >= 2
