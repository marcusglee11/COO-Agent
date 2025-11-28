from enum import Enum, auto
from typing import Optional, List, Dict, Any
import os
import json

class RuntimeState(Enum):
    """
    Canonical FSM States for COO Runtime v1.0.
    Strictly defined in COO_RUNTIME_SPECIFICATION_v1.0.md.
    """
    INIT = auto()
    AMENDMENT_PREP = auto()
    AMENDMENT_EXEC = auto()
    AMENDMENT_VERIFY = auto()
    CEO_REVIEW = auto()
    FREEZE_PREP = auto()
    FREEZE_ACTIVATED = auto()
    CAPTURE_AMU0 = auto()
    MIGRATION_SEQUENCE = auto()
    GATES = auto()
    # REPLAY state removed (B6) - Gate F runs in GATES, then transitions to CEO_FINAL_REVIEW
    CEO_FINAL_REVIEW = auto()
    COMPLETE = auto()
    ERROR = auto()

class GovernanceError(Exception):
    """Raised when a governance invariant is violated."""
    pass

class RuntimeFSM:
    """
    Deterministic Finite State Machine for the COO Runtime.
    Enforces strict linear progression and halts on ambiguity.
    """

    def __init__(self):
        self.__current_state = RuntimeState.INIT
        self._history: List[RuntimeState] = [RuntimeState.INIT]
        
        # Define allowed transitions (Strict Linear Progression)
        self._transitions: Dict[RuntimeState, List[RuntimeState]] = {
            RuntimeState.INIT: [RuntimeState.AMENDMENT_PREP, RuntimeState.ERROR],
            RuntimeState.AMENDMENT_PREP: [RuntimeState.AMENDMENT_EXEC, RuntimeState.ERROR],
            RuntimeState.AMENDMENT_EXEC: [RuntimeState.AMENDMENT_VERIFY, RuntimeState.ERROR],
            RuntimeState.AMENDMENT_VERIFY: [RuntimeState.CEO_REVIEW, RuntimeState.ERROR],
            RuntimeState.CEO_REVIEW: [RuntimeState.FREEZE_PREP, RuntimeState.ERROR],
            RuntimeState.FREEZE_PREP: [RuntimeState.FREEZE_ACTIVATED, RuntimeState.ERROR],
            RuntimeState.FREEZE_ACTIVATED: [RuntimeState.CAPTURE_AMU0, RuntimeState.ERROR],
            RuntimeState.CAPTURE_AMU0: [RuntimeState.MIGRATION_SEQUENCE, RuntimeState.ERROR],
            RuntimeState.MIGRATION_SEQUENCE: [RuntimeState.GATES, RuntimeState.ERROR, RuntimeState.CAPTURE_AMU0],
            RuntimeState.GATES: [RuntimeState.CEO_FINAL_REVIEW, RuntimeState.ERROR, RuntimeState.CAPTURE_AMU0],
            # RuntimeState.REPLAY removed
            RuntimeState.CEO_FINAL_REVIEW: [RuntimeState.COMPLETE, RuntimeState.ERROR],
            RuntimeState.COMPLETE: [], # Terminal state
            RuntimeState.ERROR: [],    # Terminal state (requires manual intervention/restart)
        }
        
        # Attempt to load state from disk
        self.load_state()

    @property
    def current_state(self) -> RuntimeState:
        return self.__current_state

    @property
    def history(self) -> List[RuntimeState]:
        return list(self._history)

    def transition_to(self, next_state: RuntimeState) -> None:
        """
        Executes a state transition.
        Raises GovernanceError if the transition is invalid.
        """
        if next_state not in self._transitions[self.__current_state]:
            # Invalid transition attempt -> Immediate Halt & Error
            self._force_error(f"Invalid transition attempted: {self.__current_state} -> {next_state}")
            return

        # Governance State Hardening (R3)
        strict_states = [
            RuntimeState.FREEZE_ACTIVATED,
            RuntimeState.CEO_REVIEW,
            RuntimeState.CEO_FINAL_REVIEW
        ]
        
        if next_state in strict_states:
            if os.environ.get("COO_STRICT_MODE", "0") != "1":
                self._force_error(f"Strict Mode Required for transition to {next_state}")
                return

        self.__current_state = next_state
        self._history.append(next_state)
        self.save_state()

    def _force_error(self, reason: str) -> None:
        """
        Forces the FSM into the ERROR state and raises a GovernanceError.
        Used for any ambiguous or invalid condition.
        """
        self.__current_state = RuntimeState.ERROR
        self._history.append(RuntimeState.ERROR)
        self.save_state()
        raise GovernanceError(f"RUNTIME HALT: {reason}. Please raise a QUESTION to the CEO.")

    def assert_state(self, expected_state: RuntimeState) -> None:
        """
        Verifies that the FSM is in the expected state.
        """
        if self.__current_state != expected_state:
            self._force_error(f"State assertion failed. Expected {expected_state}, got {self.__current_state}")

    def save_state(self, filepath: str = "fsm_state.json") -> None:
        """
        Persists the current state to disk.
        """
        data = {
            "current_state": self.__current_state.name,
            "history": [s.name for s in self._history]
        }
        with open(filepath, "w") as f:
            json.dump(data, f)

    def load_state(self, filepath: str = "fsm_state.json") -> None:
        """
        Loads state from disk.
        """
        if not os.path.exists(filepath):
            return
            
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                
            state_name = data.get("current_state")
            if state_name:
                self.__current_state = RuntimeState[state_name]
                
            history_names = data.get("history", [])
            self._history = [RuntimeState[s] for s in history_names]
            
        except Exception as e:
            # If state load fails, we default to INIT but log/warn?
            # For now, we just raise because corrupted state is fatal.
            raise GovernanceError(f"Failed to load FSM state: {e}")
