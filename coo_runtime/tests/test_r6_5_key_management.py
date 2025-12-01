import os
import pytest
from unittest.mock import patch, mock_open
from nacl.signing import SigningKey
from coo_runtime.util.crypto import Signature, CryptoError, load_keys, _CEO_PRIVATE_KEY, _CEO_PUBLIC_KEY

class TestR65KeyManagement:
    """
    R6.5 G2: Key Management Tests
    """

    def setup_method(self):
        # Generate fresh keys for testing
        self.signing_key = SigningKey.generate()
        self.verify_key = self.signing_key.verify_key
        self.priv_bytes = self.signing_key.encode()
        self.pub_bytes = self.verify_key.encode()

    def test_signature_api_rejects_paths(self):
        """
        R6.5 G2: Signature API must reject private key paths at call boundary.
        """
        # Even if keys are loaded, passing a path MUST fail
        with patch('coo_runtime.util.crypto._CEO_PRIVATE_KEY', self.signing_key):
             with pytest.raises(CryptoError, match="R6.5 G2 Violation"):
                 Signature.sign_data(b"test", private_key_path="/tmp/fake.key")

        with patch('coo_runtime.util.crypto._CEO_PUBLIC_KEY', self.verify_key):
             with pytest.raises(CryptoError, match="R6.5 G2 Violation"):
                 Signature.verify_data(b"test", b"sig", public_key_path="/tmp/fake.pub")

    def test_load_keys_from_env(self):
        """
        Verify load_keys() correctly loads from environment variables.
        """
        with patch.dict(os.environ, {
            'CEO_PRIVATE_KEY_PATH': '/tmp/priv.key',
            'CEO_PUBLIC_KEY_PATH': '/tmp/pub.key'
        }):
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open()) as m:
                    # Mock file reads to return our key bytes
                    m.side_effect = [
                        mock_open(read_data=self.priv_bytes).return_value,
                        mock_open(read_data=self.pub_bytes).return_value
                    ]
                    
                    load_keys()
                    
                    # Verify keys are loaded in module
                    from coo_runtime.util import crypto
                    assert crypto._CEO_PRIVATE_KEY is not None
                    assert crypto._CEO_PUBLIC_KEY is not None
                    
                    # Verify we can sign/verify without paths
                    sig = Signature.sign_data(b"test_message")
                    assert Signature.verify_data(b"test_message", sig)

    def test_fail_without_init(self):
        """
        Verify signing fails if keys are not loaded (and no path provided).
        """
        # Ensure keys are unloaded
        from coo_runtime.util import crypto
        crypto._CEO_PRIVATE_KEY = None
        crypto._CEO_PUBLIC_KEY = None
        
        with pytest.raises(CryptoError, match="Keys not loaded"):
            Signature.sign_data(b"test")
