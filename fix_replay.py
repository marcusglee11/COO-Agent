"""
Quick script to finish remaining R6.3 Phase 4 integration.
Fixes replay.py subprocess call.
"""
import re

# Read replay.py
with open("coo_runtime/runtime/replay.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add import after amu0_utils import
if "from ..util.subprocess import run_pinned_subprocess" not in content:
    content = content.replace(
        "from ..util import amu0_utils",
        "from ..util import amu0_utils\nfrom ..util.subprocess import run_pinned_subprocess"
    )

# 2. Replace the subprocess.run call (be very specific)
old_pattern = '''            # Run harness in subprocess with pinned environment (R6 B.2)
            subprocess.run(
                [sys.executable, harness_path, mission_path, output_dir, "--amu0", amu0_path, "--mode", mode],
                check=True,
                env=env,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Replay Harness Failed: {e.stdout}\\n{e.stderr}")
            raise GovernanceError(f"Replay Execution Failed (Subprocess): {e}")'''

new_pattern = '''            # R6.3 B5: Run harness with pinned subprocess
            run_pinned_subprocess(
                [sys.executable, harness_path, mission_path, output_dir, "--amu0", amu0_path, "--mode", mode],
                amu0_path,
                check=True,
                capture_output=True,
                text=True
            )
        except Exception as e:
            self.logger.error(f"Replay Harness Failed: {e}")
            raise GovernanceError(f"Replay Execution Failed (Subprocess): {e}")'''

content = content.replace(old_pattern, new_pattern)

# Write back
with open("coo_runtime/runtime/replay.py", "w", encoding="utf-8") as f:
    f.write(content)

print("✅ replay.py updated successfully")
