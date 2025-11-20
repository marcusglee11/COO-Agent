import asyncio
import uuid
from pathlib import Path
from coo.message_store import MessageStore
from coo.models import MessageKind

async def seed():
    db_path = Path.home() / ".local" / "share" / "coo" / "coo.db"
    store = MessageStore(db_path)
    await store.initialize()

    mission_id = f"mission_e2e_{uuid.uuid4().hex[:8]}"
    print(f"Seeding mission {mission_id}...")

    await store.create_mission({
        "id": mission_id,
        "description": "End-to-end test mission: Create a python script that prints 'Hello World'",
        "max_cost_usd": 1.0,
        "max_loops": 10
    })

    msg_id = str(uuid.uuid4())
    await store.deliver_message({
        "id": msg_id,
        "mission_id": mission_id,
        "from_agent": "User",
        "to_agent": "COO",
        "kind": MessageKind.TASK.value,
        "body_json": {"task": "Please create a python script that prints 'Hello World'"}
    })

    print(f"Seeded mission {mission_id} with initial message {msg_id}")

if __name__ == "__main__":
    asyncio.run(seed())
