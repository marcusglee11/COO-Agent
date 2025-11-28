import os
import json
import shutil
import logging
from typing import Optional, Dict, Any
from ..runtime.state_machine import RuntimeFSM, RuntimeState, GovernanceError
from ..util.crypto import verify_signature
from ..util.context import enforce_pinned_context_or_fail
from ..util import amu0_utils
from .rollback_log import RollbackLog

class RollbackEngine:
    """
    Manages the rollback mechanism for the COO Runtime.
    Enforces:
    1. AMU0 Signature Verification (Ed25519)
    2. Filesystem Restoration
    3. Rollback Limits (Persisted in AMU0)
    4. Pinned Context Enforcement (Post-Rollback)
    """
    MAX_ROLLBACKS = 3

    def __init__(self, fsm: RuntimeFSM):
        self.fsm = fsm
        self.logger = logging.getLogger("RollbackEngine")
        # CEO Public Key Path
        self.public_key_path = os.path.join(os.path.dirname(__file__), "../../coo_runtime/manifests/ceo_public_key.pem")
        # CEO Private Key Path (for signing rollback log) - In prod this would be separate or HSM
        self.private_key_path = os.path.join(os.path.dirname(__file__), "../../coo_runtime/manifests/ceo_private_key.pem")
        
        self.rollback_log = RollbackLog(self.private_key_path, self.public_key_path)

    def execute_rollback(self) -> None:
        """
        Executes the rollback process.
        """
        self.logger.warning("Initiating Rollback Sequence...")
        
        # 1. Resolve AMU0 Path (F8)
        try:
            amu0_path = amu0_utils.resolve_amu0_path()
        except GovernanceError as e:
            self.logger.critical(f"Rollback Failed: Could not resolve AMU0 path: {e}")
            self.fsm.transition_to(RuntimeState.ERROR)
            raise e

        # 2. Check Rollback Limit via Signed Log (A.1)
        try:
            current_count = self.rollback_log.get_rollback_count(amu0_path)
            if current_count >= self.MAX_ROLLBACKS:
                self.logger.critical(f"Max rollbacks exceeded ({current_count}/{self.MAX_ROLLBACKS}).")
                self.fsm.transition_to(RuntimeState.ERROR)
                raise GovernanceError("Max rollbacks exceeded.")
        except GovernanceError as e:
             self.logger.critical(f"Rollback Log Verification Failed: {e}")
             self.fsm.transition_to(RuntimeState.ERROR)
             raise e

        # 3. Verify AMU0 Integrity & Signature (F1)
        self._verify_amu0_signature(amu0_path)

        # 4. Restore Filesystem
        self._restore_from_amu0(amu0_path)

        # 5. Log Rollback Action (A.1)
        try:
            self.rollback_log.append_entry(amu0_path, {
                "action": "ROLLBACK",
                "reason": "Governance Failure or Exception",
                "actor": "RollbackEngine"
            })
        except GovernanceError as e:
            self.logger.critical(f"Failed to append to rollback log: {e}")
            self.fsm.transition_to(RuntimeState.ERROR)
            raise e

        # 6. Enforce Pinned Context (F9)
        # Must happen after restore to ensure environment is reset to pinned state
        try:
            enforce_pinned_context_or_fail(amu0_path)
        except GovernanceError as e:
            self.logger.critical(f"Post-Rollback Context Enforcement Failed: {e}")
            self.fsm.transition_to(RuntimeState.ERROR)
            raise e

        # 7. Transition FSM
        # Rollback returns to GATES state to retry
        self.fsm.transition_to(RuntimeState.GATES)
        self.logger.info(f"Rollback Complete. Count: {current_count + 1}")

    def _verify_amu0_signature(self, amu0_path: str) -> None:
        """
        Verifies the Ed25519 signature of the AMU0 bundle.
        """
        if not os.path.exists(self.public_key_path):
             # In production, this is fatal.
             raise GovernanceError("CEO Public Key missing. Cannot verify AMU0.")

        sig_path = os.path.join(amu0_path, "signature.sig")
        if not os.path.exists(sig_path):
            raise GovernanceError("AMU0 Signature missing.")

        with open(sig_path, "rb") as f:
            signature = f.read()

        # Calculate Canonical Hash (F1, F8)
        try:
            canonical_hash = amu0_utils.calculate_canonical_hash(amu0_path)
        except GovernanceError as e:
             raise GovernanceError(f"AMU0 Verification Failed (Hashing): {e}")

        # Verify
        if not verify_signature(self.public_key_path, canonical_hash, signature):
            raise GovernanceError("AMU0 Signature Verification Failed! Bundle may be tampered.")

    def _restore_from_amu0(self, amu0_path: str) -> None:
        """
        Restores the filesystem from the AMU0 snapshot.
        """
        snapshot_root = os.path.join(amu0_path, "fs_snapshot")
        if not os.path.exists(snapshot_root):
            raise GovernanceError("AMU0 Snapshot missing.")

        # Restore Project Builder
        if os.path.exists("project_builder"):
            shutil.rmtree("project_builder")
        if os.path.exists(os.path.join(snapshot_root, "project_builder")):
            shutil.copytree(os.path.join(snapshot_root, "project_builder"), "project_builder")

        # Restore COO
        if os.path.exists("coo"):
            shutil.rmtree("coo")
        if os.path.exists(os.path.join(snapshot_root, "coo")):
            shutil.copytree(os.path.join(snapshot_root, "coo"), "coo")

        # Restore Manifests (Optional, usually in coo/manifests or separate)
        if os.path.exists("manifests"):
            shutil.rmtree("manifests")
        if os.path.exists(os.path.join(snapshot_root, "manifests")):
            shutil.copytree(os.path.join(snapshot_root, "manifests"), "manifests")
            
        # Restore Reference Mission
        if os.path.exists("phase3_reference_mission.json"):
            os.remove("phase3_reference_mission.json")
        shutil.copy(os.path.join(amu0_path, "phase3_reference_mission.json"), "phase3_reference_mission.json")
