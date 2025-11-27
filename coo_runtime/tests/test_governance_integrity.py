import unittest
import os
import json
import hashlib
from coo_runtime.runtime.state_machine import RuntimeFSM
from coo_runtime.runtime.governance_leak_scanner import GovernanceLeakScanner
from coo_runtime.runtime.lint_engine import LintEngine

class TestGovernanceIntegrity(unittest.TestCase):
    def setUp(self):
        self.fsm = RuntimeFSM()
        self.scanner = GovernanceLeakScanner(self.fsm)
        self.linter = LintEngine(self.fsm)
        
        # Create mock ruleset
        self.ruleset = [{"pattern": "LEAK", "description": "Leak detected"}]
        self.ruleset_path = "mock_rules.json"
        with open(self.ruleset_path, "w") as f:
            json.dump(self.ruleset, f)
            
        with open(self.ruleset_path, "rb") as f:
            self.ruleset_hash = hashlib.sha256(f.read()).hexdigest()

    def tearDown(self):
        if os.path.exists(self.ruleset_path):
            os.remove(self.ruleset_path)
        if os.path.exists("leak_file.txt"):
            os.remove("leak_file.txt")

    def test_scanner_detects_leak(self):
        with open("leak_file.txt", "w") as f:
            f.write("This contains a LEAK.")
            
        with self.assertRaises(Exception) as cm:
            self.scanner.scan(self.ruleset_path, self.ruleset_hash, ["leak_file.txt"])
        
        self.assertIn("GOVERNANCE LEAK DETECTED", str(cm.exception))

    def test_linter_detects_random(self):
        with open("leak_file.txt", "w") as f: # reusing name but for lint
            f.write("import random")
            
        # Linter expects .py files
        os.rename("leak_file.txt", "leak_file.py")
        try:
            with self.assertRaises(Exception) as cm:
                self.linter.run_lint(".")
            self.assertIn("Determinism - Randomness", str(cm.exception))
        finally:
            if os.path.exists("leak_file.py"):
                os.remove("leak_file.py")

if __name__ == '__main__':
    unittest.main()
