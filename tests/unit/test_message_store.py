import asyncio
from pathlib import Path

import pytest
import pytest_asyncio

from coo.message_store import MessageStore
from coo.models import MessageKind


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = tmp_path / "test_coo.db"
    store = MessageStore(db_path)
    await store.initialize()
    return store


@pytest.mark.asyncio
async def test_initialize(store):
    assert store.db_path.exists()


@pytest.mark.asyncio
async def test_deliver_and_claim_message(store):
    msg_id = "msg_123"
    mission_id = "m_1"

    # Create mission first (foreign key constraint)
    await store.create_mission({"id": mission_id, "description": "Test Mission"})

    msg = {
        "id": msg_id,
        "mission_id": mission_id,
        "from_agent": "COO",
        "to_agent": "Engineer",
        "kind": MessageKind.TASK.value,
        "body_json": '{"task": "test"}',
        "priority": 5,
    }

    await store.deliver_message(msg)

    # Claim message
    claimed = await store.claim_pending_messages("Engineer", mission_id)
    assert len(claimed) == 1
    assert claimed[0]["id"] == msg_id
    assert claimed[0]["status"] == "processing"
    assert claimed[0]["locked_by"] == store.worker_id


@pytest.mark.asyncio
async def test_reclaim_stale_messages(store):
    msg_id = "msg_stale"
    mission_id = "m_1"

    await store.create_mission({"id": mission_id, "description": "Test Mission"})

    msg = {
        "id": msg_id,
        "mission_id": mission_id,
        "from_agent": "COO",
        "to_agent": "Engineer",
        "kind": MessageKind.TASK.value,
        "body_json": '{"task": "test"}',
        "priority": 5,
    }

    await store.deliver_message(msg)

    # Manually lock the message and set locked_at to the past
    # We need to simulate a stale message.
    # Since we can't easily mock time inside the DB query without modifying the query or DB time,
    # we can update the record directly to set locked_at to the past.

    # First claim it to set it to processing
    await store.claim_pending_messages("Engineer", mission_id)

    # Now update it to be stale
    from datetime import datetime, timedelta, timezone

    import aiosqlite

    stale_time = datetime.now(timezone.utc) - timedelta(
        seconds=store.HEARTBEAT_TIMEOUT_SECONDS + 10
    )

    async with aiosqlite.connect(store.db_path) as db:
        await db.execute(
            "UPDATE messages SET locked_at = ? WHERE id = ?", (stale_time, msg_id)
        )
        await db.commit()

    # Now try to reclaim
    reclaimed_count = await store.reclaim_stale_messages()
    assert reclaimed_count == 1

    # Verify it's pending again
    async with aiosqlite.connect(store.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT status, retry_count FROM messages WHERE id = ?", (msg_id,)
        ) as cursor:
            row = await cursor.fetchone()
            assert row["status"] == "pending"
            assert row["retry_count"] == 1
