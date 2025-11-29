import json
import os
import hashlib
import time
from typing import Any, Dict, List

class ExternalTraceRecorder:
    """
    Records external calls (e.g. LLM, API) to a deterministic trace file.
    Used to generate external_trace.jsonl for AMU0.
    """
    def __init__(self, trace_path: str):
        self.trace_path = trace_path
        self.entries: List[Dict[str, Any]] = []

    def record_call(self, prompt: str, response: str, metadata: Dict[str, Any] = None) -> None:
        """
        Records a call and its response.
        """
        # Calculate hash of the prompt/input to serve as key
        prompt_hash = hashlib.sha256(str(prompt).encode("utf-8")).hexdigest()
        
        entry = {
            "prompt_hash": prompt_hash,
            "prompt": prompt, # Optional: store full prompt for debugging? R6 doesn't forbid.
            "response": response,
            "timestamp": time.time(), # Recording time (not pinned)
            "metadata": metadata or {}
        }
        
        self.entries.append(entry)
        self._flush()

    def _flush(self) -> None:
        """
        Writes entries to disk.
        """
        # We write as JSONL or JSON?
        # R6 says "external_trace.jsonl".
        # But `replay_harness` was reading JSON.
        # Let's support JSONL as per requirement.
        
        with open(self.trace_path, "w", encoding="utf-8") as f:
            for entry in self.entries:
                f.write(json.dumps(entry, sort_keys=True) + "\n")
