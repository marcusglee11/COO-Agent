import asyncio
import aiosqlite
from pathlib import Path
from coo.message_store import MessageStore
import os

DB = Path("./test.db")

async def test_lifecycle():
    if DB.exists():
        DB.unlink()
    store = MessageStore(DB, worker_id="test_worker")
    await store.initialize()

    # 1. deliver
    await store.deliver_message({
        "id": "m1",
        "mission_id": "miss1",
        "from_agent": "COO",
        "to_agent": "Engineer",
        "kind": "TASK",
        "body_json": '{"action":"test"}'
    })

    # 2. claim
    msgs = await store.claim_pending_messages("Engineer", "miss1", limit=1)
    assert len(msgs) == 1
    assert msgs[0]["id"] == "m1"
    assert msgs[0]["status"] == "processing"

    # 3. idempotency (second claim returns nothing)
    msgs = await store.claim_pending_messages("Engineer", "miss1", limit=1)
    assert len(msgs) == 0

    DB.unlink()

if __name__ == "__main__":
    asyncio.run(test_lifecycle())
    print("✓ message_store smoke test passed")
