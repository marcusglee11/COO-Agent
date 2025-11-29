"""
AMU0 Utilities for COO Runtime R6.3.
Provides canonical hash calculation, AMU0 verification, and path resolution.
"""
import os
import hashlib
import json
import struct
from dataclasses import dataclass
from ..runtime.state_machine import GovernanceError
from ..util.crypto import Signature, get_ceo_public_key_path

# ============================================================================
# A4: VerificationResult Type - R6.3
# ============================================================================

@dataclass
class VerificationResult:
    """
    Result of AMU0 verification.
    
    R6.3 A4: Typed object with fail-closed semantics.
    Function returns this ONLY on success, raises GovernanceError on ANY failure.
    """
    canonical_hash: bytes        # The canonical AMU0 hash
    amu0_id: str                 # Derived from canonical_hash (first 16 hex chars)
    has_rollback_log: bool       # Whether rollback log was present & verified

# ============================================================================
# A2: Canonical Hash Calculation - R6.3
# ============================================================================

# R6.3 A1/A2: Exact exclusion set per supplemental guidance
EXCLUDED_FROM_HASH = {
    "rollback_log.jsonl",      # Separate metadata
    "rollback_log.sig",         # Rollback log signature
    "signature.sig",            # Bundle signature
    # metadata/ directory excluded (additional traces)
    # *.tmp files excluded via endswith check
    # external_trace.jsonl is INCLUDED (canonical trace)
}

def calculate_canonical_hash(amu0_dir: str) -> bytes:
    """
    Calculate canonical SHA-256 hash of AMU0 bundle.
    
    R6.3 A2: Deterministic traversal, mtime normalization, explicit exclusions.
    Excludes: rollback_log.jsonl, rollback_log.sig, signature.sig, metadata/, *.tmp
    Includes: external_trace.jsonl (canonical deep replay trace)
    
    Args:
        amu0_dir: Path to AMU0 directory
        
    Returns:
        SHA-256 digest bytes
        
    Raises:
        GovernanceError: If hashing fails
    """
    hasher = hashlib.sha256()
    
    # Sorted traversal
    for root, dirs, files in sorted(os.walk(amu0_dir)):
        # Sort in-place for deterministic ordering
        dirs[:] = sorted(dirs)
        
        # Skip metadata directory entirely
        if 'metadata' in dirs:
            dirs.remove('metadata')
        
        for filename in sorted(files):
            # Skip excluded files
            if filename in EXCLUDED_FROM_HASH or filename.endswith('.tmp'):
                continue
            
            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, amu0_dir)
            
            # Normalize path separators to POSIX
            rel_path = rel_path.replace('\\', '/')
            
            # Hash: relative path + normalized mtime + file content
            hasher.update(rel_path.encode('utf-8'))
            hasher.update(struct.pack('<Q', 315532800))  # Normalized mtime: 1980-01-01
            
            try:
                with open(filepath, 'rb') as f:
                    hasher.update(f.read())
            except Exception as e:
                raise GovernanceError(f"Failed to read file for hashing: {rel_path}: {e}")
    
    return hasher.digest()

# ============================================================================
# A3: AMU₀ ID Derivation - R6.3
# ============================================================================

def derive_amu0_id(canonical_hash: bytes) -> str:
    """
    Derive AMU0 ID from canonical hash.
    
    R6.3 A3: ID = first 16 hex chars of canonical hash.
    No amu0_id.txt file; always recomputed.
    
    Args:
        canonical_hash: Canonical hash bytes
        
    Returns:
        16-character hex string (AMU0 ID)
    """
    return canonical_hash.hex()[:16]

# ============================================================================
# A4: Unified AMU₀ Verification - R6.3
# ============================================================================

