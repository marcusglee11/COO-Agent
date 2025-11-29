"""
Subprocess utilities with pinned context enforcement.
Per R6.3 B5: All subprocess calls MUST use pinned context.
"""
import os
import json
import subprocess
from typing import List, Dict, Any
from ..runtime.state_machine import GovernanceError

# ============================================================================
# E2/B5: Pinned PATH - R6.3
# ============================================================================

PINNED_PATH = "/usr/bin:/bin"  # R6.3 E2: Fixed, deterministic PATH

def run_pinned_subprocess(
    cmd: List[str],
    amu0_path: str,
    **kwargs
) -> subprocess.CompletedProcess:
    """
    Run subprocess with pinned context from AMU0.
    
    R6.3 B5: ALL subprocess calls MUST use this helper.
    Direct usage of subprocess.run/check_output/Popen is FORBIDDEN.
    
    Args:
        cmd: Command and arguments
        amu0_path: Path to AMU0 for pinned context
        **kwargs: Additional subprocess.run arguments
        
    Returns:
        CompletedProcess from subprocess.run
        
    Raises:
        GovernanceError: If tool not found or execution fails
        
    Note:
        PATH is fixed to /usr/bin:/bin per R6.3 E2.
        Required tools must be installed in one of those directories.
    """
    # Load pinned context
    context_path = os.path.join(amu0_path, 'pinned_context.json')
    if not os.path.exists(context_path):
        raise GovernanceError(f"Pinned context not found at {context_path}")
    
    try:
        with open(context_path, 'r') as f:
            context = json.load(f)
    except json.JSONDecodeError as e:
        raise GovernanceError(f"Pinned context corrupted: {e}")
    
    # Build pinned environment
    pinned_env = {}
    
    # 1. Fixed PATH (R6.3 E2)
    pinned_env['PATH'] = PINNED_PATH
    
    # 2. Allowed env vars from context
    for key, value in context.get('env_vars', {}).items():
        pinned_env[key] = str(value)
    
    # 3. LD_PRELOAD for libfaketime (if configured)
    mock_time = context.get('mock_time')
    libfaketime_enabled = context.get('libfaketime_enabled', False)
    if mock_time and libfaketime_enabled:
        pinned_env['LD_PRELOAD'] = '/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1'
        pinned_env['FAKETIME'] = mock_time
    
    # Override any env in kwargs (enforce pinned env)
    if 'env' in kwargs:
        kwargs.pop('env')
    
    # Run subprocess
    try:
        return subprocess.run(cmd, env=pinned_env, **kwargs)
    except FileNotFoundError as e:
        # Tool not found in pinned PATH
        raise GovernanceError(
            f"Required tool '{cmd[0]}' not found in pinned PATH {PINNED_PATH}. "
            f"Ensure tool is installed in /usr/bin or /bin."
        ) from e
    except subprocess.CalledProcessError as e:
        # Command failed
        raise GovernanceError(
            f"Subprocess command failed: {' '.join(cmd)}\n"
            f"Exit code: {e.returncode}\n"
            f"Output: {e.output if hasattr(e, 'output') else 'N/A'}"
        ) from e
