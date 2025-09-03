# File: tests/unit/test_redaction.py
# Unit tests for detect_pii and redact_text.

import pytest
from app.services.redaction import detect_pii, redact_text

class TestPIIDetection:
    
    def test_detect_email_addresses(self):
        """Test detection of email addresses."""
        text = "Contact John at john.doe@example.com for more information."
        pii_spans = detect_pii(text)
        
        email_spans = [span for span in pii_spans if span["type"] == "EMAIL"]
        assert len(email_spans) == 1
        assert "john.doe@example.com" in email_spans[0]["text"]
    
    def test_detect_phone_numbers(self):
        """Test detection of phone numbers in various formats."""
        texts = [
            "Call me at (555) 123-4567",
            "Phone: 555-123-4567",
            "Contact: +1-555-123-4567"
        ]
        
        for text in texts:
            pii_spans = detect_pii(text)
            phone_spans = [span for span in pii_spans if span["type"] == "PHONE"]
            assert len(phone_spans) >= 1, f"Failed to detect phone in: {text}"
    
    def test_detect_ssn(self):
        """Test detection of Social Security Numbers."""
        text = "SSN: 123-45-6789 is confidential information."
        pii_spans = detect_pii(text)
        
        ssn_spans = [span for span in pii_spans if span["type"] == "SSN"]
        assert len(ssn_spans) == 1
        assert "123-45-6789" in ssn_spans[0]["text"]
    
    def test_detect_credit_card(self):
        """Test detection of credit card numbers."""
        text = "Credit card number 4532-1234-5678-9012 should be protected."
        pii_spans = detect_pii(text)
        
        cc_spans = [span for span in pii_spans if span["type"] == "CREDIT_CARD"]
        assert len(cc_spans) == 1
    
    def test_detect_names_with_spacy(self):
        """Test person name detection using spaCy."""
        text = "John Smith and Mary Johnson attended the meeting."
        pii_spans = detect_pii(text)
        
        person_spans = [span for span in pii_spans if span["type"] == "PERSON"]
        assert len(person_spans) >= 1  # Should detect at least one name
    
    def test_no_false_positives(self):
        """Test that normal text doesn't trigger PII detection."""
        text = "This is a normal business document with no sensitive information."
        pii_spans = detect_pii(text)
        
        # Should not detect any PII in normal text
        assert len(pii_spans) == 0
    
    def test_multiple_pii_types(self):
        """Test detection of multiple PII types in one text."""
        text = "John Doe (john.doe@example.com) phone: (555) 123-4567, SSN: 123-45-6789"
        pii_spans = detect_pii(text)
        
        # Should detect multiple types
        types_found = {span["type"] for span in pii_spans}
        expected_types = {"EMAIL", "PHONE", "SSN"}
        assert len(types_found & expected_types) >= 2  # At least 2 types detected

class TestPIIRedaction:
    
    def test_redact_mask_mode(self):
        """Test redaction using mask mode."""
        text = "Contact john.doe@example.com for details."
        pii_spans = detect_pii(text)
        
        redacted_text, applied_spans = redact_text(text, pii_spans, mode="mask")
        
        assert "john.doe@example.com" not in redacted_text
        assert "[EMAIL]" in redacted_text or "*" in redacted_text
    
    def test_redact_remove_mode(self):
        """Test redaction using remove mode."""
        text = "Call me at (555) 123-4567 tomorrow."
        pii_spans = detect_pii(text)
        
        redacted_text, applied_spans = redact_text(text, pii_spans, mode="remove")
        
        assert "(555) 123-4567" not in redacted_text
        assert len(redacted_text) < len(text)
    
    def test_redact_hash_mode_deterministic(self):
        """Test that hash mode produces deterministic results."""
        text = "Email: test@example.com"
        pii_spans = detect_pii(text)
        
        # Apply redaction twice with same tenant salt
        redacted1, _ = redact_text(text, pii_spans, mode="hash")
        redacted2, _ = redact_text(text, pii_spans, mode="hash")
        
        assert redacted1 == redacted2  # Should be deterministic
        assert "test@example.com" not in redacted1
    
    def test_redact_preserves_structure(self):
        """Test that redaction preserves document structure."""
        text = "Document title.\n\nContact: john@example.com\n\nNext paragraph."
        pii_spans = detect_pii(text)
        
        redacted_text, _ = redact_text(text, pii_spans, mode="mask")
        
        # Should preserve document structure
        assert "Document title" in redacted_text
        assert "Next paragraph" in redacted_text
        assert redacted_text.count("\n") == text.count("\n")
    
    def test_redact_no_pii(self):
        """Test redaction when no PII is detected."""
        text = "This is a clean document with no sensitive information."
        pii_spans = detect_pii(text)
        
        redacted_text, applied_spans = redact_text(text, pii_spans, mode="mask")
        
        assert redacted_text == text  # Should be unchanged
        assert len(applied_spans) == 0
    
    def test_redact_overlapping_spans(self):
        """Test handling of overlapping PII spans."""
        text = "Dr. John Smith's email john.smith@hospital.com"
        pii_spans = detect_pii(text)
        
        # Might detect both PERSON and EMAIL with overlap
        redacted_text, applied_spans = redact_text(text, pii_spans, mode="mask")
        
        # Should handle overlaps gracefully
        assert "john.smith@hospital.com" not in redacted_text
        assert len(redacted_text) > 0
    
    def test_applied_spans_tracking(self):
        """Test that applied spans are correctly tracked."""
        text = "Contact info: john@test.com and (555) 123-4567"
        pii_spans = detect_pii(text)
        
        redacted_text, applied_spans = redact_text(text, pii_spans, mode="mask")
        
        # Should track what was redacted
        assert len(applied_spans) == len(pii_spans)
        for span in applied_spans:
            assert "original_text" in span
            assert "redacted_text" in span
            assert "type" in span