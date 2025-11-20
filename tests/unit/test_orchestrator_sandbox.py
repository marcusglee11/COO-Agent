import asyncio
import pytest
import pytest_asyncio
import base64
from coo.message_store import MessageStore
from coo.budget import BudgetTracker
from coo.orchestrator import Orchestrator
from coo.models import MessageKind
import aiosqlite

@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = tmp_path / "test_coo_e2e.db"
    store = MessageStore(db_path)
    await store.initialize()
    return store

@pytest.mark.asyncio
async def test_orchestrator_sandbox_flow(store):
    config = {
        "tick_interval_seconds": 0.1,
        "sandbox": {"temp_dir": "test_sandbox_e2e"}
    }
    orchestrator = Orchestrator(store, config)
    
    # Use DummyAgents to avoid real LLM calls
    from coo.agents.dummy_agents import DummyCOO, DummyEngineer, DummyQA
    orchestrator.agents = {
        "COO": DummyCOO("COO"),
        "Engineer": DummyEngineer("Engineer"),
        "QA": DummyQA("QA"),
    }
    
    mission_id = "m_1"
    await store.create_mission({"id": mission_id, "description": "Test Mission"})
    
    # Pre-seed the artifact that DummyEngineer will request
    artifact_id = "test_artifact_1"
    script_content = 'print("Hello from Sandbox")'
    async with aiosqlite.connect(store.db_path) as db:
        await db.execute(
            "INSERT INTO artifacts (id, mission_id, filename, content_b64, created_at, created_by) VALUES (?, ?, 'main.py', ?, CURRENT_TIMESTAMP, 'setup')",
            (artifact_id, mission_id, base64.b64encode(script_content.encode()).decode())
        )
        await db.commit()
    
    # Inject initial task for COO
    await store.deliver_message({
        "id": "msg_init",
        "mission_id": mission_id,
        "from_agent": "CEO",
        "to_agent": "COO",
        "kind": MessageKind.TASK.value,
        "body_json": {"task": "Run code"}
    })
    
    task = asyncio.create_task(orchestrator.run())
    
    # Wait for flow:
    # CEO -> COO (TASK)
    # COO -> Engineer (TASK)
    # Engineer -> (SANDBOX_EXECUTE) -> Orchestrator
    # Orchestrator -> QA (RESULT)
    # QA -> COO (RESULT)
    
    # We expect a RESULT message from SYSTEM_SANDBOX to QA
    
    found_result = False
    for _ in range(100): # Wait up to 10 seconds (0.1 * 100)
        await asyncio.sleep(0.1)
        async with aiosqlite.connect(store.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM messages WHERE kind = 'RESULT' AND from_agent = 'SYSTEM_SANDBOX'") as cursor:
                row = await cursor.fetchone()
                if row:
                    found_result = True
                    # Check content
                    import json
                    body = json.loads(row["body_json"]) if isinstance(row["body_json"], str) else row["body_json"]
                    assert body["exit_code"] == 0
                    assert "Hello from Sandbox" in body["stdout"]
                    break
    
    orchestrator.running = False
    await task
    
    assert found_result, "Did not find RESULT message from sandbox"
    
    # Verify sandbox_runs table
    async with aiosqlite.connect(store.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM sandbox_runs WHERE mission_id = ?", (mission_id,)) as cursor:
            row = await cursor.fetchone()
            assert row
            assert row["status"] == "completed"
            assert row["exit_code"] == 0
