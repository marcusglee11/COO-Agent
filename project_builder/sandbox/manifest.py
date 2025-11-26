import json
import re
from pathlib import Path
from project_builder.config import settings
from project_builder.config.governance import validate_manifest_path_contract, ManifestValidationError

class SandboxTerminalFailure(Exception):
    """Raised when sandbox operation fails terminally."""
    pass

class ManifestValidationError(Exception):
    """Raised when manifest validation fails."""
    pass

MANIFEST_PATH_REGEX = re.compile(settings.MANIFEST_PATH_REGEX)
CHECKSUM_FORMAT_REGEX = re.compile(settings.CHECKSUM_FORMAT_REGEX)

def parse_manifest(workspace_root: Path) -> list[dict]:
    """
    Parse .coo-manifest.json from workspace root with validation.
    
    Args:
        workspace_root: Path to workspace directory
        
    Returns:
        List of manifest entries (dicts with 'path' and 'checksum' keys)
        
    Raises:
        SandboxTerminalFailure: If manifest file doesn't exist
        ManifestValidationError: If manifest is invalid (JSON syntax, path format, etc.)
    """
    manifest_path = workspace_root / ".coo-manifest.json"
    
    # FIX 2: Missing manifest check
    if not manifest_path.exists():
        raise SandboxTerminalFailure("sandbox_manifest_error")
    
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ManifestValidationError(f"manifest_syntax_error: {e}")
    
    if not isinstance(manifest_data, list):
        raise ManifestValidationError("manifest_syntax_error: Expected array of entries")
    
    validated_entries = []
    for entry in manifest_data:
        # Validate structure
        if not isinstance(entry, dict) or 'path' not in entry or 'checksum' not in entry:
            raise ManifestValidationError("manifest_syntax_error: Missing required fields")
        
        path = entry['path']
        checksum = entry['checksum']
        
        # Path validation (Delegated to Governance)
        validate_manifest_path_contract(path)
        
        # Checksum format validation
        if not CHECKSUM_FORMAT_REGEX.match(checksum):
            raise ManifestValidationError(f"manifest_syntax_error: Invalid checksum format for {path}")
        
        validated_entries.append(entry)
    
    return validated_entries

def verify_manifest_checksums(workspace_root: Path, manifest_entries: list[dict]) -> None:
    """
    Verify that all files in manifest exist and match checksums.
    
    Args:
        workspace_root: Path to workspace directory
        manifest_entries: Validated manifest entries from parse_manifest
        
    Raises:
        SandboxTerminalFailure: If file missing or checksum mismatch
    """
    import hashlib
    
    for entry in manifest_entries:
        path = entry['path']
        expected_checksum = entry['checksum']
        
        file_path = workspace_root / path
        
        # FIX 6B: Check for incomplete write
        if not file_path.exists():
            raise SandboxTerminalFailure(f"sandbox_incomplete_write: {path}")
        
        # Read file content
        content = file_path.read_bytes()
        
        # Text/Binary Classification & Normalization
        try:
            # Try decoding as UTF-8
            text = content.decode('utf-8')
            # Success -> It's text. Normalize CRLF to LF.
            normalized = text.replace('\r\n', '\n')
            content_to_hash = normalized.encode('utf-8')
        except UnicodeDecodeError:
            # Failure -> It's binary. Use as-is.
            content_to_hash = content
        
        actual_hash = hashlib.sha256(content_to_hash).hexdigest()
        actual_checksum = f"sha256:{actual_hash}"
        
        if actual_checksum != expected_checksum:
            raise SandboxTerminalFailure(f"sandbox_checksum_mismatch: {path}")
