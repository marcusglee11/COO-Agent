import sys
import os
import json

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from coo_runtime.runtime.state_machine import RuntimeFSM, RuntimeState

def main():
    if len(sys.argv) != 2:
        print("Usage: python set_fsm_state.py <STATE_NAME>")
        sys.exit(1)
        
    state_name = sys.argv[1]
    try:
        target_state = RuntimeState[state_name]
    except KeyError:
        print(f"Invalid state: {state_name}")
        sys.exit(1)
        
    fsm = RuntimeFSM()
    # Force state
    fsm._RuntimeFSM__current_state = target_state # Access private member
    fsm._history.append(target_state)
    fsm.save_state()
    
    print(f"FSM State forced to: {target_state.name}")

if __name__ == "__main__":
    main()
