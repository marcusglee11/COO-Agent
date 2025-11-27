import logging
import os
import shutil
import json
import hashlib
from typing import Optional
from .state_machine import RuntimeFSM, RuntimeState, GovernanceError

class RollbackEngine:
    """
    Manages safe rollback to AMU0.
    Enforces:
    - 1 Automatic Rollback limit.
    - CEO Signature Verification on AMU0.
    - Halt -> QUESTION on failure.
    """

    def __init__(self, fsm: RuntimeFSM):
        self.fsm = fsm
        self.logger = logging.getLogger("RollbackEngine")
        self._rollback_count = 0
        self._max_rollbacks = 1

    def execute_rollback(self) -> None:
        """
        Executes the rollback protocol.
        """
        self.logger.warning("Initiating Rollback Protocol")

        if self._rollback_count >= self._max_rollbacks:
            self.fsm._force_error("Max Rollback Limit Reached (1). Halting.")
            # force_error raises GovernanceError, so we stop here.
            return

        try:
            # 1. Verify CEO Signature on AMU0
            self._verify_amu0_signature()

            # 2. Restore from AMU0
            self._restore_from_amu0()

            self._rollback_count += 1
            self.logger.info(f"Rollback Successful. Count: {self._rollback_count}/{self._max_rollbacks}")
            
            # After rollback, we are effectively back at AMU0 capture state or similar.
            # We transition FSM back to CAPTURE_AMU0 to allow retry or halt.
            self.fsm.transition_to(RuntimeState.CAPTURE_AMU0)
            
        except Exception as e:
            self.logger.critical(f"Rollback Failed: {e}")
            self.fsm._force_error(f"Rollback Failed: {e}")

    def _verify_amu0_signature(self) -> None:
        """
        Verifies the CEO's cryptographic signature on the AMU0 bundle.
        Uses Ed25519. No DEV-mode bypass - signature verification always required.
        """
        self.logger.info("Verifying CEO Signature on AMU0...")
        
        from ..util.crypto import verify_signature
        
        amu_dir = "amu0_capture"
        sig_path = os.path.join(amu_dir, "signature.sig")
        
        if not os.path.exists(sig_path):
            raise GovernanceError("AMU0 Signature Missing")
        
        # Read signature (raw bytes)
        with open(sig_path, "rb") as f:
            signature = f.read()
            
        # Re-calculate canonical hash to verify
        manifest_path = os.path.join(amu_dir, "snapshot_manifest.json")
        context_path = os.path.join(amu_dir, "pinned_context.json")
        
        hasher = hashlib.sha256()
        
        # Hash files in sorted order (same as signing)
        for filepath in sorted([manifest_path, context_path]):
            if os.path.exists(filepath):
                with open(filepath, "rb") as f:
                    hasher.update(f.read())
        
        canonical_hash = hasher.digest()
        
        # Verify signature using CEO public key (resolve absolute path)
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        public_key_path = os.path.join(script_dir, "coo_runtime", "manifests", "ceo_public_key.pem")
        
        if not verify_signature(public_key_path, canonical_hash, signature):
            raise GovernanceError("AMU0 Signature Verification Failed")
        
        self.logger.info("AMU0 Signature verified successfully.")

    def _restore_from_amu0(self) -> None:
        """
        Restores filesystem, DB, etc. from AMU0.
        """
        self.logger.info("Restoring System from AMU0...")
        
        amu_dir = "amu0_capture"
        if not os.path.exists(amu_dir):
            raise GovernanceError("AMU0 Capture not found. Cannot rollback.")
            
        # Restore critical directories
        # We assume AMU0 contains 'manifests', 'pinned_context.json', etc.
        # And potentially a snapshot of 'project_builder' if we need to restore it.
        # If PB was deleted, we need to restore it.
        
        # Verify Snapshot Integrity
        manifest_path = os.path.join(amu_dir, "snapshot_manifest.json")
        if not os.path.exists(manifest_path):
             raise GovernanceError("AMU0 Snapshot Manifest Missing. Cannot rollback safely.")
             
        with open(manifest_path, "r") as f:
            snapshot_manifest = json.load(f)
            
        snapshot_root = os.path.join(amu_dir, "fs_snapshot")
        if not os.path.exists(snapshot_root):
             raise GovernanceError("AMU0 Filesystem Snapshot Missing. Cannot rollback safely.")
             
        # Verify hashes
        self.logger.info("Verifying Snapshot Integrity...")
        for rel_path, expected_hash in snapshot_manifest.items():
            # rel_path is relative to repo root, but in snapshot it's under fs_snapshot
            # Wait, _snapshot_filesystem stored full paths or relative?
            # It stored relative to repo root.
            # And structure in fs_snapshot mirrors repo root.
            # So if rel_path is "project_builder/main.py", it is at "amu0_capture/fs_snapshot/project_builder/main.py"
            
            snapshot_file_path = os.path.join(snapshot_root, rel_path)
            if not os.path.exists(snapshot_file_path):
                 raise GovernanceError(f"Snapshot Corrupt: Missing file {rel_path}")
                 
            with open(snapshot_file_path, "rb") as f:
                actual_hash = hashlib.sha256(f.read()).hexdigest()
                
            if actual_hash != expected_hash:
                 raise GovernanceError(f"Snapshot Corrupt: Hash mismatch for {rel_path}")
                 
        self.logger.info("Snapshot Integrity Verified.")

        # Restore from Snapshot
        # We restore everything in the snapshot to the repo root.
        for item in os.listdir(snapshot_root):
            src = os.path.join(snapshot_root, item)
            dest = os.path.join(os.getcwd(), item)
            
            if os.path.isdir(src):
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
                self.logger.info(f"Restored directory: {item}")
            else:
                shutil.copy2(src, dest)
                self.logger.info(f"Restored file: {item}")
