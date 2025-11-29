import json
import os
import hashlib
from typing import Any, Dict, Optional

class ExternalTraceReplayer:
    """
    Replays external calls from a deterministic trace file.
    Used in Deep Mode Replay.
    """
    def __init__(self, trace_path: str):
        self.trace_path = trace_path
        self.trace_map: Dict[str, Any] = {}
        self._load_trace()

    def _load_trace(self) -> None:
        if not os.path.exists(self.trace_path):
            raise RuntimeError(f"Deep Mode: Trace file missing at {self.trace_path}")
            
        with open(self.trace_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    # We map prompt_hash to response
                    # R6 says "Deep Mode replayer must use only this trace".
                    # We assume prompt_hash is unique enough.
                    self.trace_map[entry["prompt_hash"]] = entry["response"]

    def replay_call(self, prompt: str) -> str:
        """
        Returns the recorded response for the given prompt.
        Fails if not found.
        """
        prompt_hash = hashlib.sha256(str(prompt).encode("utf-8")).hexdigest()
        
        if prompt_hash in self.trace_map:
            return self.trace_map[prompt_hash]
        else:
            # R6 A.7: "no live calls permitted".
            # If not in trace, it's a deviation.
            raise RuntimeError(f"Deep Mode: Prompt deviation detected. Hash {prompt_hash} not found in trace.")
