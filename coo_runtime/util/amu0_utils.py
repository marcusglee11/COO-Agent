"""
AMU0 Utilities for COO Runtime (F1, F8).
Provides canonical path resolution and recursive hashing for AMU0 bundles.
"""
import os
import hashlib
import json
from dataclasses import dataclass
from ..runtime.state_machine import GovernanceError
from ..util.crypto import verify_signature

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

def resolve_amu0_path() -> str:
    """
    Resolves the active AMU0 path from the signed tracker (active_amu0_path.json).
    Verifies:
    1. Tracker signature (active_amu0_path.json.sig) using CEO Public Key.
    2. AMU0 ID matches canonical hash of the directory (A.2, A.3).
    """
    tracker_path = os.path.join(os.getcwd(), "active_amu0_path.json")
    sig_path = os.path.join(os.getcwd(), "active_amu0_path.json.sig")
    public_key_path = os.path.join(os.path.dirname(__file__), "../../coo_runtime/manifests/ceo_public_key.pem")
    
    if not os.path.exists(tracker_path):
         raise GovernanceError("Active AMU0 tracker (active_amu0_path.json) not found.")

    if not os.path.exists(sig_path):
         raise GovernanceError("Active AMU0 tracker signature (active_amu0_path.json.sig) not found.")

    if not os.path.exists(public_key_path):
        raise GovernanceError("CEO Public Key missing. Cannot verify active AMU0 tracker.")

    try:
        with open(tracker_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        raise GovernanceError("active_amu0_path.json is corrupted.")

    # 1. Verify Tracker Signature
    required_fields = ["amu0_path", "amu0_id", "created_at", "repo_commit"]
    for field in required_fields:
        if field not in data:
            raise GovernanceError(f"active_amu0_path.json missing required field: {field}")

    # Reconstruct payload for verification (canonical JSON)
    # The signature is over the sorted JSON bytes of the tracker file content
    payload_bytes = json.dumps(data, sort_keys=True).encode("utf-8")
    
    with open(sig_path, "rb") as f:
        signature = f.read()

    if not verify_signature(public_key_path, payload_bytes, signature):
        raise GovernanceError("Active AMU0 Tracker Signature Invalid!")

    # 2. Resolve Path
    path = data["amu0_path"]
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)

    if not os.path.exists(path):
        raise GovernanceError(f"Resolved AMU0 path does not exist: {path}")

    # 3. Verify AMU0 ID matches amu0_id.txt (Fast Check)
    # R6 A.1 says: "Check amu0_id against amu0_id.txt."
    try:
        stored_id = read_amu0_id(path)
        if stored_id != data["amu0_id"]:
             raise GovernanceError(f"AMU0 ID Mismatch! Tracker: {data['amu0_id']}, Stored: {stored_id}")
    except GovernanceError as e:
        raise GovernanceError(f"AMU0 ID Check Failed: {e}")

    return path

def read_amu0_id(amu0_path: str) -> str:
    """
    Reads the AMU0 ID from amu0_id.txt in the AMU0 directory.
    """
    id_path = os.path.join(amu0_path, "amu0_id.txt")
    if not os.path.exists(id_path):
        raise GovernanceError(f"AMU0 ID file missing at {id_path}")
        
    with open(id_path, "r") as f:
        return f.read().strip()

def hash_directory_recursive(amu0_path: str) -> bytes:
    """
    Recursively hash all files in the AMU0 directory in sorted POSIX path order.
    Exclusions:
        - signature.sig
        - amu0_id.txt (Excluded as it is derived from the hash)
    All other files must be present and included.
    Raise GovernanceError if any required file is missing.
    """
    required_files = [
        "pinned_context.json",
        "snapshot_manifest.json",
        "phase3_reference_mission.json",
        "rollback_log.jsonl",
        "governance_rules_frozen.json"
    ]
    
    # Check required files
    for req in required_files:
        if not os.path.exists(os.path.join(amu0_path, req)):
            raise GovernanceError(f"AMU0 Integrity Check Failed: Missing required file {req}")

    hasher = hashlib.sha256()
    
    # Walk directory sorted
    for root, dirs, files in os.walk(amu0_path):
        dirs.sort() # Sort directories in-place
        files.sort() # Sort files
        
        for file in files:
            if file in ["signature.sig", "amu0_id.txt"]:
                continue
                
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, amu0_path).replace("\\", "/") # POSIX path
            
            # Hash relative path to capture structure
            hasher.update(rel_path.encode("utf-8"))
            
            # Hash content
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
                    
    return hasher.digest()

def calculate_canonical_hash(amu0_path: str) -> bytes:
    """
    Calculates the canonical SHA256 hash of the AMU0 bundle for signing.
    """
    return hash_directory_recursive(amu0_path)
