import sys
import os
import argparse
import logging
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from coo_runtime.runtime.state_machine import RuntimeFSM
from coo_runtime.runtime.governance_leak_scanner import GovernanceLeakScanner

def main():
    parser = argparse.ArgumentParser(description="Run Governance Leak Scanner")
    parser.add_argument("--ruleset", required=True, help="Path to ruleset json")
    parser.add_argument("--hash", required=True, help="Expected SHA256 of ruleset")
    parser.add_argument("--targets", nargs="+", required=True, help="List of files/dirs to scan")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    
    fsm = RuntimeFSM()
    scanner = GovernanceLeakScanner(fsm)
    
    scanner.scan(args.ruleset, args.hash, args.targets)

if __name__ == "__main__":
    main()
