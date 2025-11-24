import pytest
import json
import tempfile
from pathlib import Path
from project_builder.sandbox.manifest import (
    parse_manifest, verify_manifest_checksums,
    SandboxTerminalFailure, ManifestValidationError
)

def test_missing_manifest():
    """FIX 6A: Test that missing manifest raises sandbox_manifest_error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # No manifest file exists
        with pytest.raises(SandboxTerminalFailure, match="sandbox_manifest_error"):
            parse_manifest(root)

def test_incomplete_write():
    """FIX 6B: Test that manifest listing missing file raises sandbox_incomplete_write."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Create manifest listing a file
        manifest = [
            {
                "path": "src/main.py",
                "checksum": "sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
            }
        ]
        (root / ".coo-manifest.json").write_text(json.dumps(manifest))
        
        # Parse should succeed
        entries = parse_manifest(root)
        
        # But verification should fail (file doesn't exist)
        with pytest.raises(SandboxTerminalFailure, match="sandbox_incomplete_write"):
            verify_manifest_checksums(root, entries)

def test_invalid_json():
    """Test that malformed JSON raises manifest_syntax_error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Write invalid JSON
        (root / ".coo-manifest.json").write_text("{invalid json")
        
        with pytest.raises(ManifestValidationError, match="manifest_syntax_error"):
            parse_manifest(root)

def test_malformed_checksum():
    """Test that malformed checksums are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Invalid checksum format (missing sha256: prefix)
        manifest = [
            {
                "path": "test.txt",
                "checksum": "1234567890abcdef"
            }
        ]
        (root / ".coo-manifest.json").write_text(json.dumps(manifest))
        
        with pytest.raises(ManifestValidationError, match="manifest_syntax_error.*checksum"):
            parse_manifest(root)

def test_checksum_mismatch():
    """Test that checksum mismatch raises sandbox_checksum_mismatch."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Create file with known content
        (root / "test.txt").write_bytes(b"actual content")
        
        # Manifest with wrong checksum
        manifest = [
            {
                "path": "test.txt",
                "checksum": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
            }
        ]
        (root / ".coo-manifest.json").write_text(json.dumps(manifest))
        
        entries = parse_manifest(root)
        
        with pytest.raises(SandboxTerminalFailure, match="sandbox_checksum_mismatch"):
            verify_manifest_checksums(root, entries)

def test_path_special_chars():
    """Test that special characters in paths are rejected (FIX 3)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Test backslash
        manifest = [{"path": "src\\main.py", "checksum": "sha256:" + "0"*64}]
        (root / ".coo-manifest.json").write_text(json.dumps(manifest))
        with pytest.raises(ManifestValidationError, match="invalid_artifact_path.*backslash"):
            parse_manifest(root)
        
        # Test semicolon
        manifest = [{"path": "src;rm -rf", "checksum": "sha256:" + "0"*64}]
        (root / ".coo-manifest.json").write_text(json.dumps(manifest))
        with pytest.raises(ManifestValidationError, match="invalid_artifact_path"):
            parse_manifest(root)
        
        # Test pipe
        manifest = [{"path": "src|cat", "checksum": "sha256:" + "0"*64}]
        (root / ".coo-manifest.json").write_text(json.dumps(manifest))
        with pytest.raises(ManifestValidationError, match="invalid_artifact_path"):
            parse_manifest(root)

def test_valid_paths_with_spaces():
    """Test that valid paths with spaces are accepted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        manifest = [
            {
                "path": "My Document.txt",
                "checksum": "sha256:" + "0"*64
            }
        ]
        (root / ".coo-manifest.json").write_text(json.dumps(manifest))
        
        # Should parse successfully (validation passes)
        entries = parse_manifest(root)
        assert len(entries) == 1
        assert entries[0]['path'] == "My Document.txt"

def test_checksum_line_ending_normalization():
    """Test that CRLF is normalized to LF before hashing."""
    import hashlib
    
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Create file with CRLF line endings
        content_crlf = b"line1\r\nline2\r\n"
        (root / "test.txt").write_bytes(content_crlf)
        
        # Expected checksum is for LF-normalized version
        content_lf = b"line1\nline2\n"
        expected_hash = hashlib.sha256(content_lf).hexdigest()
        
        manifest = [
            {
                "path": "test.txt",
                "checksum": f"sha256:{expected_hash}"
            }
        ]
        (root / ".coo-manifest.json").write_text(json.dumps(manifest))
        
        entries = parse_manifest(root)
        # Should not raise (checksum matches after normalization)
        verify_manifest_checksums(root, entries)
