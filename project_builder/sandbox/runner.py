import subprocess
import threading
import time
import os
from pathlib import Path
from project_builder.config import settings

# Try importing watchdog for inotify support (Linux only usually, but good for structure)
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

from . import SecurityViolation
from project_builder.config.governance import enforce_governance

class InotifyGuard(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    """
    Monitors output directory for symlink creation.
    Kills container if detected.
    """
    def __init__(self, container_name: str):
        self.container_name = container_name
        self.violation_detected = False

    def on_created(self, event):
        if event.is_directory:
            return
        # Check if created file is a symlink
        if os.path.islink(event.src_path):
            self.violation_detected = True
            # Kill container immediately
            subprocess.run(["docker", "kill", self.container_name], check=False)

def run_sandbox(workspace_root: Path, output_root: Path, entrypoint: str, timeout_seconds: int) -> int:
    """
    Execute entrypoint script inside Docker container with security constraints.
    
    Args:
        workspace_root: Path to workspace directory (RO)
        output_root: Path to output directory (RW)
        entrypoint: Shell command to execute
        timeout_seconds: Timeout in seconds
        
    Returns:
        Exit code from container
    """
    # Enforce Governance
    enforce_governance()

    # Verify Image Digest
    image_ref = f"coo-sandbox@{settings.SANDBOX_IMAGE_DIGEST}"
    
    # Verify digest exists (mock check for now as we don't have the image locally)
    # subprocess.run(["docker", "inspect", image_ref], check=True)

    # Ensure output directory exists
    output_root.mkdir(parents=True, exist_ok=True)

    # Inotify Guard (Linux Only)
    observer = None
    container_name = f"coo-sandbox-{os.getpid()}"
    
    if WATCHDOG_AVAILABLE and os.name != 'nt':
        guard = InotifyGuard(container_name)
        observer = Observer()
        observer.schedule(guard, str(output_root), recursive=True)
        observer.start()

    try:
        # Construct canonical Docker command using list (NO string interpolation of manifest fields)
        cmd = [
            "docker", "run", "--rm",
            "--name", container_name,
            "--network=none",
            "--user", settings.SANDBOX_USER_UID,
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            # Default seccomp profile is used (secure default)
            "--pids-limit", str(settings.SANDBOX_PIDS_LIMIT),
            "--memory", settings.SANDBOX_MEMORY_LIMIT,
            "--memory-swap", settings.SANDBOX_MEMORY_SWAP,
            "--cpus", settings.SANDBOX_CPU_LIMIT,
            "-v", f"{workspace_root.resolve()}:/workspace:ro", # RO Workspace
            "-v", f"{output_root.resolve()}:/output:rw",       # RW Output
            "-w", "/workspace",                                # Working Directory
            image_ref,
            "bash", "-c", entrypoint # Entrypoint is passed as arg, not interpolated into shell string
        ]
        
        # Execute with timeout
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout_seconds,
            check=False
        )
        
        if observer and guard.violation_detected:
            raise SecurityViolation("inotify_guard_triggered: symlink creation detected in output/")
            
        return result.returncode

    finally:
        if observer:
            observer.stop()
            observer.join()
