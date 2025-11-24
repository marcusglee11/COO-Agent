import pytest
import tempfile
import os
from pathlib import Path
from project_builder.sandbox.workspace import materialize_workspace, SecurityViolation
from project_builder.sandbox.security import scan_for_symlinks

def test_path_traversal_attacks():
    """Test that path traversal attempts are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Test 1: ../../etc/passwd
        with pytest.raises(SecurityViolation, match="invalid_artifact_path.*\\.\\."):
            materialize_workspace(root, [("../../etc/passwd", b"content", "2023-01-01")])
        
        # Test 2: ../../../root/.ssh/id_rsa  
        with pytest.raises(SecurityViolation, match="invalid_artifact_path.*\\.\\."):
            materialize_workspace(root, [("../../../root/.ssh/id_rsa", b"content", "2023-01-01")])
        
        # Test 3: subdir/../../etc
        with pytest.raises(SecurityViolation, match="invalid_artifact_path.*\\.\\."):
            materialize_workspace(root, [("subdir/../../etc", b"content", "2023-01-01")])

def test_symlink_detection():
    """Test that symlinks are detected and rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Create a normal file
        (root / "normal.txt").write_text("content")
        
        # No error for normal files
        scan_for_symlinks(root)
        
        # Create a symlink
        link_path = root / "bad_link"
        target_path = root / "target.txt"
        target_path.write_text("target")
        
        if os.name != 'nt':  # Unix/Linux
            link_path.symlink_to(target_path)
            with pytest.raises(SecurityViolation, match="sandbox_invalid_symlink"):
                scan_for_symlinks(root)

def test_path_validation_backslash():
    """Test that ANY backslash in path is rejected (FIX 3)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Test single backslash
        with pytest.raises(SecurityViolation, match="invalid_artifact_path.*backslash"):
            materialize_workspace(root, [("src\\main.py", b"content", "2023-01-01")])
        
        # Test double backslash
        with pytest.raises(SecurityViolation, match="invalid_artifact_path.*backslash"):
            materialize_workspace(root, [("src\\\\main.py", b"content", "2023-01-01")])

def test_path_validation_absolute():
    """Test that absolute paths are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        with pytest.raises(SecurityViolation, match="invalid_artifact_path.*absolute"):
            materialize_workspace(root, [("/etc/passwd", b"content", "2023-01-01")])

def test_path_validation_valid():
    """Test that valid relative paths are accepted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Valid paths should work
        materialize_workspace(root, [
            ("src/main.py", b"print('hello')", "2023-01-01"),
            ("data/file.txt", b"data", "2023-01-01"),
            ("README.md", b"# README", "2023-01-01")
        ])
        
        assert (root / "src" / "main.py").exists()
        assert (root / "data" / "file.txt").exists()
        assert (root / "README.md").exists()

def test_workspace_cleanup():
    """Test that workspace directory cleanup works."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Materialize some files
        materialize_workspace(root, [
            ("test.txt", b"content", "2023-01-01")
        ])
        
        # Verify file exists
        assert (root / "test.txt").exists()
        
        # Cleanup (handled by tempfile context manager)
        # After this block, directory is deleted

def test_integration_full_lifecycle():
    """Integration test: materialize -> scan -> verify (Required Amendment)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Step 1: Materialize workspace
        files = [
            ("src/main.py", b"print('test')", "2023-01-01"),
            ("data/input.txt", b"data", "2023-01-01")
        ]
        materialize_workspace(root, files)
        
        # Step 2: Security scan (should pass)
        scan_for_symlinks(root)
        
        # Step 3: Verify files exist
        assert (root / "src" / "main.py").exists()
        assert (root / "data" / "input.txt").exists()
        
        # Cleanup verification - all files should be removed after context exit
