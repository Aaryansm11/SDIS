"""
Unit tests for redaction.
"""
def test_detect_and_redact_email():
    from app.services.redaction import detect_pii, redact_text
    text = "Contact me at test@example.com for details."
    spans = detect_pii(text)
    assert len(spans) >= 1
    redacted, applied = redact_text(text, spans, mode="mask")
    assert "[REDACTED_EMAIL]" in redacted
