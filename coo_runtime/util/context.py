"""
Pinned Context utilities for COO Runtime R6.3.
Handles hardware capture, verification, and subprocess environment construction.
"""
import os
import sys
import json
import platform
import subprocess
from typing import Dict, Any
from ..runtime.state_machine import GovernanceError

# ============================================================================
# B1: Real Hardware Capture (No Placeholders) - R6.3
# ============================================================================

def capture_hardware_context() -> Dict[str, str]:
    """
    Capture hardware context with fail-closed behavior.
    
    R6.3 B1: Must capture real kernel_version and cpu_microcode.
    If either cannot be captured, raise GovernanceError and abort.
    
    Returns:
        Dict with kernel_version and cpu_microcode
        
    Raises:
        GovernanceError: If hardware cannot be captured
    """
    # Kernel version using platform.release()
    kernel_version = platform.release()
    if not kernel_version:
        raise GovernanceError("Cannot capture kernel version")
    
    # CPU microcode from /proc/cpuinfo - exact pattern from R6.3 guidance
    microcode_values = []
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('microcode'):
                    _, val = line.split(':', 1)
                    val = val.strip()
                    if val:
                        microcode_values.append(val)
    except Exception as e:
        raise GovernanceError(f"Cannot read /proc/cpuinfo: {e}")
    
    if not microcode_values:
        raise GovernanceError("No CPU microcode values found in /proc/cpuinfo")
    
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

def _verify_time_pinning(env: Dict[str, str], expected_time: str) -> None:
    """
    Verify time pinning by spawning subprocess.
    
    R6.3 B4: Spawn subprocess using pinned env, compare time.time() to pinned timestamp.
    Difference > 1.1s MUST raise GovernanceError.
    
    Args:
        env: Pinned environment dict
        expected_time: Expected timestamp (ISO format)
        
    Raises:
        GovernanceError: If time pinning verification fails
    """
    from datetime import datetime
    
    # Convert expected_time to timestamp
    try:
        expected_ts = datetime.fromisoformat(expected_time.replace('Z', '+00:00')).timestamp()
    except Exception as e:
        raise GovernanceError(f"Cannot parse expected time '{expected_time}': {e}")
    
    # Spawn subprocess with pinned environment
    try:
        result = subprocess.run(
            [sys.executable, '-c', 'import time; print(time.time())'],
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        actual_ts = float(result.stdout.strip())
    except Exception as e:
        raise GovernanceError(f"Time pinning subprocess failed: {e}")
    
    # Check difference
    diff = abs(actual_ts - expected_ts)
    
    if diff > TIME_PIN_TOLERANCE_SECONDS:
        raise GovernanceError(
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
        raise GovernanceError("Pinned kernel version is UNKNOWN or missing")
    
    if current_hw['kernel_version'] != pinned_kernel:
        raise GovernanceError(
            f"Kernel version mismatch: "
            f"Current={current_hw['kernel_version']}, "
            f"Pinned={pinned_kernel}"
        )
    
    # Verify microcode
    pinned_microcode = pinned_context.get('cpu_microcode')
    if not pinned_microcode or pinned_microcode == "UNKNOWN":
        raise GovernanceError("Pinned CPU microcode is UNKNOWN or missing")
    
    if current_hw['cpu_microcode'] != pinned_microcode:
        raise GovernanceError(
            f"CPU microcode mismatch: "
            f"Current={current_hw['cpu_microcode']}, "
            f"Pinned={pinned_microcode}"
        )

# ============================================================================
# Legacy Function (Deprecated)
# ============================================================================

def enforce_pinned_context_or_fail(amu0_path: str) -> Dict[str, str]:
    """
    DEPRECATED: Use initialize_runtime() and run_pinned_subprocess() instead.
    
    This function is kept for backward compatibility during R6.3 migration.
    """
    # Load context
    context_path = os.path.join(amu0_path, "pinned_context.json")
    if not os.path.exists(context_path):
        raise GovernanceError("Pinned context file missing from AMU0")
        
    try:
        with open(context_path, "r") as f:
            ctx = json.load(f)
    except json.JSONDecodeError:
        raise GovernanceError("Pinned context file corrupted")
    
    # Verify hardware
    _verify_hardware_context(ctx)
    
    # Build env
    pinned_env = {}
    for k, v in ctx.get("env_vars", {}).items():
        pinned_env[k] = str(v)
    
    # Mock time
    mock_time = ctx.get("mock_time")
    if mock_time:
        pinned_env["FAKETIME"] = mock_time
        pinned_env["LD_PRELOAD"] = "/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1"
    
    return pinned_env
