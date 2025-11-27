"""
Cryptographic utilities for COO Runtime.
Implements Ed25519 signing and verification for AMU0 bundles.
"""
from nacl.signing import VerifyKey, SigningKey

def sign_bytes(private_key_path: str, data: bytes) -> bytes:
    """
    Sign data using Ed25519 private key.
    
    Args:
        private_key_path: Path to private key file (32 bytes)
        data: Data to sign
        
    Returns:
        64-byte signature
    """
    sk = SigningKey(open(private_key_path, "rb").read())
    return sk.sign(data).signature

def verify_signature(public_key_path: str, data: bytes, signature: bytes) -> bool:
    """
    Verify Ed25519 signature.
    
    Args:
        public_key_path: Path to public key file (32 bytes)
        data: Data that was signed
        signature: 64-byte signature to verify
        
    Returns:
        True if valid, False otherwise
    """
    vk = VerifyKey(open(public_key_path, "rb").read())
    try:
        vk.verify(data, signature)
        return True
    except Exception:
        return False
