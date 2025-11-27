import sys
import os
import argparse
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from coo_runtime.runtime.state_machine import RuntimeFSM
from coo_runtime.runtime.rollback import RollbackEngine

def main():
    parser = argparse.ArgumentParser(description="Run Rollback")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    
    fsm = RuntimeFSM()
    rollback = RollbackEngine(fsm)
    
    rollback.execute_rollback()

if __name__ == "__main__":
    main()
