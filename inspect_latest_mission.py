import asyncio
import aiosqlite
from pathlib import Path
import json

DB_PATH = Path.home() / ".local" / "share" / "coo" / "coo.db"

async def inspect():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Get latest mission
        async with db.execute("SELECT * FROM missions ORDER BY created_at DESC LIMIT 1") as cursor:
            mission = await cursor.fetchone()
            if not mission:
                print("No missions found.")
                return
            
            print(f"Mission ID: {mission['id']}")
            print(f"Status: {mission['status']}")
            
            # Check artifacts
            async with db.execute("SELECT * FROM artifacts WHERE mission_id = ?", (mission['id'],)) as cursor:
                artifacts = await cursor.fetchall()
                print(f"\nArtifacts ({len(artifacts)}):")
                for art in artifacts:
                    print(f"  - ID: {art['id']}")
                    print(f"    Filename: {art['filename']}")
                    print(f"    Created By: {art['created_by']}")
            
            # Check sandbox runs
            async with db.execute("SELECT * FROM sandbox_runs WHERE mission_id = ?", (mission['id'],)) as cursor:
                runs = await cursor.fetchall()
                print(f"\nSandbox Runs ({len(runs)}):")
                for run in runs:
                    print(f"  - Status: {run['status']}")
                    print(f"    Exit Code: {run['exit_code']}")
                    print(f"    Stdout: {run['stdout']}")
                    print(f"    Stderr: {run['stderr']}")

if __name__ == "__main__":
    asyncio.run(inspect())
