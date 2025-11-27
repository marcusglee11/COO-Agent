import logging
import json
import hashlib
import time
import os
from typing import Dict, Any

class DeterministicLogger:
    """
    Produces deterministic logs for the COO Runtime.
    Enforces Section 15 of COO Runtime Spec v1.0.
    - Labeled with sequence_id
    - Includes SHA256 of config/inputs
    - Includes COO Runtime version
    - Includes Timestamp (mocked if frozen)
    """

    def __init__(self, log_dir: str, version: str = "1.0.0"):
        self.log_dir = log_dir
        self.version = version
        self.sequence_id = 0
        self._ensure_log_dir()
        
        # Configure Python logging to output to file
        self.logger = logging.getLogger("COORuntime")
        self.logger.setLevel(logging.INFO)
        
        handler = logging.FileHandler(os.path.join(log_dir, "runtime.log"))
        formatter = logging.Formatter('%(message)s') # Raw message, we format JSON manually
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _ensure_log_dir(self):
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def log_event(self, event_type: str, details: Dict[str, Any], context_hash: str = "") -> None:
        """
        Logs a deterministic event.
        """
        self.sequence_id += 1
        
        log_entry = {
            "sequence_id": self.sequence_id,
            "timestamp": self._get_timestamp(),
            "version": self.version,
            "event_type": event_type,
            "context_hash": context_hash, # SHA256 of inputs/config
            "details": details
        }
        
        # Deterministic JSON serialization (sorted keys)
        log_str = json.dumps(log_entry, sort_keys=True)
        self.logger.info(log_str)

    def _get_timestamp(self) -> str:
        """
        Returns a deterministic timestamp.
        If COO_MOCK_TIME is set, uses that.
        Otherwise, if in STRICT mode, raises error (or uses counter).
        """
        mock_time = os.environ.get("COO_MOCK_TIME")
        if mock_time:
            return mock_time
            
        # If no mock time, check strict mode
        strict_mode = os.environ.get("COO_STRICT_MODE", "0") == "1"
        if strict_mode:
            # In strict mode, we cannot use wall clock.
            # We use the sequence_id as a logical clock.
            return f"LOGICAL_CLOCK_{self.sequence_id}"
            
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def log_fsm_transition(self, from_state: str, to_state: str):
        self.log_event("FSM_TRANSITION", {"from": from_state, "to": to_state})

    def log_gate_result(self, gate_name: str, status: str, reason: str = ""):
        self.log_event("GATE_RESULT", {"gate": gate_name, "status": status, "reason": reason})

    def log_db_transaction(self, tx_id: str, operation: str):
        self.log_event("DB_TRANSACTION", {"tx_id": tx_id, "operation": operation})
