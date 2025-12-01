import os
import json
import pytest
from unittest.mock import patch, MagicMock, mock_open
from coo_runtime.runtime.rollback_log import RollbackLog, MAX_ROLLBACK_ENTRIES
from coo_runtime.runtime.state_machine import GovernanceError
from coo_runtime.util.questions import QuestionType

class TestR65RollbackIntegrity:
    """
    R6.5 C2: Rollback Integrity Tests
    """

    def setup_method(self):
        self.log = RollbackLog()

    def test_fail_closed_on_full(self):
        """
        R6.5 C2: Fail-closed when log is full.
        """
        # Mock loading MAX entries
        fake_entries = [{"sequence_number": i, "entry_hash": "h", "previous_hash": "p"} for i in range(MAX_ROLLBACK_ENTRIES)]
        
        with patch.object(self.log, '_load_and_verify_log', return_value=fake_entries):
            with pytest.raises(GovernanceError) as excinfo:
                self.log.append_entry("/tmp/amu0", {"data": "test"})
            
            assert "QUESTION_ROLLBACK_INTEGRITY" in str(excinfo.value)
            assert "Rollback log full" in str(excinfo.value)

    def test_integrity_failure_routing(self):
        """
        R6.5 C2: Signature mismatch -> QUESTION_ROLLBACK_INTEGRITY
        """
        # Mock file existence and content
        with patch('os.path.exists', return_value=True):
            with patch('os.path.getsize', return_value=100):
                with patch('builtins.open', mock_open(read_data=b"data")):
                    # Mock Signature verification failure
                    with patch('coo_runtime.util.crypto.Signature.verify_data', return_value=False):
                        with pytest.raises(GovernanceError) as excinfo:
                            self.log._load_and_verify_log("/tmp/amu0")
                        
                        assert "QUESTION_ROLLBACK_INTEGRITY" in str(excinfo.value)
                        assert "Signature Invalid" in str(excinfo.value)

    def test_hash_chain_failure_routing(self):
        """
        R6.5 C2: Hash chain broken -> QUESTION_ROLLBACK_INTEGRITY
        """
        # Mock valid signature
        with patch('os.path.exists', return_value=True):
            with patch('coo_runtime.util.crypto.Signature.verify_data', return_value=True):
                # Mock log content with broken chain
                entries = [
                    {"sequence_number": 1, "previous_hash": "0"*64, "entry_hash": "hash1", "timestamp": "t", "payload": {}},
                    {"sequence_number": 2, "previous_hash": "WRONG_HASH", "entry_hash": "hash2", "timestamp": "t", "payload": {}}
                ]
                log_content = "\n".join(json.dumps(e) for e in entries)
                
                with patch('builtins.open', mock_open(read_data=log_content)):
                    # Mock hashlib to return "hash1" then "hash2"
                    mock_hash = MagicMock()
                    mock_hash.hexdigest.side_effect = ["hash1", "hash2"]
                    with patch('hashlib.sha256', return_value=mock_hash):
                        with pytest.raises(GovernanceError) as excinfo:
                            self.log._load_and_verify_log("/tmp/amu0")
                        
                        assert "QUESTION_ROLLBACK_INTEGRITY" in str(excinfo.value)
                        assert "Hash Chain Broken" in str(excinfo.value)
