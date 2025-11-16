"""
Basic tests for encryption system.
Run with: python test_encryption.py
"""

import os
import base64
from encryption import encrypt_text, decrypt_text, is_encrypted_payload, EncryptionError, DecryptionError


def test_basic_encryption_decryption():
    """Test that encrypt/decrypt roundtrip works."""
    plaintext = "Hello, SecureBank! This is a test message."
    
    # Encrypt
    payload = encrypt_text(plaintext)
    
    # Verify payload structure
    assert is_encrypted_payload(payload), "Payload should be recognized as encrypted"
    assert "ciphertext" in payload
    assert "nonce" in payload
    assert "key_id" in payload
    
    # Decrypt
    decrypted = decrypt_text(payload)
    
    assert decrypted == plaintext, f"Decryption failed: expected '{plaintext}', got '{decrypted}'"
    print("✅ Test 1 passed: Basic encryption/decryption")


def test_encryption_with_aad():
    """Test encryption with associated authenticated data."""
    plaintext = "Account balance: £1,234.56"
    aad = {"user_id": "test_user", "request_id": "req_123"}
    
    # Encrypt with AAD
    payload = encrypt_text(plaintext, associated_data=aad)
    
    assert payload["aad"] == aad, "AAD should be stored in payload"
    
    # Decrypt
    decrypted = decrypt_text(payload)
    
    assert decrypted == plaintext, "Decryption with AAD failed"
    print("✅ Test 2 passed: Encryption with associated data")


def test_tampered_ciphertext_fails():
    """Test that tampering with ciphertext causes decryption to fail."""
    plaintext = "Sensitive customer data"
    
    # Encrypt
    payload = encrypt_text(plaintext)
    
    # Tamper with ciphertext (flip a bit)
    ciphertext_bytes = base64.b64decode(payload["ciphertext"])
    tampered_bytes = bytearray(ciphertext_bytes)
    tampered_bytes[0] ^= 1  # Flip first bit
    payload["ciphertext"] = base64.b64encode(bytes(tampered_bytes)).decode('ascii')
    
    # Try to decrypt - should fail
    try:
        decrypt_text(payload)
        assert False, "Decryption should have failed with tampered ciphertext"
    except DecryptionError:
        print("✅ Test 3 passed: Tampered ciphertext detected")


def test_wrong_nonce_fails():
    """Test that changing the nonce causes decryption to fail."""
    plaintext = "Secret message"
    
    # Encrypt
    payload = encrypt_text(plaintext)
    
    # Replace nonce with a different one
    payload["nonce"] = base64.b64encode(os.urandom(12)).decode('ascii')
    
    # Try to decrypt - should fail
    try:
        decrypt_text(payload)
        assert False, "Decryption should have failed with wrong nonce"
    except DecryptionError:
        print("✅ Test 4 passed: Wrong nonce detected")


def test_unicode_text():
    """Test that Unicode text is handled correctly."""
    plaintext = "Hello! 你好! مرحبا! 🔒🛡️"
    
    # Encrypt
    payload = encrypt_text(plaintext)
    
    # Decrypt
    decrypted = decrypt_text(payload)
    
    assert decrypted == plaintext, "Unicode text not preserved"
    print("✅ Test 5 passed: Unicode text handling")


def run_all_tests():
    """Run all encryption tests."""
    print("Running encryption tests...\n")
    
    try:
        test_basic_encryption_decryption()
        test_encryption_with_aad()
        test_tampered_ciphertext_fails()
        test_wrong_nonce_fails()
        test_unicode_text()
        
        print("\n✅ All tests passed!")
        return True
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    run_all_tests()
