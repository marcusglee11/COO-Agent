import asyncio
from pathlib import Path

import pytest
import pytest_asyncio

from coo.budget import BudgetTracker
from coo.message_store import MessageStore
from coo.models import MessageKind
from coo.orchestrator import Orchestrator


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = tmp_path / "test_coo_e2e.db"
    store = MessageStore(db_path)
    await store.initialize()
    return store


@pytest.mark.asyncio
async def test_orchestrator_flow(store):
    config = {"tick_interval_seconds": 0.1}
    
    # Mock agents to avoid real LLM calls
    from coo.agents.dummy_agents import DummyCOO, DummyEngineer, DummyQA
    
    orchestrator = Orchestrator(store, config)
    # Swap real agents with dummy agents for this test
    orchestrator.agents = {
        "COO": DummyCOO("COO"),
        "Engineer": DummyEngineer("Engineer"),
        "QA": DummyQA("QA"),
    }

    # Create mission
    mission_id = "m_1"
    await store.create_mission({"id": mission_id, "description": "Test Mission"})

    # Inject initial task for COO
    await store.deliver_message(
        {
            "id": "msg_init",
            "mission_id": mission_id,
            "from_agent": "CEO",
            "to_agent": "COO",
            "kind": MessageKind.TASK.value,
            "body_json": {"task": "Start mission"},
        }
    )

    # Start orchestrator in background
    task = asyncio.create_task(orchestrator.run())

    # Wait a bit for orchestrator to start
    await asyncio.sleep(0.2)

    # Verify COO picked up the message and sent task to Engineer

    # Wait for message to appear
    for _ in range(10):
        await asyncio.sleep(0.1)
        messages = await store.claim_pending_messages("Engineer", mission_id)
        if messages:
            # Found message for Engineer!
            msg = messages[0]
            assert msg["from_agent"] == "COO"
            assert msg["kind"] == MessageKind.TASK.value
            break
        await asyncio.sleep(0.2)

    # Stop orchestrator
    orchestrator.running = False
    await task

    # Check messages in DB
    import aiosqlite

    async with aiosqlite.connect(store.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM messages WHERE mission_id = ?", (mission_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            msgs = [dict(row) for row in rows]

    # We expect:
    # 1. COO -> Engineer (TASK)
    # 2. Engineer -> QA (TASK)
    # 3. QA -> COO (RESULT)

    # Since we stopped the orchestrator early, we might not have all of them.
    # Let's run the orchestrator for a bit longer to let the chain complete.


@pytest.mark.asyncio
async def test_full_chain(store):
    config = {"tick_interval_seconds": 0.1}
    orchestrator = Orchestrator(store, config)
    
    # Mock agents to avoid real LLM calls
    from coo.agents.dummy_agents import DummyCOO, DummyEngineer, DummyQA
    orchestrator.agents = {
        "COO": DummyCOO("COO"),
        "Engineer": DummyEngineer("Engineer"),
        "QA": DummyQA("QA"),
    }
    
    # Mock SandboxRunner to avoid Docker dependency
    from unittest.mock import AsyncMock, MagicMock
    orchestrator.sandbox = AsyncMock()
    mock_result = MagicMock()
    mock_result.exit_code = 0
    mock_result.stdout = "Mock Output"
    mock_result.stderr = ""
    mock_result.result_artifact_id = "res_1"
    mock_result.error_class = None
    mock_result.cached = False
    orchestrator.sandbox.run_artifact.return_value = mock_result

    mission_id = "m_1"
    await store.create_mission({"id": mission_id, "description": "Test Mission"})

    # Seed artifact for DummyEngineer
    import aiosqlite
    import base64
    async with aiosqlite.connect(store.db_path) as db:
        await db.execute(
            "INSERT INTO artifacts (id, mission_id, content_b64, created_at, created_by) VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)",
            ("test_artifact_1", mission_id, base64.b64encode(b"print('Hello')").decode(), "Engineer")
        )
        await db.commit()

    # Inject initial task for COO
    await store.deliver_message(
        {
            "id": "msg_init_2",
            "mission_id": mission_id,
            "from_agent": "CEO",
            "to_agent": "COO",
            "kind": MessageKind.TASK.value,
            "body_json": {"task": "Start mission"},
        }
    )

    task = asyncio.create_task(orchestrator.run())

    # Wait for chain to complete: COO -> Engineer -> QA -> COO
    # Total 3 messages generated.

    max_retries = 20
    for _ in range(max_retries):
        import aiosqlite

        async with aiosqlite.connect(store.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM messages WHERE mission_id = ?", (mission_id,)
            ) as cursor:
                count = (await cursor.fetchone())[0]
                if count >= 3:
                    break
        await asyncio.sleep(0.2)

    orchestrator.running = False
    await task

    async with aiosqlite.connect(store.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT from_agent, to_agent, kind FROM messages WHERE mission_id = ? ORDER BY created_at",
            (mission_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            msgs = [dict(row) for row in rows]

    assert len(msgs) >= 4
    assert msgs[0]["from_agent"] == "CEO" and msgs[0]["to_agent"] == "COO"
    assert msgs[1]["from_agent"] == "COO" and msgs[1]["to_agent"] == "Engineer"
    assert msgs[2]["from_agent"] == "SYSTEM_SANDBOX" and msgs[2]["to_agent"] == "QA"
    assert msgs[3]["from_agent"] == "QA" and msgs[3]["to_agent"] == "COO"
