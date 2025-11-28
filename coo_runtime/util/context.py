import os
import sys
import json
import random
import platform
from typing import Dict, Any, Optional
from ..runtime.state_machine import GovernanceError

def enforce_pinned_context_or_fail(amu0_path: str) -> Dict[str, str]:
    """
    Enforce pinned context strictly. Fail if any mismatch occurs.
    Returns the pinned environment dictionary for use in subprocesses.
    Does NOT mutate the global os.environ (R6 B.2).
    
    Enforces:
    - Platform (Linux-only)
    - RNG seed
    - Environment variable allowlist (Fail-Closed)
    - Mock time (via FAKETIME)
    - Hardware context verification (Fail-Closed)
    
    Args:
        amu0_path: Path to AMU0 directory containing pinned_context.json
        
    Returns:
        Dict[str, str]: The constructed environment dictionary.
        
    Raises:
        GovernanceError: If context mismatch detected or files missing.
    """
    # 0. Platform Check (R6 B.2)
    if sys.platform != "linux":
        raise GovernanceError(f"Unsupported platform: {sys.platform}. COO Runtime R6 is Linux-only.")

    context_path = os.path.join(amu0_path, "pinned_context.json")
    if not os.path.exists(context_path):
        raise GovernanceError("Pinned context file missing from AMU0.")
        
    try:
        with open(context_path, "r") as f:
            ctx = json.load(f)
    except json.JSONDecodeError:
        raise GovernanceError("Pinned context file corrupted.")

    # 1. RNG Seed
    rng_seed = ctx.get("rng_seed")
    if rng_seed is None:
        raise GovernanceError("RNG seed missing from pinned context.")
    random.seed(rng_seed)

    # 2. ENV VARS (Fail-Closed)
    allowed_env_vars = ctx.get("env_vars", {})
    
    # Construct new env dict (Do not mutate os.environ)
    pinned_env = {}
    for k, v in allowed_env_vars.items():
        pinned_env[k] = str(v)
        
    # 3. Mock time
    mock_time = ctx.get("mock_time")
    if mock_time is not None:
        pinned_env["FAKETIME"] = mock_time
        pinned_env["COO_MOCK_TIME"] = mock_time
    
    # 4. Hardware Context Verification (F6)
    _verify_hardware_context(ctx)
    
    return pinned_env


def _verify_hardware_context(ctx: Dict[str, Any]) -> None:
    """
    Verify hardware properties match pinned context strictly.
    
    Checks:
    - Kernel version (Fail if UNKNOWN or mismatch)
    - CPU microcode (Fail if UNKNOWN or mismatch)
    
    Raises:
        GovernanceError: If hardware mismatch detected
    """
    # Verify kernel version
    pinned_kernel = ctx.get("kernel_version")
    if pinned_kernel == "UNKNOWN" or pinned_kernel is None:
        raise GovernanceError("Pinned kernel version is UNKNOWN or missing. Hardware verification failed.")
        
    actual_kernel = platform.release()
    if pinned_kernel != actual_kernel:
        raise GovernanceError(
            f"Hardware context mismatch: Kernel version mismatch. "
            f"Expected: {pinned_kernel}, Actual: {actual_kernel}"
        )
    
    # CPU microcode verification
    pinned_microcode = ctx.get("cpu_microcode")
    if pinned_microcode == "UNKNOWN" or pinned_microcode is None:
         raise GovernanceError("Pinned CPU microcode is UNKNOWN or missing. Hardware verification failed.")

    actual_microcode = _read_cpu_microcode()
    if not actual_microcode:
         # If we can't read it, we can't verify. Fail-closed.
         raise GovernanceError("Could not read actual CPU microcode for verification.")
         
    if actual_microcode != pinned_microcode:
        raise GovernanceError(
            f"Hardware context mismatch: CPU microcode mismatch. "
            f"Expected: {pinned_microcode}, Actual: {actual_microcode}"
        )

def _read_cpu_microcode() -> str:
    """
    Read CPU microcode from /proc/cpuinfo (Linux).
    
    Returns:
        Microcode version string or empty string if unavailable
    """
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if "microcode" in line.lower():
                    return line.split(":")[-1].strip()
    except (FileNotFoundError, PermissionError):
        pass
    
    return ""
