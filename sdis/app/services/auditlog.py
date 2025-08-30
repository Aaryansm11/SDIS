# app/services/auditlog.py
import json
import hashlib
import os
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from app.core.config import get_settings
from app.services.crypto_sign import CryptoSignService
from app.core.logging import get_logger

logger = get_logger(__name__)

class AuditLogService:
    """Append-only audit log with cryptographic signatures"""
    
    def __init__(self):
        self.settings = get_settings()
        self.crypto_service = CryptoSignService(
            self.settings.signing_private_key,
            self.settings.signing_public_key
        )
        self.log_path = self.settings.audit_log_path
        
        # Ensure audit log directory exists
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
    
    def write_audit_event(self, 
                         action: str,
                         tenant_id: str,
                         user_id: Optional[str] = None,
                         resource: Optional[str] = None,
                         resource_type: Optional[str] = None,
                         request_data: Optional[Dict] = None,
                         response_data: Optional[Dict] = None,
                         ip_address: Optional[str] = None,
                         user_agent: Optional[str] = None) -> str:
        """
        Write an audit event to the log with cryptographic signature
        
        Returns:
            audit_id: Unique identifier for this audit event
        """
        timestamp = datetime.utcnow()
        
        # Create base event
        event = {
            'timestamp': timestamp.isoformat() + 'Z',
            'action': action,
            'tenant_id': tenant_id,
            'user_id': user_id,
            'resource': resource,
            'resource_type': resource_type,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'request_data': request_data or {},
            'response_data': response_data or {}
        }
        
        # Generate audit ID from event content
        event_content = json.dumps(event, sort_keys=True)
        audit_id = hashlib.sha256(event_content.encode()).hexdigest()
        event['audit_id'] = audit_id
        
        # Generate result hash if response data present
        if response_data:
            result_hash = self.crypto_service.hash_payload(response_data)
            event['result_hash'] = result_hash
        
        # Sign the complete event
        try:
            signature = self.crypto_service.sign_payload(event)
            event['signature'] = signature
            event['signature_algorithm'] = 'RS256'
            
            # Write to audit log file (append-only)
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
            
            logger.info("Audit event written", extra={
                'audit_id': audit_id,
                'action': action,
                'tenant_id': tenant_id,
                'user_id': user_id
            })
            
            return audit_id
            
        except Exception as e:
            logger.error(f"Failed to write audit event: {e}")
            raise RuntimeError(f"Audit logging failed: {e}")
    
    def read_audit_event(self, audit_id: str) -> Optional[Dict[str, Any]]:
        """
        Read and verify an audit event by ID
        
        Returns:
            Event dict with signature_valid field, or None if not found
        """
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    try:
                        event = json.loads(line.strip())
                        if event.get('audit_id') == audit_id:
                            # Verify signature
                            signature = event.pop('signature', '')
                            signature_algorithm = event.pop('signature_algorithm', '')
                            
                            signature_valid = False
                            if signature and signature_algorithm == 'RS256':
                                signature_valid = self.crypto_service.verify_signature(
                                    event, signature
                                )
                            
                            # Add signature info back
                            event['signature'] = signature
                            event['signature_algorithm'] = signature_algorithm
                            event['signature_valid'] = signature_valid
                            
                            return event
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in audit log: {line[:100]}")
                        continue
            
            return None
            
        except FileNotFoundError:
            logger.warning(f"Audit log file not found: {self.log_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to read audit event {audit_id}: {e}")
            return None
    
    def verify_audit_integrity(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Verify integrity of audit log entries
        
        Returns:
            Dict with verification statistics
        """
        stats = {
            'total_events': 0,
            'valid_signatures': 0,
            'invalid_signatures': 0,
            'malformed_events': 0,
            'missing_signatures': 0
        }
        
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if limit and i >= limit:
                        break
                    
                    if not line.strip():
                        continue
                    
                    stats['total_events'] += 1
                    
                    try:
                        event = json.loads(line.strip())
                        signature = event.get('signature')
                        
                        if not signature:
                            stats['missing_signatures'] += 1
                            continue
                        
                        # Create event copy without signature for verification
                        event_copy = {k: v for k, v in event.items() 
                                    if k not in ['signature', 'signature_algorithm']}
                        
                        if self.crypto_service.verify_signature(event_copy, signature):
                            stats['valid_signatures'] += 1
                        else:
                            stats['invalid_signatures'] += 1
                            
                    except json.JSONDecodeError:
                        stats['malformed_events'] += 1
                        
        except FileNotFoundError:
            logger.warning("Audit log file not found for integrity check")
        
        return stats

# Module-level service instance
_audit_service: Optional[AuditLogService] = None

def get_audit_service() -> AuditLogService:
    """Get singleton audit service instance"""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditLogService()
    return _audit_service

def write_audit_event(action: str, tenant_id: str, **kwargs) -> str:
    """Module-level function to write audit event"""
    service = get_audit_service()
    return service.write_audit_event(action, tenant_id, **kwargs)

def read_audit_event(audit_id: str) -> Optional[Dict[str, Any]]:
    """Module-level function to read audit event"""
    service = get_audit_service()
    return service.read_audit_event(audit_id)