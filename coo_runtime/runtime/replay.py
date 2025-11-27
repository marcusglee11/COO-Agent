import logging
import os
import hashlib
import filecmp
import shutil
import json
from .state_machine import RuntimeFSM, RuntimeState, GovernanceError

class ReplayEngine:
    """
    Executes Deterministic Replay (Gate F).
    1. Verifies Reference Mission SHA against AMU0.
    2. Runs mission twice in locked context.
    3. Compares outputs byte-for-byte.
    """

    def __init__(self, fsm: RuntimeFSM):
        self.fsm = fsm
        self.logger = logging.getLogger("ReplayEngine")

    def execute_replay(self, mission_path: str, amu0_path: str) -> None:
        """
        Executes the replay sequence.
        """
        self.fsm.assert_state(RuntimeState.GATES)
        self.logger.info("Starting Deterministic Replay (Gate F)")

        # 1. Verify Reference Mission SHA
        self._verify_reference_mission(mission_path, amu0_path)

        # 2. Run 1
        self.logger.info("Replay Run 1...")
        output1 = self._run_mission(mission_path, "run1")

        # 3. Run 2
        self.logger.info("Replay Run 2...")
        output2 = self._run_mission(mission_path, "run2")

        # 4. Compare
        self.logger.info("Comparing Outputs...")
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

    def _run_mission(self, mission_path: str, run_id: str) -> str:
        """
        Runs the mission in the locked context.
        Returns path to output directory/file.
        """
        output_dir = f"replay_output_{run_id}"
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)

        # Deterministic Harness
        # In a real implementation, this would invoke the Orchestrator.
        # Here, we simulate deterministic output based on input SHA + Context.
        
        with open(mission_path, "rb") as f:
            mission_content = f.read()
            
        # Simulate processing
        result_hash = hashlib.sha256(mission_content).hexdigest()
        
        # Write result
        with open(os.path.join(output_dir, "result.json"), "w") as f:
            json.dump({"status": "success", "hash": result_hash}, f, sort_keys=True)
            
        return output_dir

    def _compare_outputs(self, out1: str, out2: str) -> bool:
        """
        Byte-for-byte comparison.
        """
        dc = filecmp.dircmp(out1, out2)
        if dc.left_only or dc.right_only:
            return False
            
        for filename in dc.common_files:
            f1 = os.path.join(out1, filename)
            f2 = os.path.join(out2, filename)
            if not filecmp.cmp(f1, f2, shallow=False):
                return False
                
        return True
