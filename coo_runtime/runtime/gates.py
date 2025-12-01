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
from ..util.subprocess import run_pinned_subprocess
from ..util.questions import raise_question, QuestionType

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
            self._gate_c_test_suite_integrity(test_runner_script, manifests_dir)
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
            raise_question(QuestionType.GATE_FAILURE, "Gate A Failed: 'coo' directory missing.")
        
        required_subdirs = ["runtime", "orchestrator", "sandbox"]
        for subdir in required_subdirs:
            if not os.path.exists(os.path.join(coo_root, subdir)):
                raise_question(QuestionType.GATE_FAILURE, f"Gate A Failed: Missing required subdirectory '{subdir}' in 'coo'.")

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
                                            raise_question(QuestionType.MODE_VIOLATION, f"Gate B Failed: Forbidden import '{alias.name}' in {file}")
                                elif isinstance(node, ast.ImportFrom):
                                    if node.module in forbidden_imports:
                                        raise_question(QuestionType.MODE_VIOLATION, f"Gate B Failed: Forbidden import from '{node.module}' in {file}")
                                
                                # Check Dynamic Execution (D.2)
                                elif isinstance(node, ast.Call):
                                    if isinstance(node.func, ast.Name):
                                        if node.func.id in forbidden_functions:
                                            raise_question(QuestionType.MODE_VIOLATION, f"Gate B Failed: Forbidden function call '{node.func.id}' in {file}")
                        except SyntaxError:
                            pass # Should be caught by lint

    def _gate_d_sandbox_security(self, manifests_dir: str):
        """Gate D — Sandbox Security (F4: Real SHA Verification)"""
        self.logger.info("Executing Gate D: Sandbox Security")
        
        manifest_path = os.path.join(manifests_dir, "sandbox_manifest.json")
        if not os.path.exists(manifest_path):
             raise_question(QuestionType.SANDBOX_SECURITY, "Gate D Failed: Sandbox manifest missing.")
             
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
            
        expected_sha = manifest.get("image_sha256")
        if not expected_sha or expected_sha == "SHA256_PLACEHOLDER":
              raise_question(QuestionType.SANDBOX_SECURITY, "Gate D Failed: Invalid SHA256 in manifest.")
              
        # F4: Query actual sandbox digest (R6 B.1)
        actual_sha = None
        amu0_path = amu0_utils.resolve_amu0_path()
        
        # Try Docker
        try:
            result = run_pinned_subprocess(
                ["docker", "inspect", "--format='{{.Id}}'", "coo-sandbox"],
                amu0_path,
                capture_output=True,
                text=True,
                check=True
            )
            actual_sha = result.stdout.strip().replace("'", "")
        except Exception:
            # Try Podman
            try:
                result = run_pinned_subprocess(
                    ["podman", "inspect", "--format='{{.Id}}'", "coo-sandbox"],
                    amu0_path,
                    capture_output=True,
                    text=True,
                    check=True
                )
                actual_sha = result.stdout.strip().replace("'", "")
            except Exception:
                pass

        if not actual_sha:
            # Fail Closed (A.5)
            raise_question(QuestionType.SANDBOX_SECURITY, "Gate D Failed: OCI Runtime (Docker/Podman) unavailable or 'coo-sandbox' image not found.")

        # Normalize SHA
        if actual_sha.startswith("sha256:"):
            actual_sha = actual_sha[7:]
        if expected_sha.startswith("sha256:"):
            expected_sha = expected_sha[7:]

        if actual_sha != expected_sha:
            raise_question(QuestionType.SANDBOX_SECURITY, f"Gate D Failed: Sandbox SHA mismatch. Expected: {expected_sha}, Actual: {actual_sha}")

    def _gate_c_test_suite_integrity(self, test_runner_script: str, manifests_dir: str = None):
        """Gate C — Test Suite Integrity (A.11)"""
        self.logger.info("Executing Gate C: Test Suite Integrity")
        
        # 1. Verify Test Runner Hash (A.11)
        if manifests_dir:
            test_manifest_path = os.path.join(manifests_dir, "test_manifest.json")
            if os.path.exists(test_manifest_path):
                with open(test_manifest_path, "r") as f:
                    manifest = json.load(f)
                expected_sha = manifest.get("test_runner_sha256")
                
                if expected_sha:
                    with open(test_runner_script, "rb") as f:
                        actual_sha = hashlib.sha256(f.read()).hexdigest()
                    
                    if actual_sha != expected_sha:
                        raise_question(QuestionType.GATE_FAILURE, f"Gate C Failed: Test Runner SHA mismatch. Expected: {expected_sha}, Actual: {actual_sha}")
                else:
                    raise_question(QuestionType.GATE_FAILURE, "Gate C Failed: test_runner_sha256 missing in test_manifest.json")
            else:
                 raise_question(QuestionType.GATE_FAILURE, "Gate C Failed: test_manifest.json missing.")
        else:
            raise_question(QuestionType.GATE_FAILURE, "Gate C Failed: manifests_dir not provided for verification.")

        # Run the full test suite and fail on ANY error.
        try:
            # R6 A.15: Subprocess Enforcement
            amu0_path = amu0_utils.resolve_amu0_path()
            
            result = run_pinned_subprocess(
                [sys.executable, test_runner_script], 
                amu0_path,
                check=True, 
                capture_output=True, 
                text=True
            )
            self.logger.info("Test Suite Passed.")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Test Suite Output: {e.stdout}\n{e.stderr}")
            raise_question(QuestionType.GATE_FAILURE, f"Gate C Failed: Test suite failed with exit code {e.returncode}")

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
            snapshot_manifest_path = os.path.join(amu0_path, "snapshot_manifest.json")
            
            if not os.path.exists(ruleset_path):
                 raise_question(QuestionType.GATE_FAILURE, f"Gate E Failed: Frozen ruleset missing at {ruleset_path}")
                 
            if not os.path.exists(snapshot_manifest_path):
                 raise_question(QuestionType.GATE_FAILURE, "Gate E Failed: Snapshot manifest missing in AMU0.")
                 
            with open(snapshot_manifest_path, "r") as f:
                snapshot_manifest = json.load(f)
                
            expected_hash = snapshot_manifest.get("governance_rules_sha256")
            if not expected_hash:
                 raise_question(QuestionType.GATE_FAILURE, "Gate E Failed: governance_rules_sha256 missing in snapshot manifest.")
                 
            # Compute Hash
            with open(ruleset_path, "rb") as f:
                actual_hash = hashlib.sha256(f.read()).hexdigest()
                
            if actual_hash != expected_hash:
                 raise_question(QuestionType.GATE_FAILURE, f"Gate E Failed: Frozen ruleset hash mismatch. Expected: {expected_hash}, Actual: {actual_hash}")
                 
        except GovernanceError as e:
            # Fallback only allowed if strictly dev mode and explicitly requested?
            # R6 implies strictness. "Use frozen ruleset only".
            # If AMU0 is missing, we can't run Gate E strictly.
            # But maybe we are running Gate E before AMU0 capture?
            # No, Gate E is after Gates A-D. AMU0 capture is AFTER Gates.
            # Wait. The FSM says: GATES -> CAPTURE_AMU0.
            # So AMU0 does NOT exist when Gates run!
            # This is a circular dependency in my logic or the spec.
            # "During capture: compute SHA... During Gate E: Reload snapshot_manifest... Use frozen ruleset".
            # If Gate E runs BEFORE Capture, how can it use the frozen ruleset from AMU0?
            
            # Let's re-read the spec/plan.
            # A3: "checkpoint_state MUST be called... After GATES... After CAPTURE_AMU0".
            # A9: "During Gate E: Reload snapshot_manifest... Use frozen ruleset".
            
            # If Gates run before Capture, then Gate E cannot verify against AMU0.
            # Unless... we are verifying a PREVIOUS AMU0? No, that doesn't make sense for a new build.
            # OR, the Gates run AFTER Capture?
            # FSM: CAPTURE_AMU0 -> MIGRATION -> GATES.
            # Ah! `state_machine.py` says:
            # RuntimeState.CAPTURE_AMU0: [RuntimeState.MIGRATION_SEQUENCE, ...]
            # RuntimeState.MIGRATION_SEQUENCE: [RuntimeState.GATES, ...]
            # So Capture happens BEFORE Gates.
            # So AMU0 EXISTS when Gates run.
            # My previous assumption was wrong.
            # So `resolve_amu0_path` should work.
            raise e

        scanner.scan(ruleset_path, actual_hash, [coo_root])

    def _gate_f_deterministic_replay(self, coo_root: str, manifests_dir: str):
        """Gate F — Deterministic Replay"""
        self.logger.info("Executing Gate F: Deterministic Replay")
        
        # B3/F8: Resolve AMU0 path dynamically using amu0_utils
        try:
            amu0_path = amu0_utils.resolve_amu0_path()
        except GovernanceError as e:
             raise_question(QuestionType.GATE_FAILURE, f"Gate F Failed: {e}")

        mission_path = os.path.join(amu0_path, "phase3_reference_mission.json")
        
        if not os.path.exists(mission_path):
             raise_question(QuestionType.GATE_FAILURE, "Gate F Failed: Reference mission not found in AMU0.")
             
        self.replay_engine.execute_replay(mission_path, amu0_path)
