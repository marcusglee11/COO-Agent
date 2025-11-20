import re
from typing import Any, Dict, Union

import structlog

# Regex patterns for common secrets
# We look for "key", "token", "password", "secret" followed by some assignment and a value
# This is a heuristic.
SECRET_PATTERNS = [
    # Pattern 1: Key-Value pairs
    # We want to replace the VALUE part.
    # Regex: (key...separator)(value)
    re.compile(r"((?:api[_-]?key|access[_-]?token|secret|password|passwd)[\"']?\s*[:=]\s*[\"']?)([a-zA-Z0-9_\-\.]{8,})", re.IGNORECASE),
]

SK_PATTERN = re.compile(r"sk-[a-zA-Z0-9]{20,}")

def scrub_secrets(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Structlog processor to redact secrets from the event dictionary.
    Recursively traverses dictionaries and lists.
    """
    def _redact(value: Any) -> Any:
        if isinstance(value, str):
            # Check for patterns
            for pattern in SECRET_PATTERNS:
                if pattern.search(value):
                    # If the whole string looks like a key (e.g. sk-...), redact it
                    if pattern.match(value):
                        return "***REDACTED***"
                    # Otherwise, replace the match within the string
                    return pattern.sub(r"\1=***REDACTED***", value)
            return value
        elif isinstance(value, dict):
            return {k: _redact(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [_redact(item) for item in value]
        return value

    # Redact specific keys directly
    sensitive_keys = {"api_key", "password", "secret", "token", "authorization"}

    def _redact(value: Any, key: str = None) -> Any:
        # Check key first if provided
        if key and key.lower() in sensitive_keys:
            return "***REDACTED***"

        if isinstance(value, str):
            # 1. Redact standalone keys (sk-...)
            # We use sub to replace all occurrences
            value = SK_PATTERN.sub("***REDACTED***", value)
            
            # 2. Redact key-value pairs
            for pattern in SECRET_PATTERNS:
                # Replace group 2 with REDACTED, keeping group 1
                # The pattern is (key...separator)(value)
                # So we replace with \1***REDACTED***
                value = pattern.sub(r"\1***REDACTED***", value)
            return value
            
        elif isinstance(value, dict):
            return {k: _redact(v, k) for k, v in value.items()}
        elif isinstance(value, list):
            return [_redact(item) for item in value]
        return value
    
    return {k: _redact(v, k) for k, v in event_dict.items()}
