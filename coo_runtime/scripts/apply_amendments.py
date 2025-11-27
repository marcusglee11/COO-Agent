import sys
import os
import argparse
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from coo_runtime.runtime.state_machine import RuntimeFSM, RuntimeState
from coo_runtime.runtime.amendment_engine import AmendmentEngine

def main():
    parser = argparse.ArgumentParser(description="Apply Amendments")
    parser.add_argument("--protocol", required=True, help="Path to amendment_protocol_v1.0.md")
    parser.add_argument("--target", required=True, help="Target root directory")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    
    fsm = RuntimeFSM()
    engine = AmendmentEngine(fsm)
    
    # Force state
    fsm._current_state = RuntimeState.AMENDMENT_PREP
    fsm.transition_to(RuntimeState.AMENDMENT_EXEC)
    
    engine.apply_amendments(args.protocol, args.target)

if __name__ == "__main__":
    main()
