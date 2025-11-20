import asyncio
import pytest
import pytest_asyncio
from pathlib import Path
from coo.sandbox import SandboxRunner
import aiosqlite

@pytest_asyncio.fixture
async def store(tmp_path):
    from coo.message_store import MessageStore
    db_path = tmp_path / "test_coo.db"
    store = MessageStore(db_path)
    await store.initialize()
    return store

@pytest_asyncio.fixture
async def sandbox(store):
    return SandboxRunner(store.db_path, {"temp_dir": "test_sandbox"})

@pytest.mark.asyncio
async def test_hello_world(sandbox):
    result = await sandbox.run_script('print("Hello World")')
    assert result.exit_code == 0
    assert "Hello World" in result.stdout

@pytest.mark.asyncio
async def test_timeout(sandbox):
    # Script that sleeps for 5 seconds, timeout is 1 second
    result = await sandbox.run_script('import time; time.sleep(5)', timeout=1)
    assert result.exit_code == -1
    assert result.error_class == "timeout" or "timed out" in result.stderr

@pytest.mark.asyncio
async def test_no_network(sandbox):
    # Script that tries to access google.com
    script = """
import requests
try:
    requests.get("https://google.com", timeout=2)
except Exception as e:
    print(e)
    exit(1)
"""
    result = await sandbox.run_script(script)
    assert result.exit_code != 0
    # Network is unreachable or name resolution fails

@pytest.mark.asyncio
async def test_idempotency(sandbox):
    # Run once
    result1 = await sandbox.run_script('print("Once")')
    assert result1.exit_code == 0
    assert not result1.cached
    
    # We need to manually use run_artifact to test idempotency with same dedupe_id
    # run_script generates a new dedupe_id each time.
    
    # Let's use run_artifact with the artifact created by run_script?
    # run_script creates an artifact but we don't easily get its ID back to reuse.
    # Let's create an artifact manually.
    
    import uuid
    import base64
    artifact_id = str(uuid.uuid4())
    mission_id = "m_idempotency"
    dedupe_id = "dedupe_1"
    
    async with aiosqlite.connect(sandbox.db_path) as db:
        await db.execute("INSERT OR IGNORE INTO missions (id, status, description) VALUES (?, 'created', 'Test')", (mission_id,))
        await db.execute(
            "INSERT INTO artifacts (id, mission_id, filename, content_b64, created_at, created_by) VALUES (?, ?, 'main.py', ?, CURRENT_TIMESTAMP, 'test')",
            (artifact_id, mission_id, base64.b64encode(b'print("Idempotent")').decode())
        )
        await db.commit()
        
    # First run
    result1 = await sandbox.run_artifact(mission_id, artifact_id, "python main.py", dedupe_id)
    assert result1.exit_code == 0
    assert not result1.cached
    
    # Second run
    result2 = await sandbox.run_artifact(mission_id, artifact_id, "python main.py", dedupe_id)
    assert result2.exit_code == 0
    assert result2.cached
    assert result2.stdout == "" # Cached result doesn't return stdout in the object? 
    # Wait, the spec says: "result_artifact_id=row.result_artifact_id".
    # It doesn't say it returns stdout/stderr from DB.
    # The DB schema has stdout/stderr columns in sandbox_runs.
    # The idempotency check in SandboxRunner only fetches result_artifact_id.
    # If we want stdout/stderr, we should fetch them too.
    # But for now, let's assert it is cached.

@pytest.mark.asyncio
async def test_crash_recovery(sandbox):
    # Insert a stale running job
    import uuid
    dedupe_id = str(uuid.uuid4())
    mission_id = "m_crash"
    artifact_id = str(uuid.uuid4())
    
    async with aiosqlite.connect(sandbox.db_path) as db:
        await db.execute("INSERT OR IGNORE INTO missions (id, status, description) VALUES (?, 'created', 'Test')", (mission_id,))
        # Insert running job started 20 mins ago
        await db.execute(
            """
            INSERT INTO sandbox_runs (dedupe_id, mission_id, artifact_id, status, started_at)
            VALUES (?, ?, ?, 'running', datetime('now', '-20 minutes'))
            """,
            (dedupe_id, mission_id, artifact_id)
        )
        await db.commit()
        
    await sandbox.recover_crashed_runs()
    
    async with aiosqlite.connect(sandbox.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT status, exit_code FROM sandbox_runs WHERE dedupe_id=?", (dedupe_id,)) as cursor:
            row = await cursor.fetchone()
            assert row["status"] == "failed"
            assert row["exit_code"] == -1
