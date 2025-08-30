# app/services/crypto_sign.py
import base64
import json
import hashlib
from typing import Union, Dict, Any
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.exceptions import InvalidSignature

from app.core.logging import get_logger

logger = get_logger(__name__)

class CryptoSignService:
    """Handles signing and verification of audit events and payloads"""
    
    def __init__(self, private_key_pem: str, public_key_pem: str):
        self.private_key = self._load_private_key(private_key_pem)
        self.public_key = self._load_public_key(public_key_pem)
    
    def _load_private_key(self, key_pem: str):
        """Load RSA private key from PEM string or file path"""
        try:
            # Try as file path first
            if key_pem.startswith('/') or key_pem.endswith('.pem'):
                with open(key_pem, 'rb') as f:
                    key_data = f.read()
            else:
                key_data = key_pem.encode('utf-8')
            
            return serialization.load_pem_private_key(
                key_data,
                password=None
            )
        except Exception as e:
            logger.error(f"Failed to load private key: {e}")
            raise ValueError(f"Invalid private key: {e}")
    
    def _load_public_key(self, key_pem: str):
        """Load RSA public key from PEM string or file path"""
        try:
            if key_pem.startswith('/') or key_pem.endswith('.pem'):
                with open(key_pem, 'rb') as f:
                    key_data = f.read()
            else:
                key_data = key_pem.encode('utf-8')
            
            return serialization.load_pem_public_key(key_data)
        except Exception as e:
            logger.error(f"Failed to load public key: {e}")
            raise ValueError(f"Invalid public key: {e}")
    
    def sign_payload(self, payload: Union[bytes, str, Dict[str, Any]]) -> str:
        """Sign a payload and return base64 encoded signature"""
        try:
            # Normalize payload to bytes
            if isinstance(payload, dict):
                payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
            elif isinstance(payload, str):
                payload_bytes = payload.encode('utf-8')
            else:
                payload_bytes = payload
            
            # Sign using RSA-PSS
            signature = self.private_key.sign(
                payload_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return base64.b64encode(signature).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to sign payload: {e}")
            raise ValueError(f"Signing failed: {e}")
    
    def verify_signature(self, payload: Union[bytes, str, Dict[str, Any]], 
                        signature_b64: str) -> bool:
        """Verify a signature against a payload"""
        try:
            # Normalize payload to bytes (same as signing)
            if isinstance(payload, dict):
                payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
            elif isinstance(payload, str):
                payload_bytes = payload.encode('utf-8')
            else:
                payload_bytes = payload
            
            # Decode signature
            signature = base64.b64decode(signature_b64.encode('utf-8'))
            
            # Verify using RSA-PSS
            self.public_key.verify(
                signature,
                payload_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True
            
        except InvalidSignature:
            logger.warning("Invalid signature detected")
            return False
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False
    
    def hash_payload(self, payload: Union[bytes, str, Dict[str, Any]]) -> str:
        """Generate SHA256 hash of payload for integrity checking"""
        if isinstance(payload, dict):
            payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        elif isinstance(payload, str):
            payload_bytes = payload.encode('utf-8')
        else:
            payload_bytes = payload
        
        return hashlib.sha256(payload_bytes).hexdigest()

# Utility functions for module-level access
def sign_payload(payload: Union[bytes, str, Dict[str, Any]], private_key_pem: str) -> str:
    """Module-level function to sign a payload"""
    service = CryptoSignService(private_key_pem, "")  # Only need private key
    return service.sign_payload(payload)

def verify_signature(payload: Union[bytes, str, Dict[str, Any]], 
                    signature_b64: str, public_key_pem: str) -> bool:
    """Module-level function to verify a signature"""
    service = CryptoSignService("", public_key_pem)  # Only need public key
    return service.verify_signature(payload, signature_b64)