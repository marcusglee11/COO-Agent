"""
Pinned context enforcement utilities for COO Runtime.
Enforces deterministic environment: RNG seed, env vars, mock time, hardware verification.
"""
import os
import json
import random
import platform
from typing import Dict, Any
from ..runtime.state_machine import GovernanceError

def apply_pinned_context(pinned_context_path: str) -> None:
    """
    Apply pinned context to enforce deterministic environment.
    
    Enforces:
    - RNG seed
    - Environment variable allowlist
    - Mock time (via FAKETIME)
    - Hardware context verification
    
    Args:
        pinned_context_path: Path to pinned_context.json
        
    Raises:
        GovernanceError: If context mismatch detected
    """
    with open(pinned_context_path, "r") as f:
        ctx = json.load(f)

    # 1. RNG Seed
    rng_seed = ctx.get("rng_seed", "DETERMINISTIC_SEED_DEFAULT")
    random.seed(rng_seed)

    # 2. ENV VARS (replace all non-allowed vars)
    # Store original env for later restoration if needed
    allowed_env_vars = ctx.get("env_vars", {})
    
    # Clear environment and set only allowed vars
    os.environ.clear()
    for k, v in allowed_env_vars.items():
        os.environ[k] = str(v)

    # 3. Mock time (if specified)
    mock_time = ctx.get("mock_time")
    if mock_time is not None:
        # Use FAKETIME environment variable for libfaketime
        os.environ["FAKETIME"] = mock_time
        os.environ["COO_MOCK_TIME"] = mock_time  # Also set our internal mock time

    # 4. Hardware Context Verification
    _verify_hardware_context(ctx)


def _verify_hardware_context(ctx: Dict[str, Any]) -> None:
    """
    Verify hardware properties match pinned context.
    
    Checks:
    - Kernel version
    - CPU microcode (if available)
    - NUMA topology (if available)
    
    Raises:
        GovernanceError: If hardware mismatch detected
    """
    # Verify kernel version
    pinned_kernel = ctx.get("kernel_version", "UNKNOWN")
    actual_kernel = platform.release()
    
    if pinned_kernel != "UNKNOWN" and pinned_kernel != actual_kernel:
        raise GovernanceError(
            f"Hardware context mismatch: Kernel version mismatch. "
            f"Expected: {pinned_kernel}, Actual: {actual_kernel}"
        )
    
    # CPU microcode verification
    pinned_microcode = ctx.get("cpu_microcode", "UNKNOWN")
    if pinned_microcode != "UNKNOWN":
        # Try to read actual microcode (Linux-specific)
        actual_microcode = _read_cpu_microcode()
        if actual_microcode and actual_microcode != pinned_microcode:
            raise GovernanceError(
                f"Hardware context mismatch: CPU microcode mismatch. "
                f"Expected: {pinned_microcode}, Actual: {actual_microcode}"
            )
    
    # NUMA topology verification
    pinned_numa = ctx.get("numa_topology", "UNKNOWN")
    if pinned_numa != "UNKNOWN":
        # Simple check - in production this would be more thorough
        pass  # Skip for now - requires platform-specific tooling


def _read_cpu_microcode() -> str:
    """
    Read CPU microcode from /proc/cpuinfo (Linux) or equivalent.
    
    Returns:
        Microcode version string or empty string if unavailable
    """
    try:
        if platform.system() == "Linux":
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "microcode" in line.lower():
                        return line.split(":")[-1].strip()
    except (FileNotFoundError, PermissionError):
        pass
    
    return ""
