from enum import Enum, auto
from typing import Optional, List, Dict, Any
import os
import json
from ..util.questions import raise_question, QuestionType

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
        
        # Attempt to load state from disk - REMOVED (A.3)
        # self.load_state()

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
        # Legacy fsm_state.json persistence is removed entirely. (A.3)
        # Checkpoints are now explicit via checkpoint_state().

    def _force_error(self, reason: str) -> None:
        """
        Forces the FSM into the ERROR state and raises a GovernanceError.
        Used for any ambiguous or invalid condition.
        """
        self.__current_state = RuntimeState.ERROR
        self._history.append(RuntimeState.ERROR)
        raise_question(QuestionType.FSM_STATE_ERROR, f"RUNTIME HALT: {reason}. Please raise a QUESTION to the CEO.")

    def assert_state(self, expected_state: RuntimeState) -> None:
        """
        Verifies that the FSM is in the expected state.
        """
        if self.__current_state != expected_state:
            self._force_error(f"State assertion failed. Expected {expected_state}, got {self.__current_state}")

    def checkpoint_state(self, checkpoint_name: str, amu0_path: str) -> None:
        """
        Creates a signed checkpoint of the FSM state (A.3).
        Allowed only at constitutional boundaries:
        - After CAPTURE_AMU0
        - After GATES
        - Before CEO_FINAL_REVIEW (which is effectively after GATES transition)
        """
        allowed_states = [
            RuntimeState.CAPTURE_AMU0,
            RuntimeState.GATES,
            RuntimeState.CEO_FINAL_REVIEW
        ]
        
        if self.__current_state not in allowed_states:
             raise_question(QuestionType.FSM_STATE_ERROR, f"Checkpointing not allowed in state {self.__current_state}")

        # Get Pinned Time (A.3)
        context_path = os.path.join(amu0_path, "pinned_context.json")
        if not os.path.exists(context_path):
            raise_question(QuestionType.AMU0_INTEGRITY, "pinned_context.json missing. Cannot checkpoint with pinned time.")
            
        with open(context_path, "r") as f:
            context = json.load(f)
        
        if "mock_time" not in context:
            raise_question(QuestionType.AMU0_INTEGRITY, "mock_time missing in pinned_context.json")
            
        timestamp = context["mock_time"]

        data = {
            "checkpoint_name": checkpoint_name,
            "current_state": self.__current_state.name,
            "history": [s.name for s in self._history],
            "timestamp": timestamp
        }
        
        payload_bytes = json.dumps(data, sort_keys=True).encode("utf-8")
        
        # R6.4 G1: Sign using unified Signature protocol
        # R6.5 G2: Sign using unified Signature protocol (memory keys)
        from ..util.crypto import Signature
        try:
            signature = Signature.sign_data(payload_bytes)
        except Exception as e:
            raise_question(QuestionType.KEY_INTEGRITY, f"Signing failed: {e}")
        
        # Write
        filename = f"fsm_checkpoint_{checkpoint_name}.json"
        with open(filename, "w") as f:
            json.dump(data, f, sort_keys=True)
            
        with open(f"{filename}.sig", "wb") as f:
            f.write(signature)

    def load_checkpoint(self, checkpoint_name: str) -> None:
        """
        Loads a signed FSM checkpoint.
        """
        filename = f"fsm_checkpoint_{checkpoint_name}.json"
        sig_filename = f"{filename}.sig"
        
        if not os.path.exists(filename) or not os.path.exists(sig_filename):
            raise_question(QuestionType.FSM_STATE_ERROR, f"Checkpoint {checkpoint_name} missing.")
            
        # R6.4 G1: Verify using unified Signature protocol
        # R6.5 G2: Verify using unified Signature protocol (memory keys)
        from ..util.crypto import Signature
        
        # Read payload bytes for verification (was missing in original code snippet logic)
        with open(filename, "rb") as f:
            payload_bytes = f.read()
        with open(sig_filename, "rb") as f:
            signature = f.read()

        if not Signature.verify_data(payload_bytes, signature):
            raise_question(QuestionType.KEY_INTEGRITY, f"FSM Checkpoint {checkpoint_name} Signature Invalid!")
            
        # Restore State
        with open(filename, "r") as f:
            data = json.load(f)
        self.__current_state = RuntimeState[data["current_state"]]
        self._history = [RuntimeState[s] for s in data["history"]]
        
        # Validate History (A.3)
        # Check if the history is a valid path in the transition graph

