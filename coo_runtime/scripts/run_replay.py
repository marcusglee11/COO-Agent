import sys
import os
import argparse
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from coo_runtime.runtime.state_machine import RuntimeFSM, RuntimeState
from coo_runtime.runtime.replay import ReplayEngine

def main():
    parser = argparse.ArgumentParser(description="Run Deterministic Replay")
    parser.add_argument("--mission", required=True, help="Path to mission file")
    parser.add_argument("--amu0", required=True, help="Path to AMU0 directory")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    
    fsm = RuntimeFSM()
    replay = ReplayEngine(fsm)
    
    # Force state
    fsm._current_state = RuntimeState.GATES
    fsm.transition_to(RuntimeState.REPLAY)
    
    replay.execute_replay(args.mission, args.amu0)

if __name__ == "__main__":
    main()
