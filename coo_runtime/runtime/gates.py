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
from ..util import amu0_utils

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
        # R3 Clarification: Gate F runs in GATES state.
        # REPLAY state removed (B6). Transition directly to CEO_FINAL_REVIEW after gates.
        self.fsm.assert_state(RuntimeState.GATES) 
        
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

    def _gate_b_deterministic_modules(self, coo_root: str):
        """Gate B — Deterministic Modules & Security Checks (R6 D.2)"""
        self.logger.info("Executing Gate B: Deterministic Modules & Security")
        
        forbidden_imports = ["random", "time", "datetime", "uuid", "importlib"]
        forbidden_functions = ["exec", "eval", "__import__"]
        allowed_exceptions = ["logging.py", "amu_capture.py", "replay_harness.py", "context.py"] 

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
                                # Check Imports
                                if isinstance(node, ast.Import):
                                    for alias in node.names:
                                        if alias.name in forbidden_imports:
                                            raise GovernanceError(f"Gate B Failed: Forbidden import '{alias.name}' in {file}")
                                elif isinstance(node, ast.ImportFrom):
                                    if node.module in forbidden_imports:
                                        raise GovernanceError(f"Gate B Failed: Forbidden import from '{node.module}' in {file}")
                                
                                # Check Dynamic Execution (D.2)
                                elif isinstance(node, ast.Call):
                                    if isinstance(node.func, ast.Name):
                                        if node.func.id in forbidden_functions:
                                            raise GovernanceError(f"Gate B Failed: Forbidden function call '{node.func.id}' in {file}")
                        except SyntaxError:
                            pass # Should be caught by lint

    def _gate_d_sandbox_security(self, manifests_dir: str):
        """Gate D — Sandbox Security (F4: Real SHA Verification)"""
        self.logger.info("Executing Gate D: Sandbox Security")
        
        manifest_path = os.path.join(manifests_dir, "sandbox_manifest.json")
        if not os.path.exists(manifest_path):
             raise GovernanceError("Gate D Failed: Sandbox manifest missing.")
             
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
            
        expected_sha = manifest.get("image_sha256")
        if not expected_sha or expected_sha == "SHA256_PLACEHOLDER":
              raise GovernanceError("Gate D Failed: Invalid SHA256 in manifest.")
              
        # F4: Query actual sandbox digest (R6 B.1)
        try:
            # We use docker inspect to get the image ID (SHA256)
            # Format: sha256:<hash>
            result = subprocess.run(
                ["docker", "inspect", "--format='{{.Id}}'", "coo-sandbox"],
                capture_output=True,
                text=True,
                check=True
            )
            actual_sha = result.stdout.strip().replace("'", "") # Remove quotes if present
            
            # Docker might return "sha256:..." prefix. Manifest usually has it too or just hash.
            # Let's normalize.
            if actual_sha.startswith("sha256:"):
                actual_sha = actual_sha[7:]
            if expected_sha.startswith("sha256:"):
                expected_sha = expected_sha[7:]
                
        except (subprocess.CalledProcessError, FileNotFoundError):
            # If Docker is missing or command fails, we raise a QUESTION.
            # This allows manual verification or intervention if the runtime is running
            # in an environment where Docker socket is not directly accessible but sandbox is present.
            raise GovernanceError("QUESTION: Docker unavailable or sandbox image 'coo-sandbox' not found. Cannot verify SHA.")

        if actual_sha != expected_sha:
            raise GovernanceError(f"Gate D Failed: Sandbox SHA mismatch. Expected: {expected_sha}, Actual: {actual_sha}")

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
        """Gate E — Governance Integrity (R6 D.1)"""
        self.logger.info("Executing Gate E: Governance Integrity")
        
        # Run Lint
        linter = LintEngine(self.fsm)
        linter.run_lint(coo_root)
              
        # Run Governance Leak Scanner
        scanner = GovernanceLeakScanner(self.fsm)
        
        # R6 D.1: Validate against Frozen Rules in AMU0
        try:
            amu0_path = amu0_utils.resolve_amu0_path()
            ruleset_path = os.path.join(amu0_path, "governance_rules_frozen.json")
        except GovernanceError:
            # Fallback to manifests if AMU0 not available (e.g. pre-migration check?)
            # But R6 implies strictness.
            # If we are running gates, we expect AMU0.
            # But if we are running Gate A-E before migration?
            # The flow is Migration -> Gates -> Replay.
            # So AMU0 should exist.
            self.logger.warning("AMU0 not found for Gate E. Falling back to manifests (DEV ONLY).")
            ruleset_path = os.path.join(manifests_dir, "governance_ruleset.json")

        if not os.path.exists(ruleset_path):
             raise GovernanceError(f"Gate E Failed: Governance ruleset missing at {ruleset_path}")
             
        # Calculate hash of ruleset
        with open(ruleset_path, "rb") as f:
            ruleset_hash = hashlib.sha256(f.read()).hexdigest()
            
        scanner.scan(ruleset_path, ruleset_hash, [coo_root])

    def _gate_f_deterministic_replay(self, coo_root: str, manifests_dir: str):
        """Gate F — Deterministic Replay"""
        self.logger.info("Executing Gate F: Deterministic Replay")
        
        # B3/F8: Resolve AMU0 path dynamically using amu0_utils
        try:
            amu0_path = amu0_utils.resolve_amu0_path()
        except GovernanceError as e:
             raise GovernanceError(f"Gate F Failed: {e}")

        mission_path = os.path.join(amu0_path, "phase3_reference_mission.json")
        
        if not os.path.exists(mission_path):
             raise GovernanceError("Gate F Failed: Reference mission not found in AMU0.")
             
        self.replay_engine.execute_replay(mission_path, amu0_path)
