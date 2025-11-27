import unittest
from coo_runtime.runtime.state_machine import RuntimeFSM, RuntimeState, GovernanceError

class TestDeterminism(unittest.TestCase):
    def setUp(self):
        self.fsm = RuntimeFSM()

    def test_initial_state(self):
        self.assertEqual(self.fsm.current_state, RuntimeState.INIT)

    def test_valid_transitions(self):
        """Verify the strict linear progression."""
        self.fsm.transition_to(RuntimeState.AMENDMENT_PREP)
        self.assertEqual(self.fsm.current_state, RuntimeState.AMENDMENT_PREP)
        
        self.fsm.transition_to(RuntimeState.AMENDMENT_EXEC)
        self.assertEqual(self.fsm.current_state, RuntimeState.AMENDMENT_EXEC)

    def test_invalid_transition_halts(self):
        """Verify invalid transition triggers ERROR state."""
        with self.assertRaises(GovernanceError):
            self.fsm.transition_to(RuntimeState.COMPLETE) # Invalid jump
        
        self.assertEqual(self.fsm.current_state, RuntimeState.ERROR)

    def test_history_tracking(self):
        self.fsm.transition_to(RuntimeState.AMENDMENT_PREP)
        self.assertEqual(self.fsm.history, [RuntimeState.INIT, RuntimeState.AMENDMENT_PREP])

if __name__ == '__main__':
    unittest.main()
