import pytest
import asyncio
from coo.message_store import MessageStore
from coo.models import MessageKind
from coo.agents.real_agents import RealCOO

@pytest.mark.asyncio
async def test_backpressure_pause_and_resume(tmp_path):
    db_path = tmp_path / "test_control.db"
    store = MessageStore(db_path)
    await store.initialize()
    
    # 1. Create mission and set to paused
    mission_data = {"id": "m1", "description": "test", "max_cost_usd": 10.0, "max_loops": 5}
    await store.create_mission(mission_data)
    await store.update_mission_status("m1", "paused_error")
    
    # 2. Add normal message
    msg = {
        "id": "msg1",
        "mission_id": "m1",
        "from_agent": "Engineer",
        "to_agent": "COO",
        "kind": MessageKind.TASK.value,
        "body_json": {"content": "work"}
    }
    await store.deliver_message(msg)
    
    # 3. Verify claim returns nothing
    claimed = await store.claim_pending_messages("COO", limit=10)
    assert len(claimed) == 0
    
    # 4. Add CONTROL message
    control_msg = {
        "id": "ctrl1",
        "mission_id": "m1",
        "from_agent": "USER",
        "to_agent": "COO",
        "kind": MessageKind.CONTROL.value,
        "body_json": {"action": "resume"}
    }
    await store.deliver_message(control_msg)
    
    # 5. Verify claim returns ONLY control message
    claimed = await store.claim_pending_messages("COO", limit=10)
    assert len(claimed) == 1
    assert claimed[0]["id"] == "ctrl1"
    
    # 6. Verify RealCOO handles it
    agent = RealCOO("COO", None, None, None) # Mock dependencies as None since we don't call LLM
    
    # We need to pass the message in the list
    messages = [claimed[0]]
    
    emissions = []
    async for emission in agent.process_stream(mission_data, messages):
        emissions.append(emission)
        
    assert len(emissions) == 1
    assert emissions[0].type == "side_effect"
    assert emissions[0].data["state_transition"] == "executing"
