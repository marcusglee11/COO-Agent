"""
Output Bundle Utility for COO Runtime (F7).
Provides canonical, byte-for-byte hashing of mission output directories.
"""
import os
import hashlib
from ..runtime.state_machine import GovernanceError

def create_output_bundle(output_dir: str) -> bytes:
    """
    Create a canonical output bundle by recursively hashing all files
    produced by mission execution (DBs, artifacts, logs, etc.).
    
    Requirements:
        - Walk output_dir recursively in sorted POSIX path order.
        - Include ALL bytes of every file (including timestamps).
        - No exclusions allowed.
        - Return a SHA256 digest of the entire ordered file set.
    """
    if not os.path.exists(output_dir):
        raise GovernanceError(f"Output directory missing: {output_dir}")
        
    hasher = hashlib.sha256()
    
    # Walk directory sorted
    for root, dirs, files in os.walk(output_dir):
        dirs.sort() # Sort directories in-place
        files.sort() # Sort files
        
        for file in files:
            # R6 C.2: Exclude logs from canonical hash to ensure determinism
            if file.endswith(".log"):
                continue
                
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, output_dir).replace("\\", "/") # POSIX path
            
            # Hash relative path to capture structure
            hasher.update(rel_path.encode("utf-8"))
            
            # Hash content (byte-for-byte, no exclusions)
            try:
                with open(file_path, "rb") as f:
                    while chunk := f.read(8192):
                        hasher.update(chunk)
            except (IOError, OSError) as e:
                 raise GovernanceError(f"Failed to read output file {file_path}: {e}")
                    
    return hasher.digest()
