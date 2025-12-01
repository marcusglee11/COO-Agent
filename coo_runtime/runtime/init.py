"""
Runtime initialization module.
Per R6.3 B3: Centralized initialization required before all deterministic operations.
"""
import os
import json
import random
import sys
from typing import Optional
from ..runtime.state_machine import GovernanceError
from ..util.context import capture_hardware_context, _verify_time_pinning

# ============================================================================
# B3: Runtime Initialization - R6.3
# ============================================================================

_initialized_amu0_path: Optional[str] = None  # Module-level state

def initialize_runtime(amu0_path: str) -> None:
    """
    Initialize runtime with pinned context from AMU0.
    Must be called once per process before any deterministic operations.
    
    R6.3 B3 Rules:
    - First call: Initialize with given amu0_path
    - Second call with SAME amu0_path: No-op (idempotent)
    - Call with DIFFERENT amu0_path: Raise GovernanceError
    
    Performs:
    1. Platform validation (already done in __init__.py)
    2. Load pinned context
    3. Verify hardware context
    4. Seed RNG with deterministic seed
    5. Verify time pinning (if configured)
    6. Record initialized AMU₀ path
    
    Args:
        amu0_path: Path to AMU0 directory
        
    Raises:
        GovernanceError: On initialization failure or multiple AMU0s
    """
    global _initialized_amu0_path
    
    # Check if already initialized
    if _initialized_amu0_path is not None:
        if _initialized_amu0_path == amu0_path:
            return  # Idempotent for same AMU0
        else:
            raise GovernanceError(
                f"Runtime already initialized with {_initialized_amu0_path}. "
                f"Cannot re-initialize with {amu0_path}."
            )
    
    # 1. Load pinned context
    context_path = os.path.join(amu0_path, 'pinned_context.json')
    if not os.path.exists(context_path):
        raise GovernanceError(f"Pinned context not found at {context_path}")
    
    try:
        with open(context_path, 'r') as f:
            context = json.load(f)
    except json.JSONDecodeError as e:
        raise GovernanceError(f"Pinned context corrupted: {e}")
    
    # 2. Verify hardware
    from ..util.context import _verify_hardware_context
    _verify_hardware_context(context)
    
    # 3. Load Keys (R6.5 G2)
    from ..util.crypto import load_keys
    load_keys()
    
    # 4. Seed RNG
    rng_seed = context.get('rng_seed', 'DETERMINISTIC_SEED_DEFAULT')
    random.seed(rng_seed)
    
    # 4. Verify time pinning (if configured)
    mock_time = context.get('mock_time')
    if mock_time:
            # Verify time pinning
            # R6.5 F2: Pass amu0_path, let run_pinned_subprocess handle env
            _verify_time_pinning(amu0_path, mock_time)
    
    # 5. Mark as initialized
    _initialized_amu0_path = amu0_path

def assert_initialized() -> None:
    """
    Assert that runtime has been initialized.
    
    R6.3 B3: For internal checks in library code.
    
    Raises:
        GovernanceError: If runtime not initialized
    """
    if _initialized_amu0_path is None:
        raise GovernanceError(
            "Runtime not initialized. Call initialize_runtime(amu0_path) first."
        )

def get_initialized_amu0_path() -> Optional[str]:
    """
    Get the currently initialized AMU0 path.
    
    Returns:
        AMU0 path if initialized, None otherwise
    """
    return _initialized_amu0_path
