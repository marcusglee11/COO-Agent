import asyncio
import base64
import shutil
import structlog
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

import aiosqlite
import docker  # type: ignore

log = structlog.get_logger()


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    result_artifact_id: Optional[str]
    error_class: Optional[str]
    cached: bool = False


class SandboxRunner:
    def __init__(self, db_path: Path, config: Dict):
        self.db_path = db_path
        self.config = config
        self.client = docker.from_env()
        self.temp_base = Path(tempfile.gettempdir()) / config.get(
            "temp_dir", "coo-workspace"
        )

    async def run_artifact(
        self,
        mission_id: str,
        artifact_id: str,
        entrypoint: str,
        dedupe_id: str,
        timeout: int = 300,
    ) -> SandboxResult:
        """Execute an artifact in the sandbox with idempotency and security"""

        # 1. Idempotency Check
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT status, result_artifact_id FROM sandbox_runs WHERE dedupe_id=?",
                (dedupe_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row and row["status"] == "completed":
                    return SandboxResult(
                        exit_code=0,
                        stdout="",
                        stderr="",
                        result_artifact_id=row["result_artifact_id"],
                        error_class=None,
                        cached=True,
                    )

        # 2. Record Start
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO sandbox_runs (dedupe_id, mission_id, artifact_id, status, started_at)
                VALUES (?, ?, ?, 'running', CURRENT_TIMESTAMP)
                """,
                (dedupe_id, mission_id, artifact_id),
            )
            await db.commit()

        workspace = self.temp_base / dedupe_id
        container = None
        result_artifact_id = None
        error_class = None
        exit_code = -1
        stdout = ""
        stderr = ""

        try:
            # 3. Materialize Artifact
            await self._materialize_artifact(artifact_id, workspace)

            # Check entrypoint
            entry_parts = entrypoint.split()
            if not entry_parts or not (workspace / entry_parts[-1]).exists():
                # Try to find the file if it's a python script
                if len(entry_parts) > 1 and entry_parts[0] == "python":
                     script_path = workspace / entry_parts[1]
                     if not script_path.exists():
                         raise FileNotFoundError(f"Entrypoint script not found: {entry_parts[1]}")

            # 4. Execute
            log.info("sandbox_executing", dedupe_id=dedupe_id, entrypoint=entrypoint)
            
            # We need to handle timeout manually since detach=False blocks
            # Better to use detach=True and wait
            container = self.client.containers.run(
                "coo-sandbox:latest",
                command=entrypoint,
                volumes={str(workspace.absolute()): {"bind": "/workspace", "mode": "rw"}},
                working_dir="/workspace",
                network_mode="none",
                user="1000:1000",
                mem_limit="512m",
                nano_cpus=500000000,  # 0.5 CPU
                security_opt=["no-new-privileges"],
                detach=True,
            )

            # Wait for result with timeout
            loop = asyncio.get_running_loop()
            import functools
            try:
                # Wait for container to finish
                # Fix: Use asyncio.wait_for instead of container.wait(timeout=...)
                wait_coro = loop.run_in_executor(None, container.wait)
                result = await asyncio.wait_for(wait_coro, timeout=timeout)
                
                exit_code = result["StatusCode"]
                stdout = await loop.run_in_executor(
                    None, functools.partial(container.logs, stdout=True, stderr=False)
                )
                stderr = await loop.run_in_executor(
                    None, functools.partial(container.logs, stdout=False, stderr=True)
                )
                stdout = stdout.decode("utf-8", errors="replace")
                stderr = stderr.decode("utf-8", errors="replace")
                
            except asyncio.TimeoutError:
                container.kill()
                error_class = "timeout"
                stderr = f"Execution timed out after {timeout}s"
                exit_code = -1
            except Exception as e:
                # Other error
                container.kill()
                error_class = "execution_error"
                stderr = str(e)
                exit_code = -1
            
            # 5. Capture Result Artifact (if any new files?)
            # For now, we assume stdout/stderr is the result, but we might want to capture files.
            # The spec says "result_artifact_id". Maybe we save stdout/stderr as an artifact?
            # Or if the script produced an output file?
            # Let's save stdout as an artifact if successful.
            
            if exit_code == 0:
                result_artifact_id = str(uuid.uuid4())
                # Save stdout as artifact
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        """
                        INSERT INTO artifacts (id, mission_id, filename, content_b64, created_at, created_by)
                        VALUES (?, ?, 'stdout.txt', ?, CURRENT_TIMESTAMP, 'sandbox')
                        """,
                        (
                            result_artifact_id,
                            mission_id,
                            base64.b64encode(stdout.encode()).decode(),
                        ),
                    )
                    await db.commit()

        except Exception as e:
            log.error("sandbox_execution_failed", error=str(e))
            error_class = error_class or "system_error"
            stderr += f"\nSystem Error: {str(e)}"
            exit_code = -1

        finally:
            # Cleanup container if still running (should be handled by kill above, but safe check)
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass
            
            # 6. Cleanup Workspace
            shutil.rmtree(workspace, ignore_errors=True)

            # 7. Record End
            status = "completed" if exit_code == 0 else "failed"
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    UPDATE sandbox_runs 
                    SET status = ?, 
                        exit_code = ?, 
                        stdout = ?, 
                        stderr = ?, 
                        result_artifact_id = ?, 
                        completed_at = CURRENT_TIMESTAMP
                    WHERE dedupe_id = ?
                    """,
                    (status, exit_code, stdout, stderr, result_artifact_id, dedupe_id),
                )
                await db.commit()

        return SandboxResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            result_artifact_id=result_artifact_id,
            error_class=error_class,
            cached=False,
        )

    async def _materialize_artifact(self, artifact_id: str, workspace: Path):
        """Materialize artifact files to workspace"""
        workspace.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Support multiple files if artifact_id refers to a group? 
            # Or just one file per artifact_id?
            # The schema has 'filename' in artifacts table.
            # If we want to support multiple files, we might need to query by something else or 
            # assume artifact_id is unique per file.
            # The spec says: "artifacts table contains: (id, mission_id, filename, content_b64)"
            # So one artifact ID = one file.
            # But the spec also says "rows = await db.execute... for row in rows".
            # This implies multiple rows might match? 
            # Ah, if we use a shared ID for a bundle? 
            # But 'id' is PRIMARY KEY. So only one row.
            # Unless we query by mission_id? No, that would dump everything.
            # Maybe the user meant "if artifact_id is a list?"
            # Or maybe the user implies we might pass a list of artifact IDs?
            # The spec code snippet shows: "SELECT filename, content_b64 FROM artifacts WHERE id=?"
            # And then "for row in rows".
            # Since ID is PK, this will be 0 or 1 row.
            # I will follow the spec logic, but it likely only handles one file.
            
            async with db.execute(
                "SELECT filename, content_b64 FROM artifacts WHERE id=?", (artifact_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    file_path = workspace / row["filename"]
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_bytes(base64.b64decode(row["content_b64"]))

    async def run_script(self, script_content: str, timeout: int = 30) -> SandboxResult:
        """Helper for local unit testing only"""
        # Create a dummy artifact for the script
        artifact_id = str(uuid.uuid4())
        mission_id = "test_mission"
        dedupe_id = str(uuid.uuid4())
        
        async with aiosqlite.connect(self.db_path) as db:
            # Ensure mission exists
            await db.execute("INSERT OR IGNORE INTO missions (id, status, description) VALUES (?, 'created', 'Test')", (mission_id,))
            
            await db.execute(
                """
                INSERT INTO artifacts (id, mission_id, filename, content_b64, created_at, created_by)
                VALUES (?, ?, 'main.py', ?, CURRENT_TIMESTAMP, 'test')
                """,
                (
                    artifact_id,
                    mission_id,
                    base64.b64encode(script_content.encode()).decode(),
                ),
            )
            await db.commit()
            
        return await self.run_artifact(
            mission_id=mission_id,
            artifact_id=artifact_id,
            entrypoint="python main.py",
            dedupe_id=dedupe_id,
            timeout=timeout,
        )

    async def recover_crashed_runs(self):
        """Mark stale running jobs as failed"""
        stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE sandbox_runs 
                SET status = 'failed', 
                    exit_code = -1, 
                    stderr = 'Orchestrator crash recovery',
                    completed_at = CURRENT_TIMESTAMP
                WHERE status = 'running' 
                  AND started_at < ?
                """,
                (stale_cutoff,),
            )
            await db.commit()
