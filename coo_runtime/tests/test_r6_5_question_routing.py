import pytest
from unittest.mock import patch, MagicMock
from coo_runtime.runtime.state_machine import RuntimeFSM, RuntimeState, GovernanceError
from coo_runtime.runtime.gates import GateKeeper
from coo_runtime.runtime.replay import ReplayEngine
from coo_runtime.runtime.migration import MigrationEngine
from coo_runtime.util.questions import QuestionType

class TestR65QuestionRouting:
    """
    R6.5 H1: QUESTION Routing Tests
    """

    def test_gate_failure_routing(self):
        """
        Verify Gate failures route to QUESTION_GATE_FAILURE / MODE_VIOLATION / SANDBOX_SECURITY.
        """
        fsm = RuntimeFSM()
        fsm._RuntimeFSM__current_state = RuntimeState.GATES
        gate_keeper = GateKeeper(fsm)
        
        # Gate A: Missing COO root -> GATE_FAILURE
        with patch("os.path.exists", return_value=False):
            with pytest.raises(GovernanceError) as excinfo:
                gate_keeper._gate_a_repo_unification("/missing/coo")
            assert "QUESTION_GATE_FAILURE" in str(excinfo.value)

        # Gate B: Forbidden Import -> MODE_VIOLATION
        with patch("os.walk", return_value=[("/root", [], ["bad.py"])]), \
             patch("builtins.open", MagicMock()), \
             patch("ast.parse") as mock_parse:
            
            # Mock AST with forbidden import
            import ast
            mock_node = ast.Import(names=[ast.alias(name='random', asname=None)])
            mock_parse.return_value = MagicMock(body=[mock_node])
            # We need to mock ast.walk to yield the node
            with patch("ast.walk", return_value=[mock_node]):
                with pytest.raises(GovernanceError) as excinfo:
                    gate_keeper._gate_b_deterministic_modules("/root")
                assert "QUESTION_MODE_VIOLATION" in str(excinfo.value)

        # Gate D: Sandbox SHA Mismatch -> SANDBOX_SECURITY
        with patch("os.path.exists", return_value=True), \
             patch("json.load", return_value={"image_sha256": "sha256:expected"}), \
             patch("builtins.open", MagicMock()), \
             patch("coo_runtime.util.amu0_utils.resolve_amu0_path", return_value="/amu0"), \
             patch("coo_runtime.runtime.gates.run_pinned_subprocess") as mock_run:
            
            mock_run.return_value = MagicMock(stdout="sha256:actual")
            with pytest.raises(GovernanceError) as excinfo:
                gate_keeper._gate_d_sandbox_security("/manifests")
            assert "QUESTION_SANDBOX_SECURITY" in str(excinfo.value)

    def test_replay_verification_routing(self):
        """
        Verify Replay failures route to QUESTION_REPLAY_VERIFICATION.
        """
        fsm = RuntimeFSM()
        fsm._RuntimeFSM__current_state = RuntimeState.GATES
        replay_engine = ReplayEngine(fsm)
        
        # Output mismatch -> REPLAY_VERIFICATION
        with patch("coo_runtime.runtime.replay.ReplayEngine._verify_reference_mission"), \
             patch("coo_runtime.runtime.replay.initialize_runtime"), \
             patch("coo_runtime.runtime.replay.ReplayEngine._run_mission", side_effect=["out1", "out2"]), \
             patch("coo_runtime.runtime.replay.ReplayEngine._compare_outputs", return_value=False):
            
            with pytest.raises(GovernanceError) as excinfo:
                replay_engine.execute_replay("mission", "amu0")
            assert "QUESTION_REPLAY_VERIFICATION" in str(excinfo.value)

    def test_migration_failure_routing(self):
        """
        Verify Migration failures route to QUESTION_MIGRATION_FAILURE.
        """
        fsm = RuntimeFSM()
        rollback = MagicMock()
        migration_engine = MigrationEngine(fsm, rollback)
        fsm._RuntimeFSM__current_state = RuntimeState.MIGRATION_SEQUENCE
        
        # Test runner missing -> MIGRATION_FAILURE
        # We need to mock _run_tests to raise the error, or call it directly.
        # Calling _run_tests directly is easier.
        with patch("os.path.exists", return_value=False):
            with pytest.raises(GovernanceError) as excinfo:
                migration_engine._run_tests("/missing/runner")
            assert "QUESTION_MIGRATION_FAILURE" in str(excinfo.value)

    def test_fsm_state_error_routing(self):
        """
        Verify FSM errors route to QUESTION_FSM_STATE_ERROR / KEY_INTEGRITY.
        """
        fsm = RuntimeFSM()
        
        # Invalid transition -> FSM_STATE_ERROR
        with pytest.raises(GovernanceError) as excinfo:
            fsm.transition_to(RuntimeState.COMPLETE) # Invalid from INIT
        assert "QUESTION_FSM_STATE_ERROR" in str(excinfo.value)
        
        # Checkpoint signing failure -> KEY_INTEGRITY
        fsm._RuntimeFSM__current_state = RuntimeState.GATES
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", MagicMock()), \
             patch("json.load", return_value={"mock_time": "1000"}), \
             patch("coo_runtime.util.crypto.Signature.sign_data", side_effect=Exception("Sign fail")):
            
            with pytest.raises(GovernanceError) as excinfo:
                fsm.checkpoint_state("ckpt", "/amu0")
            assert "QUESTION_KEY_INTEGRITY" in str(excinfo.value)
