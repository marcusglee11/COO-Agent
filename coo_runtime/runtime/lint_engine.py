import os
import re
import logging
from typing import List, Dict
from .state_machine import RuntimeFSM, RuntimeState, GovernanceError

class LintEngine:
    """
    Enforces Constitutional Invariants from Alignment Layer v1.4.
    - Supremacy: No overrides of LifeOS/Alignment Layer.
    - Determinism: No non-deterministic calls (random, time, etc.) without wrappers.
    - No Governance Leakage: No governance logic in runtime.
    """

    def __init__(self, fsm: RuntimeFSM):
        self.fsm = fsm
        self.logger = logging.getLogger("LintEngine")
        
        # Constitutional Invariants (Regex-based for v1.0)
        self.invariants = [
            {
                "name": "Determinism - Randomness",
                "pattern": r"import random|from random import|random\.",
                "description": "Direct use of 'random' module prohibited. Use deterministic RNG wrapper.",
                "exclude": ["tests/"] # Exclude tests if they mock it, but runtime must be clean.
            },
            {
                "name": "Determinism - Time",
                "pattern": r"import time|from time import|time\.time\(\)|datetime\.now\(\)",
                "description": "Direct use of wall-clock time prohibited. Use deterministic time wrapper.",
                "exclude": ["tests/"]
            },
            {
                "name": "Supremacy - Override",
                "pattern": r"LifeOS override|Alignment Layer override|Ignore Spec",
                "description": "Attempt to override Supreme Specs detected.",
                "exclude": []
            },
            {
                "name": "Governance Leakage",
                "pattern": r"CEO signature|Governance vote|Approve amendment",
                "description": "Governance logic detected in non-governance module.",
                "exclude": ["coo_runtime/runtime/gates.py", "coo_runtime/runtime/freeze.py", "coo_runtime/runtime/rollback.py"] 
                # Allowed only where explicitly mandated by spec (e.g. signature verification)
            }
        ]

    def run_lint(self, target_root: str) -> None:
        """
        Scans the target directory for constitutional violations.
        Halts on any violation.
        """
        self.logger.info(f"Starting Constitutional Lint on {target_root}")
        
        violations = []
        for root, _, files in os.walk(target_root):
            for file in files:
                if not file.endswith(".py"):
                    continue
                    
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, target_root)
                
                violations.extend(self._lint_file(file_path, rel_path))

        if violations:
            report = "\n".join(violations)
            raise GovernanceError(f"CONSTITUTIONAL VIOLATION DETECTED:\n{report}")

        self.logger.info("Constitutional Lint Passed.")

    def _lint_file(self, file_path: str, rel_path: str) -> List[str]:
        violations = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            for rule in self.invariants:
                # Check exclusions
                is_excluded = any(ex in rel_path.replace("\\", "/") for ex in rule["exclude"])
                if is_excluded:
                    continue
                    
                if re.search(rule["pattern"], content):
                    violations.append(f"File: {rel_path} | Invariant: {rule['name']} | {rule['description']}")
                    
        except Exception as e:
            self.logger.error(f"Lint error on {file_path}: {e}")
            raise GovernanceError(f"Lint failed on {file_path}: {e}")
            
        return violations
