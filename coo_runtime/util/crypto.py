"""
Cryptographic utilities for COO Runtime.
Implements Ed25519 signing and verification for AMU0 bundles.
"""
import os
from nacl.signing import VerifyKey, SigningKey

class CryptoError(Exception):
    pass

def get_key_path(env_var: str) -> str:
    """
    Strictly resolve key path from environment variable.
    Fails if missing.
    """
    path = os.environ.get(env_var)
    if not path:
        raise CryptoError(f"Cryptographic Key Error: Environment variable {env_var} not set.")
    if not os.path.exists(path):
        raise CryptoError(f"Cryptographic Key Error: Key file not found at {path}")
    return path

def sign_bytes(private_key_path: str = None, data: bytes = None) -> bytes:
    """
    Sign data using Ed25519 private key.
    If path not provided, loads from CEO_PRIVATE_KEY_PATH.
    """
    if not private_key_path:
        private_key_path = get_key_path("CEO_PRIVATE_KEY_PATH")
        
    try:
        sk = SigningKey(open(private_key_path, "rb").read())
        return sk.sign(data).signature
    except Exception as e:
        raise CryptoError(f"Signing Failed: {e}")

def verify_signature(public_key_path: str = None, data: bytes = None, signature: bytes = None) -> bool:
    """
    Verify Ed25519 signature.
    If path not provided, loads from CEO_PUBLIC_KEY_PATH.
    """
    if not public_key_path:
        public_key_path = get_key_path("CEO_PUBLIC_KEY_PATH")
        
    try:
        vk = VerifyKey(open(public_key_path, "rb").read())
        vk.verify(data, signature)
        return True
    except Exception:
        return False
