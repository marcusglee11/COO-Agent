"""
QUESTION mapping for governance errors.
Per R6.3 F3: Explicit mapping table for CONDITION → QUESTION_TYPE.
"""
from enum import Enum

class QuestionType(str, Enum):
    """
    Standardized question types for governance errors.
    
    R6.3 F3: Alignment Layer defines logical mapping,
    Runtime implements concrete table.
    """
    AMU0_INTEGRITY = "QUESTION_AMU0_INTEGRITY"
    HARDWARE_PINNING = "QUESTION_HARDWARE_PINNING"
    SANDBOX_SECURITY = "QUESTION_SANDBOX_SECURITY"
    KEY_MANAGEMENT = "QUESTION_KEY_MANAGEMENT"
    ROLLBACK_INTEGRITY = "QUESTION_ROLLBACK_INTEGRITY"
    GATE_FAILURE = "QUESTION_GATE_FAILURE"
    MIGRATION_FAILURE = "QUESTION_MIGRATION_FAILURE"
    FSM_STATE_ERROR = "QUESTION_FSM_STATE_ERROR"
    MANIFEST_VALIDATION = "QUESTION_MANIFEST_VALIDATION"
    # R6.4 Section H: Additional QUESTION types
    REPLAY_VERIFICATION = "QUESTION_REPLAY_VERIFICATION"
    ENVIRONMENT_PINNING = "QUESTION_ENVIRONMENT_PINNING"
    MODE_VIOLATION = "QUESTION_MODE_VIOLATION"
    KEY_INTEGRITY = "QUESTION_KEY_INTEGRITY"

def raise_question(question_type: QuestionType, message: str) -> None:
    """
    Raise a governance error with proper QUESTION mapping.
    
    R6.3 F3: Central helper for raising governance errors with
    consistent QUESTION type mapping.
    
    Args:
        question_type: The QuestionType enum value
        message: Detailed error message
        
    Raises:
        GovernanceError: With formatted question type prefix
        
    Usage:
        raise_question(QuestionType.AMU0_INTEGRITY, "Hash mismatch detected")
        # Raises: GovernanceError("QUESTION_AMU0_INTEGRITY: Hash mismatch detected")
    """
    from ..runtime.state_machine import GovernanceError
    raise GovernanceError(f"{question_type.value}: {message}")
