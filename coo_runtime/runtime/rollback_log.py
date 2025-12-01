import os
import json
import hashlib
import logging
from typing import Dict, Any, List
from ..runtime.state_machine import GovernanceError
from ..util.questions import raise_question, QuestionType
from ..util.crypto import Signature

MAX_ROLLBACK_ENTRIES = 1000 # R6.5 C2: Bounded log

class RollbackLog:
    """
    Manages the append-only, hash-chained, signed rollback log.
    Enforces R6 A.2:
    - Hash chain (previous_hash, entry_hash)
    - Pinned time (no time.time())
    - Full re-signing on append
    """

    def __init__(self):
        self.logger = logging.getLogger("RollbackLog")

    def append_entry(self, amu0_path: str, payload: Dict[str, Any]) -> None:
        """
        Appends a new entry to the rollback log.
        """
        log_path = os.path.join(amu0_path, "rollback_log.jsonl")
        sig_path = os.path.join(amu0_path, "rollback_log.sig")
        
        # 1. Load existing log to get previous hash
        entries = self._load_and_verify_log(amu0_path)
        
        # R6.5 C2: Fail-closed on full
        if len(entries) >= MAX_ROLLBACK_ENTRIES:
             raise_question(QuestionType.ROLLBACK_INTEGRITY, f"Rollback log full (max {MAX_ROLLBACK_ENTRIES}). Fail-closed.")
        
        if entries:
            last_entry = entries[-1]
            previous_hash = last_entry["entry_hash"]
            sequence_number = last_entry["sequence_number"] + 1
        else:
            previous_hash = "0" * 64 # Genesis hash
            sequence_number = 1

        # 2. Get Pinned Time (R6 A.2)
        # Explicitly: No use of time.time() in rollback logging.
        pinned_time = self._get_pinned_time(amu0_path)

        # 3. Construct Entry
        entry = {
            "sequence_number": sequence_number,
            "timestamp": pinned_time,
            "previous_hash": previous_hash,
            "payload": payload
        }
        
        # 4. Calculate Entry Hash
        # Hash of canonical JSON of the entry fields (excluding entry_hash itself)
        entry_bytes = json.dumps(entry, sort_keys=True).encode("utf-8")
        entry_hash = hashlib.sha256(entry_bytes).hexdigest()
        entry["entry_hash"] = entry_hash
        
        entries.append(entry)
        
        # 5. Write Log Atomically (R6.3 A6)
        # Write to .tmp files first, then atomic rename
        log_tmp = log_path + '.tmp'
        sig_tmp = sig_path + '.tmp'
        
        # Write log to temporary file
        with open(log_tmp, "w") as f:
            for e in entries:
                f.write(json.dumps(e, sort_keys=True) + "\n")
                
        # 6. Sign Full Log (R6.3 A6)
        # Sign the temporary log file
        with open(log_tmp, "rb") as f:
            log_bytes = f.read()
            
        signature = Signature.sign_data(log_bytes)
        
        # Write signature to temporary file
        with open(sig_tmp, "wb") as f:
            f.write(signature)
        
        # 7. Atomic Rename (R6.3 A6)
        # Both files written successfully, now rename atomically
        os.rename(log_tmp, log_path)
        os.rename(sig_tmp, sig_path)
            
        self.logger.info(f"Appended rollback entry #{sequence_number}. Log re-signed atomically.")

    def get_rollback_count(self, amu0_path: str) -> int:
        """
        Returns the number of rollback entries in the log.
        Verifies integrity before counting.
        """
        entries = self._load_and_verify_log(amu0_path)
        return len(entries)

    def _load_and_verify_log(self, amu0_path: str) -> List[Dict[str, Any]]:
        """
        Loads the log, verifies the signature, and validates the hash chain.
        """
        log_path = os.path.join(amu0_path, "rollback_log.jsonl")
        sig_path = os.path.join(amu0_path, "rollback_log.sig")
        
        if not os.path.exists(log_path):
            # If log doesn't exist, it might be fresh AMU0 capture (empty log created in capture)
            # But capture creates empty file. So it should exist.
            raise GovernanceError("Rollback log missing.")
            
        # 1. Verify Signature
        if os.path.exists(sig_path):
            with open(log_path, "rb") as f:
                log_bytes = f.read()
            with open(sig_path, "rb") as f:
                signature = f.read()
                
            if not Signature.verify_data(log_bytes, signature):
                raise_question(QuestionType.ROLLBACK_INTEGRITY, "Rollback Log Signature Invalid!")
        else:
            # If no signature, log must be empty (fresh capture)
            if os.path.getsize(log_path) > 0:
                 raise_question(QuestionType.ROLLBACK_INTEGRITY, "Rollback log has content but no signature.")
        
        # 2. Parse Entries
        entries = []
        with open(log_path, "r") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
                    
        # 3. Verify Hash Chain
        expected_prev_hash = "0" * 64
        for i, entry in enumerate(entries):
            # Check Sequence
            if entry["sequence_number"] != i + 1:
                raise GovernanceError(f"Rollback Log Sequence Error at #{i+1}")
                
            # Check Previous Hash
            if entry["previous_hash"] != expected_prev_hash:
                raise_question(QuestionType.ROLLBACK_INTEGRITY, f"Rollback Log Hash Chain Broken at #{i+1}")
                
            # Re-calculate Entry Hash
            stored_hash = entry["entry_hash"]
            # Create copy without entry_hash for hashing
            entry_for_hash = entry.copy()
            del entry_for_hash["entry_hash"]
            
            entry_bytes = json.dumps(entry_for_hash, sort_keys=True).encode("utf-8")
            calculated_hash = hashlib.sha256(entry_bytes).hexdigest()
            
            if calculated_hash != stored_hash:
                 raise_question(QuestionType.ROLLBACK_INTEGRITY, f"Rollback Log Entry Hash Mismatch at #{i+1}")
                 
            expected_prev_hash = stored_hash
            
        return entries

    def _get_pinned_time(self, amu0_path: str) -> str:
        """
        Retrieves pinned time from pinned_context.json.
        """
        context_path = os.path.join(amu0_path, "pinned_context.json")
        if not os.path.exists(context_path):
            raise GovernanceError("pinned_context.json missing in AMU0.")
            
        with open(context_path, "r") as f:
            context = json.load(f)
            
        if "mock_time" not in context:
            raise GovernanceError("mock_time missing in pinned_context.json")
            
        return context["mock_time"]
