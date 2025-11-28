import os
import json
import time
import logging
from typing import List, Dict, Any
from ..runtime.state_machine import GovernanceError
from ..util.crypto import sign_bytes, verify_signature

class RollbackLog:
    """
    Implements a signed, append-only rollback log.
    Replaces mutable rollback counters with a verifiable audit trail.
    """
    LOG_FILENAME = "rollback_log.jsonl"

    def __init__(self, private_key_path: str = None, public_key_path: str = None):
        self.logger = logging.getLogger("RollbackLog")
        self.private_key_path = private_key_path
        self.public_key_path = public_key_path

    def append_entry(self, amu0_path: str, payload: Dict[str, Any]) -> None:
        """
        Appends a signed entry to the rollback log.
        
        Args:
            amu0_path: Path to AMU0 directory
            payload: Data to log (reason, actor, etc.)
        """
        if not self.private_key_path or not os.path.exists(self.private_key_path):
            raise GovernanceError("Cannot sign rollback log: Private key missing.")

        log_path = os.path.join(amu0_path, self.LOG_FILENAME)
        
        # 1. Construct Entry
        entry = {
            "timestamp": time.time(), # Use normalized time in production? R6 says "timestamp (from pinned / normalized time)"
            # For now using time.time(), but should ideally come from context if pinned.
            # But rollback happens *outside* the mission execution context usually.
            "payload": payload
        }
        
        # 2. Serialize for Signing
        # Canonical JSON serialization for consistent signing
        entry_bytes = json.dumps(entry, sort_keys=True).encode("utf-8")
        
        # 3. Sign
        signature = sign_bytes(self.private_key_path, entry_bytes)
        
        # 4. Construct Log Line
        log_line = {
            "entry": entry,
            "signature": signature.hex()
        }
        
        # 5. Append to File
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_line) + "\n")
            
        self.logger.info(f"Appended rollback entry: {payload}")

    def load_log(self, amu0_path: str) -> List[Dict[str, Any]]:
        """
        Loads and verifies the rollback log.
        Returns a list of valid entries.
        Raises GovernanceError on tampering or verification failure.
        """
        if not self.public_key_path or not os.path.exists(self.public_key_path):
            raise GovernanceError("Cannot verify rollback log: Public key missing.")

        log_path = os.path.join(amu0_path, self.LOG_FILENAME)
        if not os.path.exists(log_path):
            return []

        entries = []
        last_timestamp = 0.0

        with open(log_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    data = json.loads(line)
                    entry = data["entry"]
                    signature_hex = data["signature"]
                    signature = bytes.fromhex(signature_hex)
                except (json.JSONDecodeError, KeyError, ValueError):
                    raise GovernanceError(f"Rollback Log Corrupted at line {line_num}")

                # 1. Verify Signature
                entry_bytes = json.dumps(entry, sort_keys=True).encode("utf-8")
                if not verify_signature(self.public_key_path, entry_bytes, signature):
                    raise GovernanceError(f"Rollback Log Signature Invalid at line {line_num}")

                # 2. Verify Monotonicity (Time)
                timestamp = entry.get("timestamp", 0.0)
                if timestamp < last_timestamp:
                    raise GovernanceError(f"Rollback Log Non-Monotonic at line {line_num}")
                last_timestamp = timestamp

                entries.append(entry)

        return entries

    def get_rollback_count(self, amu0_path: str) -> int:
        """
        Calculates the number of rollbacks from the log.
        """
        entries = self.load_log(amu0_path)
        # Count entries that represent a rollback action
        # Assuming all entries in this log are rollbacks for now.
        return len(entries)
