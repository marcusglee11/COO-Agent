import os
import hashlib
import logging
import json
from typing import List, Dict
from .state_machine import RuntimeFSM, RuntimeState, GovernanceError

class GovernanceLeakScanner:
    """
    Scans for governance leaks in `project_builder/` and Implementation Packet.
    Enforces Alignment Layer v1.4 constraints.
    Uses a SHA256-pinned ruleset.
    """

    def __init__(self, fsm: RuntimeFSM):
        self.fsm = fsm
        self.logger = logging.getLogger("GovernanceLeakScanner")

    def scan(self, ruleset_path: str, expected_ruleset_hash: str, scan_targets: List[str]) -> None:
        """
        Executes the governance leak scan.
        1. Verifies ruleset integrity (SHA256).
        2. Scans specified targets (PB, IP).
        3. Halts on any violation.
        """
        # self.fsm.assert_state(RuntimeState.SCAN) # Spec FSM doesn't have explicit SCAN state, it's part of GATES or pre-freeze?
        # Spec says "5. GOVERNANCE-LEAK SCANNING & LINTING ... Using scanner + lint ruleset ... If ANY violation: Halt"
        # And "Gate E — Governance Integrity" calls this.
        # Also "Freeze activates ONLY after ... Amendments applied ... Scanned/Linted ... CEO Review"
        # So it runs before CEO Review and in Gate E.
        # The FSM has `AMENDMENT_VERIFY` which might include this, or `GATES`.
        # I won't assert state here to allow it to be called from multiple valid states (e.g. AMENDMENT_VERIFY, GATES).
        
        self.logger.info("Starting Governance Leak Scan")

        # 1. Verify Ruleset Integrity
        if not os.path.exists(ruleset_path):
             raise GovernanceError(f"Ruleset missing: {ruleset_path}")
        
        with open(ruleset_path, 'rb') as f:
            ruleset_bytes = f.read()
            actual_hash = hashlib.sha256(ruleset_bytes).hexdigest()
        
        if actual_hash != expected_ruleset_hash:
            raise GovernanceError(f"Ruleset Hash Mismatch! Expected: {expected_ruleset_hash}, Got: {actual_hash}")

        rules = json.loads(ruleset_bytes)
        
        # 2. Scan Targets
        violations = []
        for target in scan_targets:
            if os.path.isfile(target):
                violations.extend(self._scan_file(target, rules))
            elif os.path.isdir(target):
                violations.extend(self._scan_directory(target, rules))
            else:
                self.logger.warning(f"Scan target not found: {target}")

        if violations:
            report = "\n".join(violations)
            raise GovernanceError(f"GOVERNANCE LEAK DETECTED:\n{report}")

        self.logger.info("Governance Leak Scan Passed.")

    def _scan_directory(self, directory: str, rules: List[Dict]) -> List[str]:
        violations = []
        for root, _, files in os.walk(directory):
            for file in files:
                path = os.path.join(root, file)
                violations.extend(self._scan_file(path, rules))
        return violations

    def _scan_file(self, file_path: str, rules: List[Dict]) -> List[str]:
        violations = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                for rule in rules:
                    pattern = rule.get('pattern')
                    description = rule.get('description')
                    if pattern and pattern in content:
                        violations.append(f"File: {file_path} | Violation: {description}")
        except Exception as e:
            self.logger.error(f"Error scanning file {file_path}: {e}")
            # Depending on strictness, maybe raise error?
            # "Any ambiguous condition MUST route to ERROR"
            raise GovernanceError(f"Failed to scan file {file_path}: {e}")
            
        return violations
