import os
import re
from project_builder.config import settings

# MUST match the Git-tracked canonical coo-sandbox@prod digest.
ALLOWED_PROD_DIGESTS = {
    "sha256:f2c125a3328cd4dc8bbe2afee07e7870028e34fed6440f9c3d6ffaea2f8898477",
}

class SandboxConfigError(Exception):
    """Raised when sandbox configuration violates governance."""
    pass

class ManifestValidationError(Exception):
    """Raised when manifest validation fails."""
    pass

def enforce_governance():
    """
    Enforce governance policies at runtime boundaries.
    Raises SandboxConfigError if violations are detected.
    """
    # 1. Digest Verification
    current_digest = settings.SANDBOX_IMAGE_DIGEST
    
    # Check for placeholder
    placeholder_digest = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    if current_digest == placeholder_digest:
        raise SandboxConfigError("Governance Violation: Placeholder digest detected. Production digest required.")

    # Check against allowed list
    if current_digest not in ALLOWED_PROD_DIGESTS:
        raise SandboxConfigError(f"Governance Violation: Unauthorized sandbox digest: {current_digest}")

    # 2. Platform Verification
    # Reject Windows in PROD mode
    # We assume PROD if COO_ENV is set to PROD
    if os.environ.get("COO_ENV") == "PROD" and os.name == 'nt':
        raise SandboxConfigError("Governance Violation: Windows platform not allowed in PROD")

def validate_manifest_path_contract(path: str):
    """
    Validate manifest path against strict rules.
    Fails closed (raises ManifestValidationError).
    """
    # Explicit backslash rejection
    if '\\' in path:
        raise ManifestValidationError(f"invalid_artifact_path: {path} (contains backslash)")
    
    # No parent directory traversal
    if '..' in path:
        raise ManifestValidationError(f"invalid_artifact_path: {path} (contains ..)")
    
    # No absolute paths
    if path.startswith('/'):
        raise ManifestValidationError(f"invalid_artifact_path: {path} (absolute path)")
    
    # Regex validation
    if not re.match(settings.MANIFEST_PATH_REGEX, path):
        raise ManifestValidationError(f"invalid_artifact_path: {path} (invalid characters)")
