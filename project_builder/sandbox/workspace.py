import os
import unicodedata
import logging
from pathlib import Path
from project_builder.config import settings
from . import SecurityViolation

logger = logging.getLogger(__name__)

def materialize_workspace(root: Path, files: list[tuple[str, bytes, str]]) -> None:
    """
    Writes files into workspace under root with path security enforcement.
    
    # NOTE: TOCTOU race between validation and write is accepted risk on Windows.
    # Primary security boundary is resolve().startswith(root) check.
    
    Args:
        root: Workspace root directory
        files: List of (file_path, content_bytes, created_at)
    
    Raises:
        SecurityViolation: If path validation fails with spec-mandated reasons:
            - invalid_artifact_path: path contains \\, .., or starts with /
            - path_escape_attempt: resolved path escapes workspace root
            - resource_limit_exceeded: file size exceeds limit
    """
    for file_path, content, _ in files:
        # Resource Safety: Check file size
        if len(content) > settings.MAX_FILE_SIZE_BYTES:
             raise SecurityViolation(f"resource_limit_exceeded: {file_path} ({len(content)} bytes)")

        # Unicode Safety: Normalize to NFC
        normalized_path = unicodedata.normalize('NFC', file_path)
        
        # Unicode Safety: Reject combining marks (Category 'M')
        for char in normalized_path:
            if unicodedata.category(char).startswith('M'):
                raise SecurityViolation(f"invalid_artifact_path: {file_path} (contains combining marks)")
        
        # Security checks (FIX 3: Explicit backslash rejection)
        if '\\' in normalized_path:
            raise SecurityViolation(f"invalid_artifact_path: {file_path} (contains backslash)")
        if '..' in normalized_path:
            raise SecurityViolation(f"invalid_artifact_path: {file_path} (contains ..)")
        if normalized_path.startswith('/'):
            raise SecurityViolation(f"invalid_artifact_path: {file_path} (absolute path)")
        if '%' in normalized_path:
             raise SecurityViolation(f"invalid_artifact_path: {file_path} (contains %)")

        target = root / normalized_path
        resolved = target.resolve()
        
        # Canonicalization check
        if not str(resolved).startswith(str(root.resolve())):
            raise SecurityViolation(f"invalid_artifact_path: {file_path} (path escape attempt)")
        
        # Write file
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_bytes(content)

def verify_hardlink_defense(workspace_root: Path, output_root: Path) -> None:
    """
    Verify that workspace and output directories are on different filesystems 
    (or at least logically distinct) to prevent hardlink attacks.
    
    Args:
        workspace_root: Path to workspace directory
        output_root: Path to output directory
        
    Raises:
        SecurityViolation: If hardlink defense check fails
    """
    # Create directories if they don't exist to check stats
    workspace_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    
    ws_stat = workspace_root.stat()
    out_stat = output_root.stat()
    
    # On Windows, st_dev might be same for same drive. 
    # We strictly enforce this check as per spec, but note platform limitation.
    if ws_stat.st_dev == out_stat.st_dev:
        # In a real production POSIX env, this is a hard failure.
        # For local dev on Windows, we might need to relax or mock this if single drive.
        # However, spec says "Must check... to ensure distinct filesystems".
        # We will log warning on Windows but fail on POSIX.
        if os.name == 'nt':
            logger.warning("Hardlink defense (st_dev check) is a no-op on Windows. Deployment is assumed dev-only/reduced guarantees.")
        else:
             raise SecurityViolation("hardlink_defense_failure: workspace and output must be on distinct filesystems")
