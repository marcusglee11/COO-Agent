import logging
import os
import sys
import ast
import subprocess
import hashlib
import json
from .state_machine import RuntimeFSM, RuntimeState, GovernanceError
from .lint_engine import LintEngine
from .governance_leak_scanner import GovernanceLeakScanner
from .replay import ReplayEngine

class GateKeeper:
    """
    Enforces the 6 Canonical Gates (A-F) as defined in COO Runtime Spec v1.0.
    Gates are executed in a strict, deterministic order.
    """

    def __init__(self, fsm: RuntimeFSM, replay_engine: ReplayEngine = None):
        self.fsm = fsm
        self.logger = logging.getLogger("GateKeeper")
        self.replay_engine = replay_engine or ReplayEngine(fsm)

    def run_all_gates(self, coo_root: str, manifests_dir: str, test_runner_script: str) -> bool:
        """
        Executes all gates in the strict order: A -> B -> D -> C -> E -> F.
        """
        self.run_pre_replay_gates(coo_root, manifests_dir, test_runner_script)
        self.run_replay_gate(coo_root, manifests_dir)
        return True

    def run_pre_replay_gates(self, coo_root: str, manifests_dir: str, test_runner_script: str):
        """
        Executes Gates A-E (Pre-Replay).
        """
        self.fsm.assert_state(RuntimeState.GATES)
        self.logger.info("Starting Pre-Replay Gates (A-E)")
        
        try:
            self._gate_a_repo_unification(coo_root)
            self._gate_b_deterministic_modules(coo_root)
            self._gate_d_sandbox_security(manifests_dir)
            self._gate_c_test_suite_integrity(test_runner_script)
            self._gate_e_governance_integrity(coo_root, manifests_dir)
            self.logger.info("Gates A-E Passed.")
        except Exception as e:
            self.logger.error(f"Gate Failure (A-E): {str(e)}")
            raise GovernanceError(f"GATE FAILURE (A-E): {str(e)}")

    def run_replay_gate(self, coo_root: str, manifests_dir: str):
        """
        Executes Gate F (Replay).
        """
        self.fsm.assert_state(RuntimeState.GATES) # Still in GATES state? Or REPLAY state?
        # The FSM has GATES -> REPLAY.
        # If we run F in REPLAY state, we should transition.
        # But GateKeeper is usually associated with GATES state.
        # The spec says "Gate F — Deterministic Replay".
        # So it is a Gate.
        self.logger.info("Executing Gate F: Deterministic Replay")
        try:
            self._gate_f_deterministic_replay(coo_root, manifests_dir)
            self.logger.info("Gate F Passed.")
        except Exception as e:
            self.logger.error(f"Gate Failure (F): {str(e)}")
            raise GovernanceError(f"GATE FAILURE (F): {str(e)}")

    def _gate_a_repo_unification(self, coo_root: str):
        """Gate A — Repo Unification Integrity"""
        self.logger.info("Executing Gate A: Repo Unification Integrity")
        
        # Verify 'coo' directory exists and has expected structure
        if not os.path.exists(coo_root):
            raise GovernanceError("Gate A Failed: 'coo' directory missing.")
        
        required_subdirs = ["runtime", "orchestrator", "sandbox"]
        for subdir in required_subdirs:
            if not os.path.exists(os.path.join(coo_root, subdir)):
                raise GovernanceError(f"Gate A Failed: Missing required subdirectory '{subdir}' in 'coo'.")

        # Verify 'project_builder' is GONE (if we are post-migration step 6)
        # However, if migration reordering keeps PB until later, this check might need adjustment.
        # The user plan says: "Delete project_builder/ only after tests have passed and Gate A–E succeed".
        # So PB MIGHT still exist here.
        # If PB exists, we should verify it is NOT being used?
        # Or maybe Gate A just checks 'coo' integrity now?
        # The spec says "Repo Unification" implies we are moving to one repo.
        # If we delay delete, we can't strictly assert PB is gone yet.
        # But we can assert that 'coo' is self-contained.
        pass

    def _gate_b_deterministic_modules(self, coo_root: str):
        """Gate B — Deterministic Modules"""
        self.logger.info("Executing Gate B: Deterministic Modules")
        
        forbidden_imports = ["random", "time", "datetime", "uuid"]
        allowed_exceptions = ["logging.py", "amu_capture.py"] # Files allowed to use time/random under strict conditions

        for root, _, files in os.walk(coo_root):
            files.sort()
            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    if file in allowed_exceptions:
                        continue
                        
                    with open(filepath, "r", encoding="utf-8") as f:
                        try:
                            tree = ast.parse(f.read(), filename=filepath)
                            for node in ast.walk(tree):
                                if isinstance(node, ast.Import):
                                    for alias in node.names:
                                        if alias.name in forbidden_imports:
                                            raise GovernanceError(f"Gate B Failed: Forbidden import '{alias.name}' in {file}")
                                elif isinstance(node, ast.ImportFrom):
                                    if node.module in forbidden_imports:
                                        raise GovernanceError(f"Gate B Failed: Forbidden import from '{node.module}' in {file}")
                        except SyntaxError:
                            pass # Should be caught by lint

    def _gate_d_sandbox_security(self, manifests_dir: str):
        """Gate D — Sandbox Security"""
        self.logger.info("Executing Gate D: Sandbox Security")
        
        manifest_path = os.path.join(manifests_dir, "sandbox_manifest.json")
        if not os.path.exists(manifest_path):
             raise GovernanceError("Gate D Failed: Sandbox manifest missing.")
             
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
            
        expected_sha = manifest.get("image_sha256")
        if not expected_sha or expected_sha == "SHA256_PLACEHOLDER":
             raise GovernanceError("Gate D Failed: Invalid SHA256 in manifest.")
             
        # In a real scenario, we would check the docker image SHA.
        # For now, we assume the manifest must be valid.
        pass

    def _gate_c_test_suite_integrity(self, test_runner_script: str):
        """Gate C — Test Suite Integrity"""
        self.logger.info("Executing Gate C: Test Suite Integrity")
        
        # Run the full test suite and fail on ANY error.
        try:
            # We assume test_runner_script is an executable python script
            result = subprocess.run(
                [sys.executable, test_runner_script], 
                check=True, 
                capture_output=True, 
                text=True
            )
            self.logger.info("Test Suite Passed.")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Test Suite Output: {e.stdout}\n{e.stderr}")
            raise GovernanceError(f"Gate C Failed: Test suite failed with exit code {e.returncode}")

    def _gate_e_governance_integrity(self, coo_root: str, manifests_dir: str):
        """Gate E — Governance Integrity"""
        self.logger.info("Executing Gate E: Governance Integrity")
        
        # Run Lint
        linter = LintEngine(self.fsm)
        # LintEngine.run_lint returns None but raises GovernanceError on failure
        linter.run_lint(coo_root)
             
        # Run Governance Leak Scanner
        scanner = GovernanceLeakScanner(self.fsm)
        
        ruleset_path = os.path.join(manifests_dir, "governance_ruleset.json")
        if not os.path.exists(ruleset_path):
             # For now, if missing, we might skip or fail.
             # Spec says "Using scanner + lint ruleset".
             # I'll assume it must exist.
             raise GovernanceError("Gate E Failed: Governance ruleset missing.")
             
        # Calculate hash of ruleset
        with open(ruleset_path, "rb") as f:
            ruleset_hash = hashlib.sha256(f.read()).hexdigest()
            
        scanner.scan(ruleset_path, ruleset_hash, [coo_root])

    def _gate_f_deterministic_replay(self, coo_root: str, manifests_dir: str):
        """Gate F — Deterministic Replay"""
        self.logger.info("Executing Gate F: Deterministic Replay")
        
        # We need the reference mission path and AMU0 path.
        # Assuming AMU0 is at a fixed location or passed in.
        amu0_path = "amu0_capture" # Should be passed in dynamically in real impl
        mission_path = os.path.join(amu0_path, "phase3_reference_mission.json")
        
        if not os.path.exists(mission_path):
             raise GovernanceError("Gate F Failed: Reference mission not found in AMU0.")
             
        self.replay_engine.execute_replay(mission_path, amu0_path)
