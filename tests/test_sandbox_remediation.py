import pytest
import tempfile
import unicodedata
from pathlib import Path
from project_builder.sandbox.workspace import materialize_workspace, SecurityViolation, verify_hardlink_defense
from project_builder.config import settings

def test_unicode_safety_combining_marks():
    """Test that paths with combining marks are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # 'e' + combining acute accent
        path = "t" + "\u0301" + "est.txt" 
        
        with pytest.raises(SecurityViolation, match="invalid_artifact_path.*combining marks"):
            materialize_workspace(root, [(path, b"content", "2023-01-01")])

def test_unicode_safety_normalization():
    """Test that paths are normalized to NFC."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # 'e' + combining acute accent (NFD)
        nfd_path = "e" + "\u0301"
        # NFC equivalent
        nfc_path = "\u00e9"
        
        # Should be normalized and written as NFC
        materialize_workspace(root, [(nfd_path, b"content", "2023-01-01")])
        
        assert (root / nfc_path).exists()
        # NFD path string check might fail depending on OS filesystem normalization, 
        # but we check if the file exists under the NFC name.

def test_resource_limit_file_size():
    """Test that files exceeding MAX_FILE_SIZE_BYTES are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Create content larger than limit (10MB)
        # We'll mock the setting to be small for test speed
        original_limit = settings.MAX_FILE_SIZE_BYTES
        settings.MAX_FILE_SIZE_BYTES = 100 # 100 bytes
        
        try:
            large_content = b"a" * 101
            with pytest.raises(SecurityViolation, match="resource_limit_exceeded"):
                materialize_workspace(root, [("large.txt", large_content, "2023-01-01")])
        finally:
            settings.MAX_FILE_SIZE_BYTES = original_limit

def test_hardlink_defense():
    """Test hardlink defense verification."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        ws = root / "workspace"
        out = root / "output"
        
        # On Windows/Local, these are likely on same dev, so it should pass (warning only)
        # or fail if we enforced strict check. 
        # The code currently passes on Windows.
        verify_hardlink_defense(ws, out) 
        
        # If we were to mock different st_dev, we could test the failure case.

def test_unicode_percent_rejection():
    """Test that paths with % are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        with pytest.raises(SecurityViolation, match="invalid_artifact_path.*%"):
            materialize_workspace(root, [("test%20file.txt", b"content", "2023-01-01")])
