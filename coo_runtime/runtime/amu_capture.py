import os
import json
import uuid
import shutil
import logging
import hashlib
from typing import Optional, Dict, Any
from ..runtime.state_machine import GovernanceError
from ..util.crypto import Signature, create_signature_metadata
from ..util import amu0_utils
from ..util.questions import raise_question, QuestionType
from ..util.context import capture_hardware_context
from ..util.subprocess import run_pinned_subprocess

class AMUCapture:
    """
    Handles the capture of the AMU0 (Authorized Mission Unit 0) state.
    This includes:
    1. Filesystem snapshot (Project Builder, COO, Manifests)
    2. Pinned Context (RNG seed, env vars, time)
    3. Cryptographic Signing (Ed25519)
    """
    def __init__(self):
        self.logger = logging.getLogger("AMUCapture")
        # R6.3: Key paths from environment variables only (D1)
        # No repository paths, no fallbacks

    def capture_amu0(self, manifests_dir: str, mission_path: str) -> str:
        """
        Execute the AMU0 capture process.
        
        Args:
            manifests_dir: Path to manifests directory
            mission_path: Path to reference mission file
            
        Returns:
            Path to the captured AMU0 directory
        """
        self.logger.info("Initiating AMU0 Capture...")
        
        # 1. Validate Manifests (A.3)
        self._validate_manifests(manifests_dir)

        # 2. Prepare Temporary Directory for Snapshot
        # We need to snapshot first to calculate the hash/ID
        temp_id = str(uuid.uuid4())
        temp_dir = os.path.abspath(f"temp_amu0_{temp_id}")
        os.makedirs(temp_dir)
        
        try:
            # 3. Snapshot Filesystem
            snapshot_manifest = self._snapshot_filesystem(temp_dir, manifests_dir, mission_path)
            
            # 4. Initialize Rollback Log (A.1)
            # Empty log file
            with open(os.path.join(temp_dir, "rollback_log.jsonl"), "w") as f:
                pass
            
            # 5. Verify Hygiene (R6.5 A3)
            self._verify_amu0_temp_hygiene(temp_dir)

            # 6. Calculate Canonical Hash & Derive ID (A.3)
            try:
                canonical_hash = amu0_utils.calculate_canonical_hash(temp_dir)
            except GovernanceError as e:
                raise GovernanceError(f"AMU0 Hashing Failed: {e}")
                
            amu0_id = amu0_utils.derive_amu0_id(canonical_hash)
            
            # 7. Sign AMU0 Bundle in Temp (R6.5 A3)
            # Sign using unified Signature protocol (memory keys)
            signature = Signature.sign_data(canonical_hash)
            with open(os.path.join(temp_dir, "signature.sig"), "wb") as f:
                f.write(signature)
            
            # 8. Rename to Final AMU0 Directory (Atomic Promotion)
            amu_dir_name = f"amu0_{amu0_id}"
            amu_dir = os.path.abspath(amu_dir_name)
            
            if os.path.exists(amu_dir):
                self.logger.warning(f"AMU0 directory {amu_dir} already exists. Overwriting/Using existing.")
                shutil.rmtree(amu_dir)
                
            os.rename(temp_dir, amu_dir)
            self.logger.info(f"Created AMU0 directory: {amu_dir}")
            
            # 9. Post-Promotion Verification (R6.5 A3)
            # Verify hash matches what we signed
            final_hash = amu0_utils.calculate_canonical_hash(amu_dir)
            if final_hash != canonical_hash:
                raise_question(QuestionType.AMU0_INTEGRITY, "Post-promotion canonical hash mismatch!")

            # 10. Persist Active AMU0 Path (A.1 - Signed Tracker)
            # ... (rest of tracker logic)
            # Get current git commit using pinned subprocess
            try:
                result = run_pinned_subprocess(
                    ["git", "rev-parse", "HEAD"],
                    amu_dir,
                    capture_output=True,
                    text=True,
                    check=True
                )
                repo_commit = result.stdout.strip()
            except Exception as e:
                raise GovernanceError(f"Cannot determine git commit: {e}")

            # Use pinned timestamp if available, else current time (but R6 says pinned time)
            # We have pinned_context['mock_time'] from manifest or generated.
            # Let's use the timestamp we put in snapshot_manifest.
            created_at = snapshot_manifest["timestamp"]

            # R6.3 Supplemental: Add mode to tracker
            mode = os.environ.get("COO_MODE", "dev")
            
            tracker_payload = {
                "amu0_id": amu0_id,
                "amu0_path": amu_dir_name,
                "created_at": created_at,
                "repo_commit": repo_commit,
                "mode": mode  # R6.3 Supplemental: dev/prod separation
            }
            
            # Sign the payload (R6.3 D2: Unified Signature Protocol)
            tracker_bytes = json.dumps(tracker_payload, sort_keys=True).encode("utf-8")
            
            # R6.5 G2: Use memory-resident keys (no path resolution)
            try:
                tracker_sig = Signature.sign_data(tracker_bytes)
            except Exception as e:
                raise GovernanceError(f"Signing failed: {e}")
            
            # Write Tracker JSON
            with open("active_amu0_path.json", "w") as f:
                json.dump(tracker_payload, f, sort_keys=True)

            # Write Signature File
            with open("active_amu0_path.json.sig", "wb") as f:
                f.write(tracker_sig)
                
            # Remove old trackers if exist
            if os.path.exists("active_amu0_path.txt"):
                os.remove("active_amu0_path.txt")
            if os.path.exists("active_amu0.json"):
                os.remove("active_amu0.json")
            
            # 9. Sign AMU0 Bundle (F1) - MOVED TO STEP 7 (Before Rename)
            # self._sign_amu0(amu_dir) -> Removed, done in temp
            
            self.logger.info(f"AMU0 Capture Complete. ID: {amu0_id}")
            return amu_dir
            
        except Exception as e:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise e

    def _validate_manifests(self, manifests_dir: str) -> None:
        """
        Validates manifests against strict schema (A.3).
        """
        # Environment Manifest
        env_path = os.path.join(manifests_dir, "environment_manifest.json")
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    raise GovernanceError("environment_manifest.json is not valid JSON")
            
            # Check allowed_env_vars is a list
            if "allowed_env_vars" in data and not isinstance(data["allowed_env_vars"], list):
                raise GovernanceError("environment_manifest.json: allowed_env_vars must be a list")
                
        # Sandbox Manifest
        sandbox_path = os.path.join(manifests_dir, "sandbox_manifest.json")
        if os.path.exists(sandbox_path):
            with open(sandbox_path, "r") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    raise GovernanceError("sandbox_manifest.json is not valid JSON")
                    
            if "image_sha256" not in data:
                raise GovernanceError("sandbox_manifest.json: missing image_sha256")

    def _verify_amu0_temp_hygiene(self, temp_dir: str) -> None:
        """
        R6.5 A3: Verify AMU0 hygiene before promotion.
        No symlinks, no .tmp files, no metadata files.
        """
        for root, dirs, files in os.walk(temp_dir):
            for d in dirs:
                path = os.path.join(root, d)
                if os.path.islink(path):
                     raise_question(QuestionType.AMU0_INTEGRITY, f"Symlink detected in AMU0: {path}")
            for f in files:
                path = os.path.join(root, f)
                if os.path.islink(path):
                     raise_question(QuestionType.AMU0_INTEGRITY, f"Symlink detected in AMU0: {path}")
                if f.endswith(".tmp"):
                     raise_question(QuestionType.AMU0_INTEGRITY, f"Temporary file detected in AMU0: {path}")
                if f in ["amu0_id.txt", "signature.sig"]:
                     raise_question(QuestionType.AMU0_INTEGRITY, f"Metadata file {f} found prematurely in AMU0")

    def _snapshot_filesystem(self, amu_dir: str, manifests_dir: str, mission_path: str) -> Dict[str, Any]:
        """
        Snapshot the filesystem state into AMU0.
        Returns the snapshot manifest.
        """
        # Create fs_snapshot directory
        fs_snapshot_dir = os.path.join(amu_dir, "fs_snapshot")
        os.makedirs(fs_snapshot_dir, exist_ok=True)

        # Copy Project Builder
        pb_src = "project_builder"
        if os.path.exists(pb_src):
            shutil.copytree(pb_src, os.path.join(amu_dir, "fs_snapshot", "project_builder"))
        else:
            self.logger.warning("Project Builder directory not found during snapshot.")
            
        # Copy COO
        coo_src = "coo"
        if os.path.exists(coo_src):
            shutil.copytree(coo_src, os.path.join(amu_dir, "fs_snapshot", "coo"))
            
        # Copy Manifests
        shutil.copytree(manifests_dir, os.path.join(amu_dir, "fs_snapshot", "manifests"))
        
        # Copy Reference Mission
        shutil.copy(mission_path, os.path.join(amu_dir, "phase3_reference_mission.json"))
        
        # Copy Governance Rules (D.2)
        rules_src = os.path.join(manifests_dir, "governance_ruleset.json")
        rules_frozen_path = os.path.join(amu_dir, "governance_rules_frozen.json")
        rules_hash = "MISSING"
        
        if os.path.exists(rules_src):
             shutil.copy(rules_src, rules_frozen_path)
             # Compute SHA (A.9)
             with open(rules_frozen_path, "rb") as f:
                 rules_hash = hashlib.sha256(f.read()).hexdigest()
        
        # Capture External Trace (R6.5 A4)
        trace_src = os.path.join(manifests_dir, "external_trace.jsonl")
        trace_dest = os.path.join(amu_dir, "external_trace.jsonl")
        if os.path.exists(trace_src):
            # Canonicalize (Sort by prompt_hash)
            entries = []
            with open(trace_src, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            raise GovernanceError("Invalid JSON in external_trace.jsonl")
            
            # Sort deterministically by prompt_hash
            entries.sort(key=lambda x: x.get("prompt_hash", ""))
            
            with open(trace_dest, "w", encoding="utf-8") as f:
                for entry in entries:
                    f.write(json.dumps(entry, sort_keys=True) + "\n")
        else:
            # Optional? If missing, Deep Replay won't work.
            # But we don't fail capture.
            pass
        
        # Create Snapshot Manifest
        snapshot_manifest = {
            "timestamp": "2025-11-28T00:00:00Z", # In real system, use actual time
            "contents": ["project_builder", "coo", "manifests", "phase3_reference_mission.json", "governance_rules_frozen.json", "external_trace.jsonl"],
            "governance_rules_sha256": rules_hash # A.9
        }
        with open(os.path.join(amu_dir, "snapshot_manifest.json"), "w") as f:
            json.dump(snapshot_manifest, f, sort_keys=True)
            
        # Normalize mtimes (A.10)
        # Set all files in amu_dir to 1980-01-01 00:00:00 UTC
        # timestamp: 315532800
        pinned_ts = 315532800
        for root, dirs, files in os.walk(amu_dir):
            for d in dirs:
                os.utime(os.path.join(root, d), (pinned_ts, pinned_ts))
            for f in files:
                os.utime(os.path.join(root, f), (pinned_ts, pinned_ts))
        os.utime(amu_dir, (pinned_ts, pinned_ts))
            
        # Generate Pinned Context
        # In a real scenario, this would capture current env/hardware state.
        # Here we copy from manifests or generate a default.
        env_manifest_path = os.path.join(manifests_dir, "environment_manifest.json")
        if os.path.exists(env_manifest_path):
             with open(env_manifest_path, "r") as f:
                 env_data = json.load(f)
        else:
            env_data = {}
            
        # Capture allowed env vars
        allowed_vars = env_data.get("allowed_env_vars", [])
        captured_env = {}
        if isinstance(allowed_vars, list):
            for k in allowed_vars:
                if k in os.environ:
                    captured_env[k] = os.environ[k]
        elif isinstance(allowed_vars, dict):
             # A.3: Fail on wrong type
             raise GovernanceError("environment_manifest.json: allowed_env_vars must be a list")
            
        # R6.3 B1: Capture REAL hardware context (no placeholders)
        try:
            hw_context = capture_hardware_context()
        except Exception as e:
            raise GovernanceError(f"Hardware capture failed during AMU0 snapshot: {e}")
        
        pinned_context = {
            "rng_seed": env_data.get("rng_seed", "DETERMINISTIC_SEED_DEFAULT"),
            "env_vars": captured_env,
            "mock_time": env_data.get("mock_time"),
            "kernel_version": hw_context["kernel_version"],  # R6.3 B1: Real capture
            "cpu_microcode": hw_context["cpu_microcode"]      # R6.3 B1: Real capture
        }
        
        with open(os.path.join(amu_dir, "pinned_context.json"), "w") as f:
            json.dump(pinned_context, f)
            
        return snapshot_manifest


