from enum import Enum, auto
from typing import Optional, List, Dict, Any

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
    REPLAY = auto()
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
            RuntimeState.GATES: [RuntimeState.REPLAY, RuntimeState.ERROR, RuntimeState.CAPTURE_AMU0],
            RuntimeState.REPLAY: [RuntimeState.CEO_FINAL_REVIEW, RuntimeState.ERROR, RuntimeState.CAPTURE_AMU0],
            RuntimeState.CEO_FINAL_REVIEW: [RuntimeState.COMPLETE, RuntimeState.ERROR],
            RuntimeState.COMPLETE: [], # Terminal state
            RuntimeState.ERROR: [],    # Terminal state (requires manual intervention/restart)
        }

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

        self.__current_state = next_state
        self._history.append(next_state)

    def _force_error(self, reason: str) -> None:
        """
        Forces the FSM into the ERROR state and raises a GovernanceError.
        Used for any ambiguous or invalid condition.
        """
        self.__current_state = RuntimeState.ERROR
        self._history.append(RuntimeState.ERROR)
        raise GovernanceError(f"RUNTIME HALT: {reason}. Please raise a QUESTION to the CEO.")

    def assert_state(self, expected_state: RuntimeState) -> None:
        """
        Verifies that the FSM is in the expected state.
        """
        if self.__current_state != expected_state:
            self._force_error(f"State assertion failed. Expected {expected_state}, got {self.__current_state}")
