"""
Pinned Context utilities for COO Runtime R6.3.
Handles hardware capture, verification, and subprocess environment construction.
"""
import os
import sys
import json
import platform
from typing import Dict, Any, Optional
from ..runtime.state_machine import GovernanceError
from ..util.questions import raise_question, QuestionType
from ..util.subprocess import run_pinned_subprocess

# ============================================================================
# B1: Real Hardware Capture (No Placeholders) - R6.3
# ============================================================================

def capture_hardware_context() -> Dict[str, str]:
    """
    Capture hardware context with fail-closed behavior.
    
    R6.4 D2: Must capture real kernel_version (fail-closed if missing).
    Missing microcode uses deterministic sentinel "MICROCODE_UNKNOWN" (NOT a failure).
    
    Returns:
        Dict with kernel_version and cpu_microcode
        
    Raises:
        GovernanceError: If kernel_version cannot be captured
    """
    # Kernel version using platform.release() - FAIL-CLOSED if missing
    kernel_version = platform.release()
    if not kernel_version:
        raise GovernanceError("Cannot capture kernel version")
    
    # CPU microcode from /proc/cpuinfo
    # R6.4 D2: Missing microcode uses sentinel, NOT a failure
    microcode_values = []
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('microcode'):
                    _, val = line.split(':', 1)
                    val = val.strip()
                    if val:
                        microcode_values.append(val)
    except Exception:
        # R6.4 D2: Cannot read /proc/cpuinfo → use sentinel
        pass
    
    # R6.4 D2: If no microcode values found, use deterministic sentinel
    if not microcode_values:
        cpu_microcode = "MICROCODE_UNKNOWN"
    else:
        # Deterministic representation - vendor-agnostic
        cpu_microcode = "|".join(sorted(set(microcode_values)))
    
    return {
        "kernel_version": kernel_version,
        "cpu_microcode": cpu_microcode
    }

# ============================================================================
# B4: Time Pinning Verification - R6.3
# ============================================================================

TIME_PIN_TOLERANCE_SECONDS = 1.1  # R6.3 B4: 1.1s to account for subprocess overhead

def _verify_time_pinning(amu0_path: str, expected_time: str) -> None:
    """
    Verify time pinning by spawning subprocess.
    
    R6.3 B4: Spawn subprocess using pinned env, compare time.time() to pinned timestamp.
    Difference > 1.1s MUST raise GovernanceError.
    
    Args:
        amu0_path: Path to AMU0 directory (for pinned context)
        expected_time: Expected timestamp (ISO format)
        
    Raises:
        GovernanceError: If time pinning verification fails
    """
    from datetime import datetime
    
    # Convert expected_time to timestamp
    try:
        expected_ts = datetime.fromisoformat(expected_time.replace('Z', '+00:00')).timestamp()
    except Exception as e:
        raise_question(QuestionType.ENVIRONMENT_PINNING, f"Cannot parse expected time '{expected_time}': {e}")
    
    # Spawn subprocess with pinned environment
    # R6.5 F2: Use run_pinned_subprocess (no direct subprocess calls)
    try:
        result = run_pinned_subprocess(
            [sys.executable, '-c', 'import time; print(time.time())'],
            amu0_path,
            capture_output=True,
            text=True,
            check=True
        )
        actual_ts = float(result.stdout.strip())
    except Exception as e:
        raise_question(QuestionType.ENVIRONMENT_PINNING, f"Time pinning subprocess failed: {e}")
    
    # Check difference
    diff = abs(actual_ts - expected_ts)
    
    if diff > TIME_PIN_TOLERANCE_SECONDS:
        raise_question(
            QuestionType.ENVIRONMENT_PINNING,
            f"Time pinning verification failed. "
            f"Expected: {expected_time} ({expected_ts}), "
            f"Actual: {actual_ts}, "
            f"Difference: {diff}s > {TIME_PIN_TOLERANCE_SECONDS}s"
        )

# ============================================================================
# Hardware Verification
# ============================================================================

def _verify_hardware_context(pinned_context: Dict[str, Any]) -> None:
    """
    Verify current hardware matches pinned context.
    
    Args:
        pinned_context: Pinned context from AMU0
        
    Raises:
        GovernanceError: If hardware mismatch detected
    """
    # Capture current hardware
    current_hw = capture_hardware_context()
    
    # Verify kernel
    pinned_kernel = pinned_context.get('kernel_version')
    if not pinned_kernel or pinned_kernel == "UNKNOWN":
        raise_question(QuestionType.HARDWARE_PINNING, "Pinned kernel version is UNKNOWN or missing")
    
    if current_hw['kernel_version'] != pinned_kernel:
        raise_question(
            QuestionType.HARDWARE_PINNING,
            f"Kernel version mismatch: "
            f"Current={current_hw['kernel_version']}, "
            f"Pinned={pinned_kernel}"
        )
    
    # R6.4 D2: Verify microcode (sentinel-aware)
    pinned_microcode = pinned_context.get('cpu_microcode')
    if not pinned_microcode:
        raise_question(QuestionType.HARDWARE_PINNING, "Pinned CPU microcode is missing")
    
    # R6.4 D2: Both MICROCODE_UNKNOWN and actual values are valid
    # They must match exactly (deterministic)
    if current_hw['cpu_microcode'] != pinned_microcode:
        raise_question(
            QuestionType.HARDWARE_PINNING,
            f"CPU microcode mismatch: "
            f"Current={current_hw['cpu_microcode']}, "
            f"Pinned={pinned_microcode}"
        )

def get_pinned_time(amu0_path: str):
    """
    Get the pinned time from the AMU0 context.
    
    Args:
        amu0_path: Path to the AMU0 directory.
        
    Returns:
        datetime: The pinned mock time.
        
    Raises:
        GovernanceError: If pinned context is missing or invalid.
    """
    from datetime import datetime
    context_path = os.path.join(amu0_path, 'pinned_context.json')
    if not os.path.exists(context_path):
        from ..runtime.state_machine import GovernanceError
        raise GovernanceError(f"Pinned context not found at {context_path}")
        
    try:
        with open(context_path, 'r') as f:
            context = json.load(f)
    except json.JSONDecodeError as e:
        from ..runtime.state_machine import GovernanceError
        raise GovernanceError(f"Pinned context corrupted: {e}")
        
    mock_time_str = context.get('mock_time')
    if not mock_time_str:
        from ..runtime.state_machine import GovernanceError
        raise GovernanceError("mock_time missing in pinned_context.json")
        
    # Parse ISO format (assuming it ends in Z)
    # R6.3 uses ISO8601 strings
    if mock_time_str.endswith('Z'):
        mock_time_str = mock_time_str[:-1]
    return datetime.fromisoformat(mock_time_str)

# R6.4 E2: enforce_pinned_context_or_fail() has been REMOVED per constitutional mandate.
# All callsites must use initialize_runtime() from coo_runtime.runtime.init instead.
