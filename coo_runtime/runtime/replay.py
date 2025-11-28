import logging
import os
import sys
import hashlib
import shutil
import json
import subprocess
from .state_machine import RuntimeFSM, RuntimeState, GovernanceError
from ..util.context import enforce_pinned_context_or_fail
from ..util.output_bundle import create_output_bundle
from ..util import amu0_utils

class ReplayEngine:
    """
    Executes Deterministic Replay (Gate F).
    1. Verifies Reference Mission SHA against AMU0.
    2. Runs mission twice in locked context.
    3. Compares outputs byte-for-byte (Output Bundle).
    """

    def __init__(self, fsm: RuntimeFSM):
        self.fsm = fsm
        self.logger = logging.getLogger("ReplayEngine")

    def execute_replay(self, mission_path: str, amu0_path: str, mode: str = "fast") -> None:
        """
        Executes the replay sequence.
        Args:
            mission_path: Path to reference mission
            amu0_path: Path to AMU0
            mode: "fast" (mocked) or "deep" (trace-based)
        """
        self.fsm.assert_state(RuntimeState.GATES)
        self.logger.info(f"Starting Deterministic Replay (Gate F) - Mode: {mode}")

        # 1. Verify Reference Mission SHA
        self._verify_reference_mission(mission_path, amu0_path)

        # 2. Enforce Pinned Context (F2, R6 B.2)
        # We must enforce the environment captured in AMU0.
        self.logger.info("Enforcing Pinned Context from AMU0...")
        pinned_env = enforce_pinned_context_or_fail(amu0_path)

        # 3. Run 1
        self.logger.info("Replay Run 1...")
        output1 = self._run_mission(mission_path, "run1", pinned_env, amu0_path, mode)

        # 4. Run 2
        self.logger.info("Replay Run 2...")
        output2 = self._run_mission(mission_path, "run2", pinned_env, amu0_path, mode)

        # 5. Compare (F7)
        self.logger.info("Comparing Outputs (Byte-for-Byte)...")
        if not self._compare_outputs(output1, output2):
             raise GovernanceError("Deterministic Replay Failed: Outputs do not match byte-for-byte.")

        self.logger.info("Deterministic Replay Passed.")

    def _verify_reference_mission(self, mission_path: str, amu0_path: str) -> None:
        """
        Verifies that the mission being replayed matches the one locked in AMU0.
        """
        # Calculate SHA of current mission
        with open(mission_path, "rb") as f:
            current_sha = hashlib.sha256(f.read()).hexdigest()
            
        # Get SHA from AMU0 manifest or file
        # For now, we assume we compare against the file in AMU0
        amu_mission_path = os.path.join(amu0_path, "phase3_reference_mission.json")
        if not os.path.exists(amu_mission_path):
            raise GovernanceError("AMU0 missing reference mission copy")
            
        with open(amu_mission_path, "rb") as f:
            amu_sha = hashlib.sha256(f.read()).hexdigest()
            
        if current_sha != amu_sha:
            raise GovernanceError("Replay Mission Mismatch: SHA256 does not match AMU0 locked version.")

    def _run_mission(self, mission_path: str, run_id: str, env: dict, amu0_path: str, mode: str) -> str:
        """
        Runs the mission in the locked context using the Replay Harness subprocess.
        Returns path to output directory.
        """
        output_dir = f"replay_output_{run_id}"
        
        # Harness script path
        harness_path = os.path.join(os.path.dirname(__file__), "replay_harness.py")
        if not os.path.exists(harness_path):
            raise GovernanceError(f"Replay Harness missing at {harness_path}")

        self.logger.info(f"Launching Replay Harness for {run_id}...")
        
        try:
            # Run harness in subprocess with pinned environment (R6 B.2)
            subprocess.run(
                [sys.executable, harness_path, mission_path, output_dir, "--amu0", amu0_path, "--mode", mode],
                check=True,
                env=env,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Replay Harness Failed: {e.stdout}\n{e.stderr}")
            raise GovernanceError(f"Replay Execution Failed (Subprocess): {e}")

        return output_dir

    def _compare_outputs(self, out1: str, out2: str) -> bool:
        """
        Strict byte-for-byte comparison of output bundles (F7).
        """
        try:
            hash1 = create_output_bundle(out1)
            hash2 = create_output_bundle(out2)
            
            if hash1 != hash2:
                self.logger.error(f"Bundle Hash Mismatch: {hash1.hex()} vs {hash2.hex()}")
                return False
                
            return True
        except Exception as e:
            self.logger.error(f"Comparison failed: {e}")
            return False
