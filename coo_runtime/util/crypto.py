"""
Cryptographic utilities for COO Runtime.
Implements Ed25519 signing and verification per R6.3 Unified Signature Protocol.
R6.5 G2: Enforces memory-resident keys and rejects key paths in API.
"""
import os
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from nacl.signing import VerifyKey, SigningKey
from nacl.exceptions import BadSignatureError

class CryptoError(Exception):
    """Cryptographic operation errors."""
    pass

# ============================================================================
# G2: Memory-Resident Key Management - R6.5
# ============================================================================

_CEO_PRIVATE_KEY: Optional[SigningKey] = None
_CEO_PUBLIC_KEY: Optional[VerifyKey] = None

def load_keys() -> None:
    """
    Load keys from environment paths into memory.
    MUST be called exactly once during initialization.
    
    R6.5 G2: Keys are loaded into memory-only structures.
    Path resolution happens ONLY here.
    """
    global _CEO_PRIVATE_KEY, _CEO_PUBLIC_KEY
    
    # Load Private Key
    priv_path = os.environ.get('CEO_PRIVATE_KEY_PATH')
    if not priv_path:
        raise CryptoError("CEO_PRIVATE_KEY_PATH not set.")
    if not os.path.exists(priv_path):
        raise CryptoError(f"CEO private key not found at {priv_path}")
        
    try:
        with open(priv_path, 'rb') as f:
            _CEO_PRIVATE_KEY = SigningKey(f.read())
    except Exception as e:
        raise CryptoError(f"Failed to load private key: {e}")

    # Load Public Key
    pub_path = os.environ.get('CEO_PUBLIC_KEY_PATH')
    if not pub_path:
        raise CryptoError("CEO_PUBLIC_KEY_PATH not set.")
    if not os.path.exists(pub_path):
        raise CryptoError(f"CEO public key not found at {pub_path}")
        
    try:
        with open(pub_path, 'rb') as f:
            _CEO_PUBLIC_KEY = VerifyKey(f.read())
    except Exception as e:
        raise CryptoError(f"Failed to load public key: {e}")

def _get_private_key() -> SigningKey:
    """Internal accessor for private key."""
    if _CEO_PRIVATE_KEY is None:
        raise CryptoError("Keys not loaded. Call initialize_runtime() first.")
    return _CEO_PRIVATE_KEY

def _get_public_key() -> VerifyKey:
    """Internal accessor for public key."""
    if _CEO_PUBLIC_KEY is None:
        raise CryptoError("Keys not loaded. Call initialize_runtime() first.")
    return _CEO_PUBLIC_KEY

# ============================================================================
# D2: Unified Signature Protocol - R6.3 / R6.5
# ============================================================================

class Signature:
    """
    Unified signature protocol for all COO Runtime signing operations.
    
    R6.5 G2: 
    - Uses memory-resident keys ONLY.
    - Rejects path arguments.
    """
    
    @staticmethod
    def sign_data(data: bytes, private_key_path: str = None) -> bytes:
        """
        Sign arbitrary bytes using loaded private key.
        
        Args:
            data: Bytes to sign
            private_key_path: FORBIDDEN in R6.5. Must be None.
            
        Returns:
            Raw signature bytes
            
        Raises:
            CryptoError: If signing fails or path provided
        """
        if private_key_path is not None:
            raise CryptoError("R6.5 G2 Violation: Passing key paths to sign_data is forbidden.")
            
        try:
            sk = _get_private_key()
            return sk.sign(data).signature
        except Exception as e:
            raise CryptoError(f"Signing failed: {e}") from e
    
    @staticmethod
    def verify_data(data: bytes, signature: bytes, public_key_path: str = None) -> bool:
        """
        Verify signature over bytes using loaded public key.
        
        Args:
            data: Original data that was signed
            signature: Signature bytes to verify
            public_key_path: FORBIDDEN in R6.5. Must be None.
            
        Returns:
            True on successful verification, False on failure
        """
        if public_key_path is not None:
            raise CryptoError("R6.5 G2 Violation: Passing key paths to verify_data is forbidden.")
            
        try:
            vk = _get_public_key()
            vk.verify(data, signature)
            return True
        except (BadSignatureError, Exception):
            return False
    
    @staticmethod
    def sign_file(filepath: str, private_key_path: str = None) -> bytes:
        """
        Read file contents and sign them.
        """
        if private_key_path is not None:
             raise CryptoError("R6.5 G2 Violation: Passing key paths to sign_file is forbidden.")
             
        with open(filepath, 'rb') as f:
            data = f.read()
        return Signature.sign_data(data)
    
    @staticmethod
    def verify_file(filepath: str, signature: bytes, public_key_path: str = None) -> bool:
        """
        Read file contents and verify signature bytes.
        """
        if public_key_path is not None:
             raise CryptoError("R6.5 G2 Violation: Passing key paths to verify_file is forbidden.")

        with open(filepath, 'rb') as f:
            data = f.read()
        return Signature.verify_data(data, signature)

# ============================================================================
# Dev/Prod Mode Support (Supplemental R6.3 Guidance)
# ============================================================================

def create_signature_metadata(mode: str = None) -> Dict[str, Any]:
    """
    Create signature metadata with mode information.
    """
    if mode is None:
        mode = os.environ.get("COO_MODE", "dev")
    
    try:
        # Use memory key for ID generation
        vk = _get_public_key()
        key_bytes = vk.encode()
        key_id = hashlib.sha256(key_bytes).hexdigest()[:8]
    except CryptoError:
        key_id = "UNKNOWN"
    
    # R6.5 Hygiene Fix: Use pinned time source
    from ..runtime.init import get_initialized_amu0_path
    from ..util.context import get_pinned_time
    
    amu0_path = get_initialized_amu0_path()
    if amu0_path:
        try:
            timestamp = get_pinned_time(amu0_path).isoformat() + "Z"
        except Exception:
             # Fallback if pinned time fails (should not happen if initialized)
             timestamp = datetime.utcnow().isoformat() + "Z"
    else:
        # Fallback if runtime not initialized (e.g. unit tests or early boot)
        # But for deterministic operations, this should be initialized.
        timestamp = datetime.utcnow().isoformat() + "Z"

    return {
        "mode": mode,
        "timestamp": timestamp,
        "key_id": key_id
    }
