import sys
import os
import argparse
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from coo_runtime.runtime.state_machine import RuntimeFSM
from coo_runtime.runtime.lint_engine import LintEngine

def main():
    parser = argparse.ArgumentParser(description="Run Constitutional Lint")
    parser.add_argument("--target", required=True, help="Target directory to lint")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    
    fsm = RuntimeFSM()
    linter = LintEngine(fsm)
    
    linter.run_lint(args.target)

if __name__ == "__main__":
    main()
