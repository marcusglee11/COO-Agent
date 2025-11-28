"""
AMU0 Utilities for COO Runtime (F1, F8).
Provides canonical path resolution and recursive hashing for AMU0 bundles.
"""
import os
import hashlib
import json
from ..runtime.state_machine import GovernanceError
from ..util.crypto import verify_signature

def resolve_amu0_path() -> str:
    """
    Resolves the active AMU0 path from the signed tracker (active_amu0.json).
    Verifies:
    1. Tracker signature (A.2)
    2. AMU0 ID matches canonical hash of the directory (A.2, A.3)
    """
    tracker_path = os.path.join(os.getcwd(), "active_amu0.json")
    public_key_path = os.path.join(os.path.dirname(__file__), "../../coo_runtime/manifests/ceo_public_key.pem")
    
    if not os.path.exists(tracker_path):
         # Fallback for bootstrapping/tests if json doesn't exist yet? 
         # R6 implies strictness. But let's check if txt exists for backward compat during migration?
         # No, R6 is a fix packet. We should enforce the new way.
         raise GovernanceError("Active AMU0 tracker (active_amu0.json) not found.")

    if not os.path.exists(public_key_path):
        raise GovernanceError("CEO Public Key missing. Cannot verify active AMU0 tracker.")

    try:
        with open(tracker_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        raise GovernanceError("active_amu0.json is corrupted.")

    # 1. Verify Tracker Signature
    if "amu0_id" not in data or "path" not in data or "signature" not in data:
        raise GovernanceError("active_amu0.json missing required fields.")

    # Reconstruct payload for verification (canonical JSON)
    payload = {
        "amu0_id": data["amu0_id"],
        "path": data["path"]
    }
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = bytes.fromhex(data["signature"])

    if not verify_signature(public_key_path, payload_bytes, signature):
        raise GovernanceError("Active AMU0 Tracker Signature Invalid!")

    # 2. Resolve Path
    path = data["path"]
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)

    if not os.path.exists(path):
        raise GovernanceError(f"Resolved AMU0 path does not exist: {path}")

    # 3. Verify AMU0 ID matches Canonical Hash (Binding)
    # This ensures the directory content matches the ID signed in the tracker.
    # Note: This is expensive (hashing whole dir). 
    # R6 A.2 says: "verify that amu0_id matches canonical hash of AMU0".
    # We should do this.
    try:
        canonical_hash = calculate_canonical_hash(path)
        derived_id = canonical_hash.hex()[:16]
        if derived_id != data["amu0_id"]:
             raise GovernanceError(f"AMU0 ID Mismatch! Tracker: {data['amu0_id']}, Derived: {derived_id}")
    except GovernanceError as e:
        raise GovernanceError(f"AMU0 Integrity Check Failed during resolution: {e}")

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
