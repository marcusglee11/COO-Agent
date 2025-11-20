from typing import Any, AsyncGenerator, Dict, List

from coo.agents.base import Agent, Emission
from coo.models import MessageKind


class DummyCOO(Agent):
    name = "COO"

    async def process_stream(
        self, mission: Dict[str, Any], messages: List[Dict[str, Any]]
    ) -> AsyncGenerator[Emission, None]:
        # Simple plan: if we get a task, send task to Engineer
        if messages and messages[0]["kind"] == MessageKind.TASK.value:
            yield Emission(
                type="message",
                data={
                    "to_agent": "Engineer",
                    "kind": MessageKind.TASK.value,
                    "body_json": {"action": "implement", "summary": "Do the work"},
                },
            )
            yield Emission(type="side_effect", data={"state_transition": "planning"})
        else:
            # If result from QA, complete mission
            last_msg = messages[-1]
            if (
                last_msg["from_agent"] == "QA"
                and last_msg["kind"] == MessageKind.RESULT.value
            ):
                yield Emission(
                    type="side_effect", data={"state_transition": "completed"}
                )


class DummyEngineer(Agent):
    name = "Engineer"

    async def process_stream(
        self, mission: Dict[str, Any], messages: List[Dict[str, Any]]
    ) -> AsyncGenerator[Emission, None]:
        # Receive task, emit sandbox execution request
        # We'll use a hardcoded ID that the test will populate or we assume it's created.
        # For the E2E test, we will pre-seed the artifact in the DB.
        artifact_id = "test_artifact_1"
        
        yield Emission(
            type="sandbox_execute",
            data={
                "artifact_id": artifact_id,
                "entrypoint": "python main.py",
                "timeout": 10,
                "dedupe_id": f"run_{messages[-1]['id']}",
                "reply_to": "QA"
            }
        )


class DummyQA(Agent):
    name = "QA"

    async def process_stream(
        self, mission: Dict[str, Any], messages: List[Dict[str, Any]]
    ) -> AsyncGenerator[Emission, None]:
        # Receive result, approve and send result to COO
        last_msg = messages[-1]
        if last_msg["kind"] == MessageKind.RESULT.value:
            yield Emission(
                type="message",
                data={
                    "to_agent": "COO",
                    "kind": MessageKind.RESULT.value,
                    "body_json": {"action": "approved", "summary": "Looks good"},
                },
            )