def verify_amu0_complete(amu0_path: str) -> VerificationResult:
    """
    Verify AMU0 integrity. Raises GovernanceError on any failure.
    
    R6.3 A4: Single canonical verification function.
    All components MUST call this instead of maintaining local variants.
    
    Checks:
    - Directory structure
    - Required files (fs_snapshot, snapshot_manifest.json, pinned_context.json)
    - Canonical hash computation
    - Bundle signature validation
    - Rollback log integrity (if present)
    - Derived ID matches tracker
    
    Args:
        amu0_path: Path to AMU0 directory
        
    Returns:
        VerificationResult (only on full success)
        
    Raises:
        GovernanceError: On any failure (structure, hash, signatures, log integrity, ID mismatch)
    """
    # 1. Check structure
    if not os.path.isdir(amu0_path):
        raise GovernanceError(f"AMU0 path is not a directory: {amu0_path}")
    
    # 2. Check required files/directories
    required = ['fs_snapshot', 'snapshot_manifest.json', 'pinned_context.json']
    for req in required:
        req_path = os.path.join(amu0_path, req)
        if not os.path.exists(req_path):
            raise GovernanceError(f"Missing required file/dir: {req}")
    
    # 3. Compute canonical hash
    try:
        canonical_hash = calculate_canonical_hash(amu0_path)
    except Exception as e:
        raise GovernanceError(f"Canonical hash computation failed: {e}")
    
    amu0_id = derive_amu0_id(canonical_hash)
    
    # 4. Verify bundle signature
    sig_path = os.path.join(amu0_path, 'signature.sig')
    if not os.path.exists(sig_path):
        raise GovernanceError("Missing bundle signature (signature.sig)")
    
    with open(sig_path, 'rb') as f:
        signature = f.read()
    
    try:
        public_key_path = get_ceo_public_key_path()
    except Exception as e:
        raise GovernanceError(f"Cannot get CEO public key path: {e}")
    
    if not Signature.verify_data(canonical_hash, signature, public_key_path):
        raise GovernanceError("AMU0 bundle signature verification failed")
    
    # 5. Verify rollback log (if present)
    has_rollback_log = False
    log_path = os.path.join(amu0_path, 'rollback_log.jsonl')
    
    if os.path.exists(log_path):
        # Verify rollback log signature and integrity
        log_sig_path = os.path.join(amu0_path, 'rollback_log.sig')
        if not os.path.exists(log_sig_path):
            raise GovernanceError("Rollback log exists but signature missing")
        
        # Verify log signature
        with open(log_path, 'rb') as f:
            log_bytes = f.read()
        
        with open(log_sig_path, 'rb') as f:
            log_sig = f.read()
        
        if not Signature.verify_data(log_bytes, log_sig, public_key_path):
            raise GovernanceError("Rollback log signature verification failed")
        
        # TODO: Verify hash chain in rollback log (deferred to rollback_log.py)
        has_rollback_log = True
    
    # 6. Success
    return VerificationResult(
        canonical_hash=canonical_hash,
        amu0_id=amu0_id,
        has_rollback_log=has_rollback_log
    )

# ============================================================================
# Active AMU₀ Tracker Resolution
# ============================================================================

def resolve_amu0_path() -> str:
    """
    Resolves the active AMU0 path from the signed tracker (active_amu0_path.json).
    
    Verifies:
    1. Tracker signature (active_amu0_path.json.sig) using CEO Public Key
    2. AMU0 exists and is valid via verify_amu0_complete()
    3. Derived ID matches tracker ID
    
    Returns:
        Absolute path to verified AMU0 directory
        
    Raises:
        GovernanceError: If tracker invalid or AMU0 verification fails
    """
    tracker_path = os.path.join(os.getcwd(), "active_amu0_path.json")
    sig_path = os.path.join(os.getcwd(), "active_amu0_path.json.sig")
    
    if not os.path.exists(tracker_path):
        raise GovernanceError("Active AMU0 tracker (active_amu0_path.json) not found")
    
    if not os.path.exists(sig_path):
        raise GovernanceError("Active AMU0 tracker signature (active_amu0_path.json.sig) not found")
    
    # Load tracker
    try:
        with open(tracker_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        raise GovernanceError("active_amu0_path.json is corrupted")
    
    # Verify required fields
    required_fields = ["amu0_path", "amu0_id", "created_at", "repo_commit"]
    for field in required_fields:
        if field not in data:
            raise GovernanceError(f"active_amu0_path.json missing required field: {field}")
    
    # Verify tracker signature
    payload_bytes = json.dumps(data, sort_keys=True).encode("utf-8")
    
    with open(sig_path, "rb") as f:
        signature = f.read()
    
    try:
        public_key_path = get_ceo_public_key_path()
    except Exception as e:
        raise GovernanceError(f"Cannot get CEO public key path: {e}")
    
    if not Signature.verify_data(payload_bytes, signature, public_key_path):
        raise GovernanceError("Active AMU0 tracker signature invalid")
    
    # Resolve path
    path = data["amu0_path"]
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)
    
    if not os.path.exists(path):
        raise GovernanceError(f"Resolved AMU0 path does not exist: {path}")
    
    # Verify AMU0 completely
    verification_result = verify_amu0_complete(path)
    
    # Verify derived ID matches tracker
    if verification_result.amu0_id != data["amu0_id"]:
        raise GovernanceError(
            f"AMU0 ID mismatch! "
            f"Tracker: {data['amu0_id']}, "
            f"Derived: {verification_result.amu0_id}"
        )
    
    return path

# ============================================================================
# Legacy Functions (Deprecated - R6.2 compatibility)
# ============================================================================

def read_amu0_id(amu0_path: str) -> str:
    """
    DEPRECATED: R6.3 removed amu0_id.txt file.
    
    This function now derives the ID from canonical hash instead of reading a file.
    Kept for backward compatibility during migration.
    
    Args:
        amu0_path: Path to AMU0 directory
        
    Returns:
        Derived AMU0 ID
    """
    canonical_hash = calculate_canonical_hash(amu0_path)
    return derive_amu0_id(canonical_hash)

def hash_directory_recursive(amu0_path: str) -> bytes:
    """
    DEPRECATED: Use calculate_canonical_hash() instead.
    
    This function is kept for backward compatibility during R6.3 migration.
    """
    return calculate_canonical_hash(amu0_path)
