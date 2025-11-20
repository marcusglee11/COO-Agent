from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MessageKind(str, Enum):
    TASK = "TASK"
    RESULT = "RESULT"
    STREAM = "STREAM"
    ERROR = "ERROR"
    APPROVAL = "APPROVAL"
    SANDBOX_EXECUTE = "SANDBOX_EXECUTE"
    CONTROL = "CONTROL"
    QUESTION = "QUESTION"
    SYSTEM = "SYSTEM"


class MessageStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXPIRED = "expired"


class Message(BaseModel):
    id: str
    schema_version: int = 1
    from_agent: str
    to_agent: str
    mission_id: str
    conversation_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    priority: int = 5
    kind: MessageKind
    status: MessageStatus = MessageStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    timeout_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    body_json: Dict[str, Any]
    correlation_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MissionStatus(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    PAUSED_BUDGET = "paused_budget"
    PAUSED_APPROVAL = "paused_approval"
    PAUSED_ERROR = "paused_error"
    PAUSED_MANUAL = "paused_manual"
    COMPLETED = "completed"
    FAILED = "failed"


class Mission(BaseModel):
    id: str
    status: MissionStatus
    description: str
    max_cost_usd: float
    max_loops: int
    priority: int = 5
    budget_increase_requests: int = 0
    config_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    spent_cost_usd: float = 0.0
    loop_count: int = 0
    message_count: int = 0

    model_config = ConfigDict(from_attributes=True)
