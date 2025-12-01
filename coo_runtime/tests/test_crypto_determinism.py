import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
from coo_runtime.util.crypto import create_signature_metadata

class TestCryptoDeterminism(unittest.TestCase):
    @patch("coo_runtime.runtime.init.get_initialized_amu0_path")
    @patch("coo_runtime.util.context.get_pinned_time")
    @patch("coo_runtime.util.crypto._get_public_key")
    def test_metadata_time_pinning(self, mock_get_key, mock_get_time, mock_get_path):
        # Setup
        mock_get_path.return_value = "/tmp/amu0"
        pinned_time = datetime(2025, 1, 1, 12, 0, 0)
        mock_get_time.return_value = pinned_time
        
        # Mock key
        mock_vk = MagicMock()
        mock_vk.encode.return_value = b"key"
        mock_get_key.return_value = mock_vk
        
        # Execute
        metadata = create_signature_metadata()
        
        # Verify
        expected_ts = "2025-01-01T12:00:00Z"
        self.assertEqual(metadata["timestamp"], expected_ts)
        print(f"\nTestCryptoDeterminism: Timestamp pinned to {expected_ts}")

if __name__ == "__main__":
    unittest.main()
