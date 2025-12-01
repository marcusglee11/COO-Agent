import os
import json
import pytest
from unittest.mock import patch, MagicMock, mock_open
from coo_runtime.util.amu0_utils import resolve_amu0_path
from coo_runtime.runtime.state_machine import GovernanceError
from coo_runtime.util.questions import QuestionType

class TestR65TrackerSigning:
    """
    R6.5 B2: Tracker Signing Tests
    """

    def test_tracker_signature_mismatch(self):
        """
        R6.5 B2: Signature mismatch -> QUESTION_ROLLBACK_INTEGRITY
        """
        tracker_data = {
            "amu0_path": "amu0_ID",
            "amu0_id": "ID",
            "created_at": "t",
            "repo_commit": "c"
        }
        tracker_json = json.dumps(tracker_data)
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=tracker_json)), \
             patch('coo_runtime.util.crypto.Signature.verify_data', return_value=False):
            
            with pytest.raises(GovernanceError) as excinfo:
                resolve_amu0_path()
            
            assert "QUESTION_ROLLBACK_INTEGRITY" in str(excinfo.value)
            assert "Active AMU0 tracker signature invalid" in str(excinfo.value)

    def test_tracker_id_mismatch(self):
        """
        R6.5 B2: ID mismatch -> QUESTION_ROLLBACK_INTEGRITY
        """
        tracker_data = {
            "amu0_path": "amu0_ID",
            "amu0_id": "ID_TRACKER",
            "created_at": "t",
            "repo_commit": "c"
        }
        tracker_json = json.dumps(tracker_data)
        
        # Mock successful signature verify
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=tracker_json)), \
             patch('coo_runtime.util.crypto.Signature.verify_data', return_value=True), \
             patch('os.path.isabs', return_value=True), \
             patch('coo_runtime.util.amu0_utils.verify_amu0_complete') as mock_verify:
            
            # Mock verification result with DIFFERENT ID
            mock_verify.return_value = MagicMock(amu0_id="ID_DERIVED")
            
            with pytest.raises(GovernanceError) as excinfo:
                resolve_amu0_path()
            
            assert "QUESTION_ROLLBACK_INTEGRITY" in str(excinfo.value)
            assert "AMU0 ID mismatch" in str(excinfo.value)

    def test_missing_signature_file(self):
        """
        R6.5 B2: Missing signature file -> QUESTION_ROLLBACK_INTEGRITY
        """
        # Mock tracker exists but signature does not
        def exists_side_effect(path):
            if "active_amu0_path.json.sig" in path:
                return False
            return True
            
        with patch('os.path.exists', side_effect=exists_side_effect):
            with pytest.raises(GovernanceError) as excinfo:
                resolve_amu0_path()
            
            assert "QUESTION_ROLLBACK_INTEGRITY" in str(excinfo.value)
            assert "signature (active_amu0_path.json.sig) not found" in str(excinfo.value)
