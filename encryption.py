"""
Encryption module for SecureBank Support Agent.

Provides AES-256-GCM authenticated encryption for LLM messages to ensure
raw text is never stored or transmitted in plaintext outside controlled points.

Key Features:
- AES-256-GCM (AEAD) for confidentiality + integrity
- Per-message random nonces (96-bit)
- Support for associated authenticated data (AAD)
- Key rotation ready (key_id support)
"""

import os
import base64
import json
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag


class EncryptionError(Exception):
    """Base exception for encryption operations."""
    pass


class DecryptionError(Exception):
    """Exception raised when decryption fails (wrong key, tampered data, etc)."""
    pass


class KeyManager:
    """Manages encryption keys with support for key rotation."""
    
    def __init__(self):
        self.keys: Dict[str, bytes] = {}
        self.current_key_id = "main-2025-01"
        self._load_keys()
    
    def _load_keys(self):
        """Load encryption keys from environment variables."""
        key_b64 = os.getenv("SECUREBANK_ENC_KEY")
        
        if not key_b64:
            raise EncryptionError(
                "SECUREBANK_ENC_KEY environment variable not set. "
                "Generate a key with: python -c 'import os, base64; print(base64.b64encode(os.urandom(32)).decode())'"
            )
        
        try:
            key_bytes = base64.b64decode(key_b64)
        except Exception as e:
            raise EncryptionError(f"Invalid base64 in SECUREBANK_ENC_KEY: {e}")
        
        if len(key_bytes) != 32:
            raise EncryptionError(
                f"SECUREBANK_ENC_KEY must be 32 bytes (256 bits), got {len(key_bytes)} bytes. "
                "Generate a new key with: python -c 'import os, base64; print(base64.b64encode(os.urandom(32)).decode())'"
            )
        
        self.keys[self.current_key_id] = key_bytes
    
    def get_current_key_id(self) -> str:
        """Get the current key ID for encryption."""
        return self.current_key_id
    
    def get_key(self, key_id: str) -> bytes:
        """Get a key by ID (supports key rotation)."""
        if key_id not in self.keys:
            raise EncryptionError(f"Unknown key_id: {key_id}")
        return self.keys[key_id]


# Global key manager instance
_key_manager: Optional[KeyManager] = None


def _get_key_manager() -> KeyManager:
    """Get or initialize the global key manager."""
    global _key_manager
    if _key_manager is None:
        _key_manager = KeyManager()
    return _key_manager


def encrypt_text(
    plaintext: str,
    associated_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Encrypt plaintext using AES-256-GCM.
    
    Args:
        plaintext: UTF-8 string to encrypt
        associated_data: Optional dict of authenticated metadata (e.g., user_id, request_id)
    
    Returns:
        Dict containing:
        - ciphertext: base64-encoded encrypted data
        - nonce: base64-encoded 96-bit nonce
        - key_id: identifier for the encryption key (supports rotation)
        - aad: associated authenticated data (if provided)
    
    Raises:
        EncryptionError: If encryption fails
    """
    try:
        km = _get_key_manager()
        key_id = km.get_current_key_id()
        key = km.get_key(key_id)
        
        # Create AESGCM cipher
        aesgcm = AESGCM(key)
        
        # Generate random 96-bit nonce
        nonce = os.urandom(12)  # 96 bits = 12 bytes
        
        # Encode plaintext
        plaintext_bytes = plaintext.encode('utf-8')
        
        # Prepare AAD (associated authenticated data)
        aad_bytes = None
        if associated_data:
            aad_bytes = json.dumps(associated_data, sort_keys=True).encode('utf-8')
        
        # Encrypt
        ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, aad_bytes)
        
        # Return payload
        payload = {
            "ciphertext": base64.b64encode(ciphertext).decode('ascii'),
            "nonce": base64.b64encode(nonce).decode('ascii'),
            "key_id": key_id
        }
        
        if associated_data:
            payload["aad"] = associated_data
        
        return payload
    
    except Exception as e:
        if isinstance(e, EncryptionError):
            raise
        raise EncryptionError(f"Encryption failed: {e}")


def decrypt_text(payload: Dict[str, Any]) -> str:
    """
    Decrypt a payload created by encrypt_text.
    
    Args:
        payload: Dict containing ciphertext, nonce, key_id, and optional aad
    
    Returns:
        Decrypted plaintext string
    
    Raises:
        DecryptionError: If decryption fails or integrity check fails
    """
    try:
        # Extract payload components
        ciphertext_b64 = payload.get("ciphertext")
        nonce_b64 = payload.get("nonce")
        key_id = payload.get("key_id")
        associated_data = payload.get("aad")
        
        if not all([ciphertext_b64, nonce_b64, key_id]):
            raise DecryptionError("Invalid payload: missing required fields (ciphertext, nonce, key_id)")
        
        # Decode from base64
        ciphertext = base64.b64decode(ciphertext_b64)
        nonce = base64.b64decode(nonce_b64)
        
        # Get key
        km = _get_key_manager()
        key = km.get_key(key_id)
        
        # Create AESGCM cipher
        aesgcm = AESGCM(key)
        
        # Prepare AAD
        aad_bytes = None
        if associated_data:
            aad_bytes = json.dumps(associated_data, sort_keys=True).encode('utf-8')
        
        # Decrypt and verify integrity
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, aad_bytes)
        
        return plaintext_bytes.decode('utf-8')
    
    except InvalidTag:
        raise DecryptionError("Decryption failed: authentication tag verification failed (data may be tampered)")
    except Exception as e:
        if isinstance(e, (EncryptionError, DecryptionError)):
            raise
        raise DecryptionError(f"Decryption failed: {e}")


def is_encrypted_payload(data: Any) -> bool:
    """
    Check if data is an encrypted payload.
    
    Args:
        data: Any data to check
    
    Returns:
        True if data is a dict with encryption payload fields
    """
    if not isinstance(data, dict):
        return False
    return all(key in data for key in ["ciphertext", "nonce", "key_id"])


def get_payload_preview(payload: Dict[str, Any], max_length: int = 50) -> str:
    """
    Get a safe preview of an encrypted payload for logging.
    
    Args:
        payload: Encrypted payload
        max_length: Maximum length of preview
    
    Returns:
        Safe preview string showing key_id and truncated ciphertext
    """
    key_id = payload.get("key_id", "unknown")
    ciphertext = payload.get("ciphertext", "")
    preview = ciphertext[:max_length] + "..." if len(ciphertext) > max_length else ciphertext
    return f"[ENCRYPTED key_id={key_id} ciphertext={preview}]"
