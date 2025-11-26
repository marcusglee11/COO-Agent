import pytest
import os
from unittest.mock import patch
from project_builder.config import governance, settings

# Placeholder digest for testing failure
PLACEHOLDER_DIGEST = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
VALID_DIGEST = "sha256:f2c125a3328cd4dc8bbe2afee07e7870028e34fed6440f9c3d6ffaea2f8898477"

class TestEnforceGovernance:
    def test_valid_digest(self):
        """Should pass with valid digest."""
        with patch.object(settings, 'SANDBOX_IMAGE_DIGEST', VALID_DIGEST):
            governance.enforce_governance()

    def test_placeholder_digest_failure(self):
        """Should fail if digest is placeholder."""
        with patch.object(settings, 'SANDBOX_IMAGE_DIGEST', PLACEHOLDER_DIGEST):
            with pytest.raises(governance.SandboxConfigError, match="Placeholder digest detected"):
                governance.enforce_governance()

    def test_invalid_digest_failure(self):
        """Should fail if digest is not in allowed list."""
        with patch.object(settings, 'SANDBOX_IMAGE_DIGEST', "sha256:invalid"):
            with pytest.raises(governance.SandboxConfigError, match="Unauthorized sandbox digest"):
                governance.enforce_governance()

    def test_windows_prod_failure(self):
        """Should fail on Windows if COO_ENV is PROD."""
        with patch.dict(os.environ, {"COO_ENV": "PROD"}), \
             patch("os.name", "nt"), \
             patch.object(settings, 'SANDBOX_IMAGE_DIGEST', VALID_DIGEST):
            with pytest.raises(governance.SandboxConfigError, match="Windows platform not allowed in PROD"):
                governance.enforce_governance()

    def test_windows_dev_success(self):
        """Should pass on Windows if COO_ENV is not PROD."""
        with patch.dict(os.environ, {"COO_ENV": "DEV"}), \
             patch("os.name", "nt"), \
             patch.object(settings, 'SANDBOX_IMAGE_DIGEST', VALID_DIGEST):
            governance.enforce_governance()

    def test_empty_digest_failure(self):
        """Should fail if digest is empty."""
        with patch.object(settings, 'SANDBOX_IMAGE_DIGEST', ""):
            with pytest.raises(governance.SandboxConfigError, match="Unauthorized sandbox digest"):
                governance.enforce_governance()

    def test_malformed_digest_failure(self):
        """Should fail if digest is malformed (even if not in allowed list check, it fails that check first)."""
        with patch.object(settings, 'SANDBOX_IMAGE_DIGEST', "not-a-digest"):
            with pytest.raises(governance.SandboxConfigError, match="Unauthorized sandbox digest"):
                governance.enforce_governance()

class TestValidateManifestPathContract:
    def test_valid_paths(self):
        valid_paths = ["file.txt", "dir/file.txt", "dir/subdir/file.py"]
        for path in valid_paths:
            governance.validate_manifest_path_contract(path)

    def test_backslash_failure(self):
        with pytest.raises(governance.ManifestValidationError, match="contains backslash"):
            governance.validate_manifest_path_contract("dir\\file.txt")

    def test_parent_traversal_failure(self):
        with pytest.raises(governance.ManifestValidationError, match="contains .."):
            governance.validate_manifest_path_contract("../file.txt")

    def test_absolute_path_failure(self):
        with pytest.raises(governance.ManifestValidationError, match="absolute path"):
            governance.validate_manifest_path_contract("/etc/passwd")

    def test_invalid_chars_failure(self):
        with pytest.raises(governance.ManifestValidationError, match="invalid characters"):
            governance.validate_manifest_path_contract("file?.txt")
