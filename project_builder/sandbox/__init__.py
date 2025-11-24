# Sandbox package for secure workspace materialization and Docker execution

class SandboxError(Exception):
    """Base class for all sandbox errors."""
    pass

class SecurityViolation(SandboxError):
    """Raised when security validation fails during sandbox operations."""
    pass
