import pytest
from unittest.mock import patch, MagicMock
from coo_runtime.util.context import _verify_time_pinning, _verify_hardware_context
from coo_runtime.runtime.state_machine import GovernanceError
from coo_runtime.util.questions import QuestionType

class TestR65SubprocessIsolation:
    """
    R6.5 F1/F2: Subprocess Isolation Tests
    """

    def test_verify_time_pinning_uses_pinned_subprocess(self):
        """
        R6.5 F2: _verify_time_pinning MUST use run_pinned_subprocess.
        """
        amu0_path = "/tmp/amu0"
        expected_time = "2025-11-28T00:00:00Z"
        expected_ts = 1764288000.0
        
        # Mock successful run
        mock_result = MagicMock()
        mock_result.stdout = str(expected_ts)
        
        with patch('coo_runtime.util.context.run_pinned_subprocess', return_value=mock_result) as mock_run:
            _verify_time_pinning(amu0_path, expected_time)
            
            assert mock_run.called
            assert mock_run.call_args[0][1] == amu0_path # Check amu0_path passed

    def test_verify_time_pinning_failure_routing(self):
        """
        R6.5 F2: Time drift -> QUESTION_ENVIRONMENT_PINNING
        """
        amu0_path = "/tmp/amu0"
        expected_time = "2025-11-28T00:00:00Z"
        expected_ts = 1764288000.0
        
        # Mock drift
        mock_result = MagicMock()
        mock_result.stdout = str(expected_ts + 5.0) # 5s drift
        
        with patch('coo_runtime.util.context.run_pinned_subprocess', return_value=mock_result):
            with pytest.raises(GovernanceError) as excinfo:
                _verify_time_pinning(amu0_path, expected_time)
            
            assert "QUESTION_ENVIRONMENT_PINNING" in str(excinfo.value)
            assert "Time pinning verification failed" in str(excinfo.value)

    def test_hardware_verification_routing(self):
        """
        R6.5 D2: Hardware mismatch -> QUESTION_HARDWARE_PINNING
        """
        pinned_context = {
            "kernel_version": "Linux 6.8",
            "cpu_microcode": "0x123"
        }
        
        # Mock mismatch
        current_hw = {
            "kernel_version": "Linux 6.9", # Mismatch
            "cpu_microcode": "0x123"
        }
        
        with patch('coo_runtime.util.context.capture_hardware_context', return_value=current_hw):
            with pytest.raises(GovernanceError) as excinfo:
                _verify_hardware_context(pinned_context)
            
            assert "QUESTION_HARDWARE_PINNING" in str(excinfo.value)
            assert "Kernel version mismatch" in str(excinfo.value)
