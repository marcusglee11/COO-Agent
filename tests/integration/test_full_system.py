import pytest
import asyncio
import aiosqlite
from pathlib import Path

from coo.orchestrator import Orchestrator
from coo.message_store import MessageStore
from coo.models import MessageKind
from coo.agents.dummy_agents import DummyCOO, DummyEngineer, DummyQA

@pytest.mark.asyncio
async def test_full_system_flow_with_dummy_agents(tmp_path):
    """
    Integration test using DummyAgents to verify:
    - Message routing
    - Timeline events
    - Mission status transitions
    - Orchestrator lifecycle
    """
    # 1. Setup
    db_path = tmp_path / "integration.db"
    store = MessageStore(db_path)
    await store.initialize()
    
    config = {
        "tick_interval_seconds": 0.05,  # Fast ticks for testing
        "budgets": {"global_daily_usd": 100.0},
        "backpressure": {"max_pending_messages": 50},
        "sandbox": {"temp_dir": "coo-test-integration"}
    }
    
    orchestrator = Orchestrator(store, config)
    
    # Replace with DummyAgents
    orchestrator.agents = {
        "COO": DummyCOO("COO"),
        "Engineer": DummyEngineer("Engineer"),
        "QA": DummyQA("QA"),
    }
    
    # 2. Start Mission
    mission_data = {
        "id": "mission-int-1", 
        "description": "Test mission",
        "max_cost_usd": 1.0,
        "max_loops": 5
    }
    await store.create_mission(mission_data)
    
    # Inject initial trigger message
    await store.deliver_message({
        "id": "trigger-1",
        "mission_id": "mission-int-1",
        "from_agent": "USER",
        "to_agent": "COO",
        "kind": MessageKind.TASK.value,
        "body_json": {"content": "Start"}
    })
    
    # 3. Run Orchestrator (background task)
    orchestrator_task = asyncio.create_task(orchestrator.run())
    
    # 4. Wait for completion (poll DB)
    try:
        for i in range(100): # Wait up to 10 seconds
            mission = await store.get_mission("mission-int-1")
            if mission["status"] == "completed":
                break
            await asyncio.sleep(0.1)
            
        print(f"Final mission status: {mission['status']}")
        
        # Check message count
        async with aiosqlite.connect(db_path) as db:
            async with db.execute("SELECT COUNT(*), status FROM messages WHERE mission_id = ? GROUP BY status", ("mission-int-1",)) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    print(f"Messages with status '{row[1]}': {row[0]}")
                
        assert mission["status"] == "completed", f"Mission did not complete. Status: {mission['status']}"
        
        # 5. Verify Timeline Events exist
        async with aiosqlite.connect(db_path) as db:
            async with db.execute("SELECT event_type FROM timeline_events WHERE mission_id = ?", ("mission-int-1",)) as cursor:
                rows = await cursor.fetchall()
                events = [row[0] for row in rows]
                print(f"Timeline events: {events}")
                assert len(events) > 0, "No timeline events logged"
                assert "mission_status_changed" in events
                
    finally:
        orchestrator.running = False
        try:
            await asyncio.wait_for(orchestrator_task, timeout=2.0)
        except asyncio.TimeoutError:
            orchestrator_task.cancel()
            try:
                await orchestrator_task
            except asyncio.CancelledError:
                pass
