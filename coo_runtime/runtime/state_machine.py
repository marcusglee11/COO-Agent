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
        raise GovernanceError(f"RUNTIME HALT: {reason}. Please raise a QUESTION to the CEO.")

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
             raise GovernanceError(f"Checkpointing not allowed in state {self.__current_state}")

        # Get Pinned Time (A.3)
        context_path = os.path.join(amu0_path, "pinned_context.json")
        if not os.path.exists(context_path):
            raise GovernanceError("pinned_context.json missing. Cannot checkpoint with pinned time.")
            
        with open(context_path, "r") as f:
            context = json.load(f)
        
        if "mock_time" not in context:
            raise GovernanceError("mock_time missing in pinned_context.json")
            
        timestamp = context["mock_time"]

        data = {
            "checkpoint_name": checkpoint_name,
            "current_state": self.__current_state.name,
            "history": [s.name for s in self._history],
            "timestamp": timestamp
        }
        
        payload_bytes = json.dumps(data, sort_keys=True).encode("utf-8")
        
        # Sign
        private_key_path = os.path.join(os.path.dirname(__file__), "../../coo_runtime/manifests/ceo_private_key.pem")
        if not os.path.exists(private_key_path):
             raise GovernanceError("CEO Private Key missing. Cannot sign FSM checkpoint.")
             
        from ..util.crypto import sign_bytes # Import here to avoid circular dependency if any
        signature = sign_bytes(private_key_path, payload_bytes)
        
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
            raise GovernanceError(f"Checkpoint {checkpoint_name} missing.")
            
        # Verify Signature
        public_key_path = os.path.join(os.path.dirname(__file__), "../../coo_runtime/manifests/ceo_public_key.pem")
        if not os.path.exists(public_key_path):
             raise GovernanceError("CEO Public Key missing. Cannot verify FSM checkpoint.")
             
        with open(filename, "r") as f:
            data = json.load(f)
            
        with open(sig_filename, "rb") as f:
            signature = f.read()
            
        payload_bytes = json.dumps(data, sort_keys=True).encode("utf-8")
        
        from ..util.crypto import verify_signature
        if not verify_signature(public_key_path, payload_bytes, signature):
            raise GovernanceError(f"FSM Checkpoint {checkpoint_name} Signature Invalid!")
            
        # Restore State
        self.__current_state = RuntimeState[data["current_state"]]
        self._history = [RuntimeState[s] for s in data["history"]]
        
        # Validate History (A.3)
        # Check if the history is a valid path in the transition graph
        for i in range(len(self._history) - 1):
            curr = self._history[i]
            next_s = self._history[i+1]
            if next_s not in self._transitions[curr] and next_s != RuntimeState.ERROR:
                 # ERROR is allowed jump from anywhere usually, but let's be strict
                 # The transitions dict defines valid next states.
                 raise GovernanceError(f"Invalid transition in checkpoint history: {curr} -> {next_s}")
