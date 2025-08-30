# app/services/redaction.py
import re
import hashlib
from typing import List, Dict, Tuple, Any
import spacy
from app.core.logging import get_logger

logger = get_logger(__name__)

class PIIDetector:
    """Detects PII using regex patterns and spaCy NER"""
    
    def __init__(self):
        self.patterns = {
            'ssn': re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b'),
            'phone': re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'credit_card': re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
            'date_of_birth': re.compile(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'),
            'zip_code': re.compile(r'\b\d{5}(?:-\d{4})?\b'),
        }
        
        # Try to load spaCy model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy model not found, using regex-only PII detection")
            self.nlp = None
    
    def detect_pii(self, text: str) -> List[Dict[str, Any]]:
        """Detect PII spans in text using regex and optionally spaCy"""
        spans = []
        
        # Regex-based detection
        for pii_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                spans.append({
                    'type': pii_type,
                    'start': match.start(),
                    'end': match.end(),
                    'text': match.group(),
                    'confidence': 0.9,  # High confidence for regex matches
                    'method': 'regex'
                })
        
        # spaCy NER detection
        if self.nlp:
            doc = self.nlp(text)
            for ent in doc.ents:
                if ent.label_ in ['PERSON', 'ORG', 'GPE', 'DATE', 'MONEY']:
                    spans.append({
                        'type': ent.label_.lower(),
                        'start': ent.start_char,
                        'end': ent.end_char,
                        'text': ent.text,
                        'confidence': 0.7,  # Lower confidence for NER
                        'method': 'spacy'
                    })
        
        # Remove overlapping spans (keep highest confidence)
        spans = self._remove_overlaps(spans)
        return sorted(spans, key=lambda x: x['start'])
    
    def _remove_overlaps(self, spans: List[Dict]) -> List[Dict]:
        """Remove overlapping spans, keeping the one with highest confidence"""
        if not spans:
            return spans
        
        spans = sorted(spans, key=lambda x: (x['start'], -x['confidence']))
        result = []
        
        for span in spans:
            # Check if this span overlaps with any in result
            overlaps = False
            for existing in result:
                if (span['start'] < existing['end'] and 
                    span['end'] > existing['start']):
                    overlaps = True
                    break
            
            if not overlaps:
                result.append(span)
        
        return result

class TextRedactor:
    """Handles text redaction with different modes"""
    
    def __init__(self, tenant_salt: str = "default"):
        self.tenant_salt = tenant_salt
    
    def redact_text(self, text: str, pii_spans: List[Dict], 
                   mode: str = 'mask') -> Tuple[str, List[Dict]]:
        """
        Apply redaction to text based on PII spans
        
        Args:
            text: Original text
            pii_spans: List of PII span dicts from detect_pii
            mode: 'mask', 'hash', or 'remove'
        
        Returns:
            Tuple of (redacted_text, applied_redactions)
        """
        if not pii_spans:
            return text, []
        
        # Sort spans by start position (reverse order for removal)
        spans_sorted = sorted(pii_spans, key=lambda x: x['start'], reverse=True)
        redacted_text = text
        applied_redactions = []
        
        for span in spans_sorted:
            start, end = span['start'], span['end']
            original_text = span['text']
            
            if mode == 'mask':
                replacement = self._mask_text(original_text, span['type'])
            elif mode == 'hash':
                replacement = self._hash_text(original_text, span['type'])
            elif mode == 'remove':
                replacement = ""
            else:
                raise ValueError(f"Unknown redaction mode: {mode}")
            
            # Apply redaction
            redacted_text = redacted_text[:start] + replacement + redacted_text[end:]
            
            applied_redactions.append({
                'original_start': start,
                'original_end': end,
                'original_text': original_text,
                'replacement': replacement,
                'type': span['type'],
                'mode': mode,
                'confidence': span['confidence']
            })
        
        return redacted_text, applied_redactions
    
    def _mask_text(self, text: str, pii_type: str) -> str:
        """Create masked replacement for PII"""
        type_labels = {
            'ssn': '[SSN]',
            'phone': '[PHONE]',
            'email': '[EMAIL]',
            'credit_card': '[CARD]',
            'person': '[NAME]',
            'org': '[ORG]',
            'date_of_birth': '[DOB]',
            'zip_code': '[ZIP]'
        }
        
        return type_labels.get(pii_type, '[PII]')
    
    def _hash_text(self, text: str, pii_type: str) -> str:
        """Create deterministic hash replacement for PII"""
        # Use tenant salt for deterministic but secure hashing
        salted_text = f"{self.tenant_salt}:{text}:{pii_type}"
        hash_digest = hashlib.sha256(salted_text.encode()).hexdigest()[:8]
        
        type_prefixes = {
            'ssn': 'SSN',
            'phone': 'PH',
            'email': 'EM',
            'credit_card': 'CC',
            'person': 'NM',
            'org': 'OR',
            'date_of_birth': 'DOB',
            'zip_code': 'ZIP'
        }
        
        prefix = type_prefixes.get(pii_type, 'PII')
        return f"[{prefix}:{hash_digest}]"

# Service functions for dependency injection
detector = PIIDetector()

def detect_pii(text: str) -> List[Dict[str, Any]]:
    """Module-level function to detect PII"""
    return detector.detect_pii(text)

def redact_text(text: str, pii_spans: List[Dict], mode: str = 'mask', 
               tenant_salt: str = 'default') -> Tuple[str, List[Dict]]:
    """Module-level function to redact text"""
    redactor = TextRedactor(tenant_salt)
    return redactor.redact_text(text, pii_spans, mode)