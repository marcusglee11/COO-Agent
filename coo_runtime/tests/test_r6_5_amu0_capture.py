import os
import pytest
from unittest.mock import patch, MagicMock, call
from coo_runtime.runtime.amu_capture import AMUCapture
from coo_runtime.runtime.state_machine import GovernanceError
from coo_runtime.util.questions import QuestionType

class TestR65AMU0Capture:
    """
    R6.5 A3: AMU0 Capture Tests
    """

    def setup_method(self):
        self.capture = AMUCapture()

    def test_atomic_capture_flow(self):
        """
        R6.5 A3: Verify atomic capture flow (temp -> verify -> sign -> rename -> verify).
        """
        with patch('os.makedirs'), \
             patch('os.path.abspath', side_effect=lambda x: x), \
             patch('coo_runtime.runtime.amu_capture.AMUCapture._validate_manifests'), \
             patch('coo_runtime.runtime.amu_capture.AMUCapture._snapshot_filesystem', return_value={"timestamp": "t"}), \
             patch('builtins.open', MagicMock()), \
             patch('coo_runtime.runtime.amu_capture.AMUCapture._verify_amu0_temp_hygiene') as mock_hygiene, \
             patch('coo_runtime.util.amu0_utils.calculate_canonical_hash', side_effect=["hash1", "hash1"]) as mock_hash, \
             patch('coo_runtime.util.amu0_utils.derive_amu0_id', return_value="ID"), \
             patch('coo_runtime.util.crypto.Signature.sign_data', return_value=b"sig"), \
             patch('os.rename') as mock_rename, \
             patch('coo_runtime.runtime.amu_capture.run_pinned_subprocess', return_value=MagicMock(stdout="commit")), \
             patch('os.path.exists', return_value=False): # For amu_dir check

            self.capture.capture_amu0("/manifests", "/mission")

            # Verify Hygiene Called on Temp
            assert mock_hygiene.called
            
            # Verify Hash Calculated on Temp (first call)
            assert "temp_amu0_" in mock_hash.call_args_list[0][0][0]
            
            # Verify Rename Called
            assert mock_rename.called
            
            # Verify Hash Calculated on Final (second call)
            assert "amu0_ID" in mock_hash.call_args_list[1][0][0]

    def test_hygiene_failure_symlink(self):
        """
        R6.5 A3: Hygiene check fails on symlink.
        """
        with patch('os.walk', return_value=[("/tmp", [], ["link"])]), \
             patch('os.path.join', return_value="/tmp/link"), \
             patch('os.path.islink', return_value=True):
            
            with pytest.raises(GovernanceError) as excinfo:
                self.capture._verify_amu0_temp_hygiene("/tmp")
            
            assert "QUESTION_AMU0_INTEGRITY" in str(excinfo.value)
            assert "Symlink detected" in str(excinfo.value)

    def test_post_promotion_hash_mismatch(self):
        """
        R6.5 A3: Post-promotion hash mismatch -> QUESTION_AMU0_INTEGRITY.
        """
        with patch('os.makedirs'), \
             patch('os.path.abspath', side_effect=lambda x: x), \
             patch('coo_runtime.runtime.amu_capture.AMUCapture._validate_manifests'), \
             patch('coo_runtime.runtime.amu_capture.AMUCapture._snapshot_filesystem', return_value={"timestamp": "t"}), \
             patch('builtins.open', MagicMock()), \
             patch('coo_runtime.runtime.amu_capture.AMUCapture._verify_amu0_temp_hygiene'), \
             patch('coo_runtime.util.amu0_utils.calculate_canonical_hash', side_effect=["hash1", "hash2"]), \
             patch('coo_runtime.util.amu0_utils.derive_amu0_id', return_value="ID"), \
             patch('coo_runtime.util.crypto.Signature.sign_data', return_value=b"sig"), \
             patch('os.rename'), \
             patch('os.path.exists', return_value=False):

            with pytest.raises(GovernanceError) as excinfo:
                self.capture.capture_amu0("/manifests", "/mission")
            
            assert "QUESTION_AMU0_INTEGRITY" in str(excinfo.value)
            assert "Post-promotion canonical hash mismatch" in str(excinfo.value)
