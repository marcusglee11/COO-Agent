"""
Cryptographic utilities for COO Runtime.
Implements Ed25519 signing and verification per R6.3 Unified Signature Protocol.
"""
import os
import hashlib
from datetime import datetime
from typing import Dict, Any
from nacl.signing import VerifyKey, SigningKey
from nacl.exceptions import BadSignatureError

class CryptoError(Exception):
    """Cryptographic operation errors."""
    pass

# ============================================================================
# D1: Canonical Key Resolution (No Fallbacks) - R6.3
# ============================================================================

def get_ceo_private_key_path() -> str:
    """
    Get CEO private key path from environment variable.
    Raises CryptoError if not set or file doesn't exist.
    
    R6.3 D1: Keys MUST ONLY be specified via environment variables.
    No repository paths. No fallback search order. Fail-closed.
    """
    path = os.environ.get('CEO_PRIVATE_KEY_PATH')
    if not path:
        raise CryptoError(
            "CEO_PRIVATE_KEY_PATH environment variable not set. "
            "Cannot perform signing operations."
        )
    if not os.path.exists(path):
        raise CryptoError(
            f"CEO private key not found at {path}"
        )
    return path

def get_ceo_public_key_path() -> str:
    """
    Get CEO public key path from environment variable.
    Raises CryptoError if not set or file doesn't exist.
    
    R6.3 D1: Keys MUST ONLY be specified via environment variables.
    No repository paths. No fallback search order. Fail-closed.
    """
    path = os.environ.get('CEO_PUBLIC_KEY_PATH')
    if not path:
        raise CryptoError(
            "CEO_PUBLIC_KEY_PATH environment variable not set. "
            "Cannot perform verification operations."
        )
    if not os.path.exists(path):
        raise CryptoError(
            f"CEO public key not found at {path}"
        )
    return path

# ============================================================================
# D2: Unified Signature Protocol - R6.3
# ============================================================================

class Signature:
    """
    Unified signature protocol for all COO Runtime signing operations.
    
    R6.3 D2: ALL signing and verification (AMU₀, rollback, checkpoints, gates)
    MUST use this unified protocol.
    """
    
    @staticmethod
    def sign_data(data: bytes, private_key_path: str) -> bytes:
        """
        Sign arbitrary bytes. Returns raw signature bytes.
        
        Args:
            data: Bytes to sign
            private_key_path: Path to Ed25519 private key
            
        Returns:
            Raw signature bytes
            
        Raises:
            CryptoError: If signing fails
        """
        try:
            with open(private_key_path, 'rb') as f:
                sk = SigningKey(f.read())
            return sk.sign(data).signature
        except Exception as e:
            raise CryptoError(f"Signing failed: {e}") from e
    
    @staticmethod
    def verify_data(data: bytes, signature: bytes, public_key_path: str) -> bool:
        """
        Verify signature over bytes.
        
        Args:
            data: Original data that was signed
            signature: Signature bytes to verify
            public_key_path: Path to Ed25519 public key
            
        Returns:
            True on successful verification, False on failure
        """
        try:
            with open(public_key_path, 'rb') as f:
                vk = VerifyKey(f.read())
            vk.verify(data, signature)
            return True
        except (BadSignatureError, Exception):
            return False
    
    @staticmethod
    def sign_file(filepath: str, private_key_path: str) -> bytes:
        """
        Read file contents and sign them.
        
        Args:
            filepath: Path to file to sign
            private_key_path: Path to Ed25519 private key
            
        Returns:
            Signature bytes
            
        Note:
            Caller is responsible for writing signature to <filepath>.sig if desired.
        """
        with open(filepath, 'rb') as f:
            data = f.read()
        return Signature.sign_data(data, private_key_path)
    
    @staticmethod
    def verify_file(filepath: str, signature: bytes, public_key_path: str) -> bool:
        """
        Read file contents and verify signature bytes.
        
        Args:
            filepath: Path to file that was signed
            signature: Signature bytes to verify
            public_key_path: Path to Ed25519 public key
            
        Returns:
            True on successful verification, False on failure
        """
        with open(filepath, 'rb') as f:
            data = f.read()
        return Signature.verify_data(data, signature, public_key_path)

# ============================================================================
# Dev/Prod Mode Support (Supplemental R6.3 Guidance)
# ============================================================================

def create_signature_metadata(mode: str = None) -> Dict[str, Any]:
    """
    Create signature metadata with mode information.
    
    Supplemental R6.3: All signatures must include mode information to
    mechanically fence development from production.
    
    Args:
        mode: "dev" or "prod" (defaults to COO_MODE env var or "dev")
        
    Returns:
        Dict with mode, timestamp, key_id
    """
    if mode is None:
        mode = os.environ.get("COO_MODE", "dev")
    
    try:
        public_key_path = get_ceo_public_key_path()
        with open(public_key_path, 'rb') as f:
            key_bytes = f.read()
        key_id = hashlib.sha256(key_bytes).hexdigest()[:8]
    except CryptoError:
        key_id = "UNKNOWN"
    
    return {
        "mode": mode,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "key_id": key_id
    }

# ============================================================================
# Legacy Functions (Deprecated - Use Signature class instead)
# ============================================================================

def sign_bytes(private_key_path: str = None, data: bytes = None) -> bytes:
    """
    DEPRECATED: Use Signature.sign_data() instead.
    Legacy function for backward compatibility during migration.
    """
    if not private_key_path:
        private_key_path = get_ceo_private_key_path()
    return Signature.sign_data(data, private_key_path)

def verify_signature(public_key_path: str = None, data: bytes = None, signature: bytes = None) -> bool:
    """
    DEPRECATED: Use Signature.verify_data() instead.
    Legacy function for backward compatibility during migration.
    """
    if not public_key_path:
        public_key_path = get_ceo_public_key_path()
    return Signature.verify_data(data, signature, public_key_path)
