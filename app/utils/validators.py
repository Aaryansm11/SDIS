# app/utils/validators.py
import re
from typing import Optional
from uuid import UUID

def validate_tenant_id(tenant_id: str) -> bool:
    """Validate tenant ID format and basic rules"""
    if not tenant_id:
        return False
    
    # Check if it's a valid UUID
    try:
        UUID(tenant_id)
        return True
    except ValueError:
        pass
    
    # Or validate as alphanumeric string (3-50 chars)
    pattern = re.compile(r'^[a-zA-Z0-9_-]{3,50}$')
    return bool(pattern.match(tenant_id))

def validate_file_size(file_bytes: bytes, max_mb: int = 50) -> bool:
    """Validate file size is within limits"""
    if not file_bytes:
        return False
    
    max_bytes = max_mb * 1024 * 1024
    return len(file_bytes) <= max_bytes

def validate_mime_type(mime_type: str) -> bool:
    """Validate that mime type is supported"""
    supported_types = {
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword',
        'text/plain',
        'text/markdown'
    }
    
    return mime_type.lower() in supported_types

def validate_email(email: str) -> bool:
    """Validate email format"""
    if not email:
        return False
    
    pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    return bool(pattern.match(email)) and len(email) <= 255

def validate_password_strength(password: str) -> tuple[bool, List[str]]:
    """Validate password strength and return issues"""
    issues = []
    
    if len(password) < 8:
        issues.append("Password must be at least 8 characters")
    
    if not re.search(r'[A-Z]', password):
        issues.append("Password must contain uppercase letter")
    
    if not re.search(r'[a-z]', password):
        issues.append("Password must contain lowercase letter")
    
    if not re.search(r'\d', password):
        issues.append("Password must contain number")
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        issues.append("Password must contain special character")
    
    return len(issues) == 0, issues

def validate_query(query: str, max_length: int = 1000) -> tuple[bool, Optional[str]]:
    """Validate search query"""
    if not query or not query.strip():
        return False, "Query cannot be empty"
    
    if len(query) > max_length:
        return False, f"Query too long (max {max_length} characters)"
    
    # Check for potential injection attempts
    suspicious_patterns = [
        r'<script',
        r'javascript:',
        r'data:',
        r'vbscript:',
        r'onload=',
        r'onerror='
    ]
    
    query_lower = query.lower()
    for pattern in suspicious_patterns:
        if re.search(pattern, query_lower):
            return False, "Query contains potentially malicious content"
    
    return True, None

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    if not filename:
        return "unnamed_file"
    
    # Remove path separators and dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove control characters
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_len = 250 - len(ext)
        filename = name[:max_name_len] + ('.' + ext if ext else '')
    
    # Ensure not empty after sanitization
    if not filename.strip():
        return "sanitized_file"
    
    return filename.strip()

def validate_uuid(uuid_str: str) -> bool:
    """Validate UUID string format"""
    try:
        UUID(uuid_str)
        return True
    except (ValueError, TypeError):
        return False

def validate_json_size(data: dict, max_kb: int = 100) -> bool:
    """Validate JSON data size"""
    import json
    try:
        json_str = json.dumps(data)
        size_kb = len(json_str.encode('utf-8')) / 1024
        return size_kb <= max_kb
    except Exception:
        return False