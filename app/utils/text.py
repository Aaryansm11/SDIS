# app/utils/text.py
import re
import unicodedata
from typing import str

def normalize_whitespace(text: str) -> str:
    """Normalize whitespace and newlines in text"""
    if not text:
        return ""
    
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Normalize newlines (convert \r\n and \r to \n)
    text = re.sub(r'\r\n|\r', '\n', text)
    
    # Replace multiple newlines with double newline (paragraph break)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    
    # Strip leading/trailing whitespace
    return text.strip()

def clean_text_for_embedding(text: str) -> str:
    """Clean text for embedding generation"""
    if not text:
        return ""
    
    # Normalize unicode
    text = unicodedata.normalize('NFKD', text)
    
    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', text)
    
    # Remove excessive punctuation
    text = re.sub(r'[.]{3,}', '...', text)
    text = re.sub(r'[!]{2,}', '!', text)
    text = re.sub(r'[?]{2,}', '?', text)
    
    # Clean up common document artifacts
    text = re.sub(r'\bPage \d+\b', '', text)  # Page numbers
    text = re.sub(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', '[DATE]', text)  # Dates
    
    # Normalize whitespace last
    return normalize_whitespace(text)

def extract_sentences(text: str) -> List[str]:
    """Extract sentences from text using simple rule-based approach"""
    if not text:
        return []
    
    # Simple sentence boundary detection
    sentence_endings = re.compile(r'[.!?]+\s+')
    sentences = sentence_endings.split(text)
    
    # Clean and filter sentences
    cleaned_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) > 10:  # Filter very short fragments
            cleaned_sentences.append(sentence)
    
    return cleaned_sentences

def truncate_text(text: str, max_length: int, preserve_words: bool = True) -> str:
    """Truncate text to maximum length, optionally preserving word boundaries"""
    if not text or len(text) <= max_length:
        return text
    
    if not preserve_words:
        return text[:max_length] + "..."
    
    # Find last complete word before max_length
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.8:  # Don't cut too much
        return text[:last_space] + "..."
    else:
        return text[:max_length] + "..."

def estimate_tokens(text: str, chars_per_token: float = 4.0) -> int:
    """Rough estimation of token count for text"""
    if not text:
        return 0
    return int(len(text) / chars_per_token)

def validate_text_quality(text: str) -> Dict[str, Any]:
    """Validate text quality and return metrics"""
    if not text:
        return {
            'is_valid': False,
            'length': 0,
            'issues': ['empty_text']
        }
    
    issues = []
    
    # Check length
    if len(text) < 50:
        issues.append('too_short')
    
    # Check character diversity
    unique_chars = len(set(text.lower()))
    if unique_chars < 10:
        issues.append('low_diversity')
    
    # Check for excessive repetition
    words = text.lower().split()
    if len(words) > 10:
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        max_freq = max(word_freq.values())
        if max_freq > len(words) * 0.3:
            issues.append('excessive_repetition')
    
    # Check encoding issues
    if '�' in text or '\ufffd' in text:
        issues.append('encoding_issues')
    
    return {
        'is_valid': len(issues) == 0,
        'length': len(text),
        'word_count': len(words) if 'words' in locals() else 0,
        'unique_chars': unique_chars,
        'issues': issues
    }