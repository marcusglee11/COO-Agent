from pathlib import Path
from . import SecurityViolation

def scan_for_symlinks(root: Path) -> None:
    """
    Recursively scan for symlinks. Raises SecurityViolation if found.
    
    On Windows, is_symlink() may return True for junctions.
    This is acceptable - any filesystem reparse point is treated as a violation.
    
    Raises:
        SecurityViolation: with reason 'sandbox_invalid_symlink' if symlink found
    """
    for p in root.rglob("*"):
        if p.is_symlink():
            raise SecurityViolation(f"sandbox_invalid_symlink: {p.relative_to(root)}")
