import asyncio
import aiosqlite
from pathlib import Path

async def main():
    db_path = Path.home() / ".local/share/coo/coo.db"
    mission_id = None

    # Automatically detect the newest mission (for convenience)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        print("\n--- Missions ---")
        async with db.execute("SELECT * FROM missions ORDER BY created_at DESC LIMIT 1") as cur:
            row = await cur.fetchone()
            print(dict(row))
            mission_id = row["id"]

        print("\n--- Messages ---")
        async with db.execute("""
            SELECT id, from_agent, to_agent, kind, status, created_at 
            FROM messages 
            WHERE mission_id = ? 
            ORDER BY created_at
        """, (mission_id,)) as cur:
            for r in await cur.fetchall():
                print(dict(r))

        print("\n--- Sandbox Runs ---")
        async with db.execute("""
            SELECT id, mission_id, status, exit_code, stderr, stdout, started_at, completed_at 
            FROM sandbox_runs 
            WHERE mission_id = ?
            ORDER BY started_at
        """, (mission_id,)) as cur:
            for r in await cur.fetchall():
                print(dict(r))

        print("\n--- Artifacts ---")
        async with db.execute("""
            SELECT id, mission_id, filename, created_at
            FROM artifacts 
            WHERE mission_id = ?
        """, (mission_id,)) as cur:
            for r in await cur.fetchall():
                print(dict(r))

asyncio.run(main())
