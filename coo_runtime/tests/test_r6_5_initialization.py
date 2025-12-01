import pytest
from unittest.mock import patch, MagicMock
from coo_runtime.runtime.init import initialize_runtime, assert_initialized, _initialized_amu0_path
from coo_runtime.runtime.state_machine import GovernanceError
import coo_runtime.runtime.init as init_module

class TestR65Initialization:
    """
    R6.5 E1/E2: Initialization & Determinism Tests
    """

    def setup_method(self):
        # Reset initialization state
        init_module._initialized_amu0_path = None

    def tearDown(self):
        init_module._initialized_amu0_path = None

    def test_initialization_flow(self):
        """
        R6.5 E1: initialize_runtime flow.
        """
        amu0_path = "/tmp/amu0"
        
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", MagicMock()), \
             patch("json.load", return_value={}), \
             patch("coo_runtime.util.context._verify_hardware_context"), \
             patch("coo_runtime.util.crypto.load_keys"), \
             patch("coo_runtime.runtime.init._verify_time_pinning"):
            
            # First call
            initialize_runtime(amu0_path)
            assert init_module._initialized_amu0_path == amu0_path
            
            # Second call (Idempotent)
            initialize_runtime(amu0_path)
            assert init_module._initialized_amu0_path == amu0_path

    def test_reinitialization_failure(self):
        """
        R6.5 E1: Re-initialization with different path fails.
        """
        amu0_path1 = "/tmp/amu0_1"
        amu0_path2 = "/tmp/amu0_2"
        
        # Manually set state
        init_module._initialized_amu0_path = amu0_path1
        
        with pytest.raises(GovernanceError) as excinfo:
            initialize_runtime(amu0_path2)
        
        assert "Runtime already initialized" in str(excinfo.value)

    def test_assert_initialized_enforcement(self):
        """
        R6.5 E2: assert_initialized raises error if not initialized.
        """
        # Ensure not initialized
        init_module._initialized_amu0_path = None
        
        with pytest.raises(GovernanceError) as excinfo:
            assert_initialized()
        
        assert "Runtime not initialized" in str(excinfo.value)
        
        # Initialize and verify pass
        init_module._initialized_amu0_path = "/tmp/amu0"
        assert_initialized() # Should not raise
