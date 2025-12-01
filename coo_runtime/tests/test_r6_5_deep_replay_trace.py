import pytest
import os
import json
import shutil
import tempfile
from unittest.mock import patch, MagicMock
from coo_runtime.runtime.amu_capture import AMUCapture
from coo_runtime.util import amu0_utils

class TestR65DeepReplayTrace:
    """
    R6.5 A4: Deep Replay Trace Tests
    """

    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.manifests_dir = os.path.join(self.test_dir, "manifests")
        os.makedirs(self.manifests_dir)
        self.mission_path = os.path.join(self.test_dir, "mission.json")
        with open(self.mission_path, "w") as f:
            f.write("{}")
            
        # Create dummy manifests
        with open(os.path.join(self.manifests_dir, "environment_manifest.json"), "w") as f:
            json.dump({"allowed_env_vars": [], "rng_seed": 123, "mock_time": "1000"}, f)
        with open(os.path.join(self.manifests_dir, "sandbox_manifest.json"), "w") as f:
            json.dump({"image_sha256": "sha256:123"}, f)
        with open(os.path.join(self.manifests_dir, "governance_ruleset.json"), "w") as f:
            f.write("{}")

    def teardown_method(self):
        shutil.rmtree(self.test_dir)
        if os.path.exists("active_amu0_path.json"):
            os.remove("active_amu0_path.json")
        if os.path.exists("active_amu0_path.json.sig"):
            os.remove("active_amu0_path.json.sig")

    def test_trace_capture_and_canonicalization(self):
        """
        Verify external_trace.jsonl is captured, sorted, and included in AMU0.
        """
        # Create unsorted external_trace.jsonl
        trace_path = os.path.join(self.manifests_dir, "external_trace.jsonl")
        unsorted_entries = [
            {"prompt_hash": "bbb", "response": "2"},
            {"prompt_hash": "aaa", "response": "1"},
            {"prompt_hash": "ccc", "response": "3"}
        ]
        with open(trace_path, "w") as f:
            for entry in unsorted_entries:
                f.write(json.dumps(entry) + "\n")

        capture = AMUCapture()
        
        # Mock dependencies
        with patch("coo_runtime.util.context.capture_hardware_context", return_value={"kernel_version": "1", "cpu_microcode": "1"}), \
             patch("coo_runtime.util.subprocess.run_pinned_subprocess") as mock_run, \
             patch("coo_runtime.util.crypto.Signature.sign_data", return_value=b"sig"), \
             patch("coo_runtime.util.crypto.Signature.verify_data", return_value=True):
            
            mock_run.return_value = MagicMock(stdout="commit_hash")
            
            amu_dir = capture.capture_amu0(self.manifests_dir, self.mission_path)
            
            # 1. Verify file exists in AMU0
            captured_trace_path = os.path.join(amu_dir, "external_trace.jsonl")
            assert os.path.exists(captured_trace_path)
            
            # 2. Verify Canonicalization (Sorted)
            with open(captured_trace_path, "r") as f:
                lines = f.readlines()
                entries = [json.loads(line) for line in lines]
                
            assert entries[0]["prompt_hash"] == "aaa"
            assert entries[1]["prompt_hash"] == "bbb"
            assert entries[2]["prompt_hash"] == "ccc"
            
            # 3. Verify Snapshot Manifest inclusion
            with open(os.path.join(amu_dir, "snapshot_manifest.json"), "r") as f:
                manifest = json.load(f)
            assert "external_trace.jsonl" in manifest["contents"]
            
            # Clean up AMU dir
            shutil.rmtree(amu_dir)
