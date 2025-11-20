import asyncio
import json
import os
from pathlib import Path
from click.testing import CliRunner
import pytest
import aiosqlite

from coo.cli import cli
from coo.message_store import MessageStore

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_coo.db"

def test_init_db(runner, db_path):
    result = runner.invoke(cli, ["--db-path", str(db_path), "init-db"])
    assert result.exit_code == 0
    assert f"Database initialized at {db_path}" in result.output
    assert db_path.exists()

def test_mission_command(runner, db_path):
    # Setup function
    async def setup():
        store = MessageStore(db_path)
        await store.initialize()
        mission_data = {
            "id": "mission-123",
            "description": "Test Mission",
            "max_cost_usd": 10.0,
            "max_loops": 5
        }
        await store.create_mission(mission_data)
        await store.log_timeline_event("mission-123", "test_event", {"foo": "bar"})

    # Run setup
    asyncio.run(setup())
    
    # Run CLI command
    result = runner.invoke(cli, ["--db-path", str(db_path), "mission", "mission-123"])
    assert result.exit_code == 0
    assert "Mission: mission-123" in result.output
    assert "Status: created" in result.output
    assert "test_event" in result.output

def test_logs_command(runner, db_path):
    async def setup():
        store = MessageStore(db_path)
        await store.initialize()
        await store.create_mission({"id": "m1", "description": "d"})
        await store.log_timeline_event("m1", "event1", {"a": 1})
        await store.log_timeline_event("m1", "event2", {"b": 2})
    
    asyncio.run(setup())
    
    result = runner.invoke(cli, ["--db-path", str(db_path), "logs", "m1"])
    assert result.exit_code == 0
    assert "event1" in result.output
    assert "event2" in result.output
    assert '{"a": 1}' in result.output

def test_dlq_replay_command(runner, db_path):
    async def setup():
        store = MessageStore(db_path)
        await store.initialize()
        await store.create_mission({"id": "m1", "description": "d"})
        msg = {
            "id": "msg-1",
            "mission_id": "m1",
            "from_agent": "A",
            "to_agent": "B",
            "kind": "task",
            "body_json": {}
        }
        await store.deliver_message(msg)
        
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                INSERT INTO dead_letters (id, original_message_id, mission_id, failed_at, error_type, retry_count, payload_snapshot)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
                """,
                ("dlq-1", "msg-1", "m1", "error", 3, "{}")
            )
            await db.commit()
            
    asyncio.run(setup())
        
    result = runner.invoke(cli, ["--db-path", str(db_path), "dlq-replay", "dlq-1"])
    assert result.exit_code == 0
    assert "Replayed dead letter dlq-1" in result.output
    
    # Verify
    async def verify():
        async with aiosqlite.connect(db_path) as db:
            async with db.execute("SELECT * FROM dead_letters WHERE id = 'dlq-1'") as cursor:
                assert await cursor.fetchone() is None
                
            async with db.execute("SELECT status, retry_count FROM messages WHERE id = 'msg-1'") as cursor:
                row = await cursor.fetchone()
                assert row[0] == "pending"
                assert row[1] == 0
                
    asyncio.run(verify())
