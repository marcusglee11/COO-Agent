# COO Runtime v1.0 R6.3
# Per R6.3 B2: Linux-only enforcement at import level

import sys

# ============================================================================
# B2: Linux-Only Enforcement - R6.3
# ============================================================================

if sys.platform != "linux":
    raise ImportError(
        f"COO Runtime v1.0 R6.3 requires Linux. "
        f"Current platform: {sys.platform}. "
        f"Use WSL2, Linux VM, or native Linux for development."
    )

# Rest of package initialization
# (existing code continues below)
