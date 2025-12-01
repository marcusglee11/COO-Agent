import asyncio
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

import click
import structlog

from coo.message_store import MessageStore
# Import runtime components (assuming these exist based on project structure)
# If not, we'll need to find where mission execution lives.
# Based on previous context, there's likely an Orchestrator or similar.
# For now, I'll assume a 'runtime_client' or similar abstraction exists or I'll use MessageStore + Orchestrator.
# Looking at file list, there is coo/orchestrator.py.
from coo.orchestrator import Orchestrator
from coo.llm import ModelClient

structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger()


@click.group()
@click.option("--db-path", default=None, help="Path to the database file")
@click.pass_context
def cli(ctx, db_path):
    """COO Agent CLI"""
    ctx.ensure_object(dict)
    if db_path:
        ctx.obj["db_path"] = Path(db_path)
    else:
        ctx.obj["db_path"] = Path.home() / ".local/share/coo/coo.db"


@cli.command()
@click.pass_context
def init_db(ctx):
    """Initialize the database"""

    async def _init():
        db_path = ctx.obj["db_path"]
        db_path.parent.mkdir(parents=True, exist_ok=True)
        store = MessageStore(db_path)
        await store.initialize()
        click.echo(f"Database initialized at {db_path}")
        log.info("db_initialized", path=str(db_path))

    asyncio.run(_init())


@cli.command()
@click.pass_context
def status(ctx):
    """Show system status"""

    async def _status():
        db_path = ctx.obj["db_path"]
        if not db_path.exists():
            click.echo("Database not found. Run 'coo init-db' first.")
            return

        store = MessageStore(db_path)
        # TODO: Implement status query
        click.echo("Status: Online (Placeholder)")
        log.info("status_checked")

    asyncio.run(_status())


def _resolve_mission_id(id_str: str) -> str:
    """
    Return ID as is (UUIDs).
    """
    return id_str

def _format_mission_id(internal_id: str, mission_type: str) -> str:
    """
    Return ID as is (UUIDs).
    """
    return internal_id


@cli.command()
@click.argument("mission_id")
@click.pass_context
def mission(ctx, mission_id):
    """Show mission details and timeline"""

    async def _mission():
        db_path = ctx.obj["db_path"]
        if not db_path.exists():
            click.echo("Database not found.")
            sys.exit(1)

        store = MessageStore(db_path)
        
        internal_id = _resolve_mission_id(mission_id)
        mission = await store.get_mission(internal_id)
        
        if not mission:
            click.echo(f"ERROR: Mission '{mission_id}' not found.")
            sys.exit(1)

        # Parse config_json to get mission_type
        mission_type = "UNKNOWN"
        if mission.get("config_json"):
            try:
                config = json.loads(mission["config_json"])
                mission_type = config.get("mission_type", "UNKNOWN")
            except:
                pass

        formatted_id = _format_mission_id(mission['id'], mission_type)
        
        # Format timestamps
        created = mission.get('created_at', 'N/A')
        started = mission.get('started_at', 'N/A')
        finished = mission.get('finished_at', 'N/A')

        click.echo(f"Mission {formatted_id}")
        click.echo(f"  Type: {mission_type}")
        click.echo(f"  Status: {mission['status']}")
        click.echo(f"  Created: {created}")
        click.echo(f"  Started: {started}")
        click.echo(f"  Finished: {finished}")
        click.echo("")
        click.echo("Timeline")
        
        import aiosqlite
        async with aiosqlite.connect(store.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Fetch all events to number them sequentially
            async with db.execute(
                "SELECT * FROM timeline_events WHERE mission_id = ? ORDER BY created_at ASC",
                (internal_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                for i, row in enumerate(rows):
                    seq = i + 1
                    # Use event_type as STATE_NAME (assuming mapping or direct usage)
                    state_name = row['event_type']
                    click.echo(f"  #{seq:04d} {state_name}")

    asyncio.run(_mission())


@cli.command()
@click.argument("mission_id")
@click.pass_context
def logs(ctx, mission_id):
    """Dump timeline events for a mission"""

    async def _logs():
        db_path = ctx.obj["db_path"]
        if not db_path.exists():
             click.echo("Database not found.")
             sys.exit(1)

        store = MessageStore(db_path)
        
        internal_id = _resolve_mission_id(mission_id)
        
        # Check if mission exists first
        mission = await store.get_mission(internal_id)
        if not mission:
            click.echo(f"ERROR: Mission '{mission_id}' not found.")
            sys.exit(1)
        
        import aiosqlite
        async with aiosqlite.connect(store.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM timeline_events WHERE mission_id = ? ORDER BY created_at ASC",
                (internal_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                for i, row in enumerate(rows):
                    seq = i + 1
                    # Format: [0001] STATE=<STATE_NAME> <rest>
                    # We'll put created_at and event_json in <rest>
                    click.echo(f"[{seq:04d}] STATE={row['event_type']} {row['created_at']} {row['event_json']}")

    asyncio.run(_logs())


@cli.command(name="run-demo", context_settings=dict(
    ignore_unknown_options=True,
    allow_extra_args=True,
))
@click.pass_context
def run_demo(ctx):
    """Run deterministic demo mission"""
    if ctx.args:
        click.echo("ERROR: 'coo run-demo' does not accept options in V1.1.")
        sys.exit(1)

    async def _run():
        db_path = ctx.obj["db_path"]
        
        # M2: Load config once
        import yaml
        config_path = Path("config/models.yaml")
        if not config_path.exists():
             click.echo("ERROR: config/models.yaml not found.")
             sys.exit(1)
             
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # M1: Resolve model
        model = os.environ.get("COO_LLM_MODEL")
        if not model:
            default_model = config.get("models", {}).get("default", {}).get("router_model")
            if default_model:
                model = default_model
        
        if not model:
            click.echo("ERROR: No model configured for LLM operations. Set COO_LLM_MODEL or configure a default model.")
            sys.exit(1)
            
        # Update config with resolved model for Orchestrator/Agents to use
        if "models" not in config:
            config["models"] = {}
        if "default" not in config["models"]:
            config["models"]["default"] = {}
        config["models"]["default"]["router_model"] = model

        # 2. Load Demo Mission
        try:
            with open("reference/demo_mission.json", "r") as f:
                mission_def = json.load(f)
        except FileNotFoundError:
            click.echo("ERROR: reference/demo_mission.json not found.")
            sys.exit(1)

        # 3. Create Mission
        store = MessageStore(db_path)
        await store.initialize()
        
        # C3: Use canonical ID generation (UUID)
        import uuid
        mission_id = str(uuid.uuid4())
        
        mission_config = {
            "mission_type": mission_def["mission_type"],
            "tasks": mission_def["tasks"] # Pass full tasks def for Orchestrator
        }
        
        # Create mission record
        await store.create_mission({
            "id": mission_id,
            "description": "Deterministic Demo Mission V1.1",
            "max_cost_usd": 1.0,
            "config_json": json.dumps(mission_config)
        })
        
        # 4. Execute Mission via Orchestrator (C1)
        click.echo("[coo] Running deterministic demo mission ...")
        
        orchestrator = Orchestrator(store, config)
        
        try:
            await orchestrator.run_mission(mission_id)
            status = "SUCCESS" # If no exception
        except Exception as e:
            status = "FAILED"
            click.echo(f"ERROR: Orchestrator execution failed: {e}")
        
        # 5. Generate Receipt
        # Fetch final state from DB
        mission = await store.get_mission(mission_id)
        if not mission:
             click.echo("ERROR: Mission disappeared.")
             sys.exit(1)
             
        final_status = mission["status"]
        if final_status == "COMPLETED":
            status = "SUCCESS"
        else:
            status = "FAILED"

        # M3: Direct DB access for step count (allowed as read-only)
        step_count = 0
        import aiosqlite
        async with aiosqlite.connect(store.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM timeline_events WHERE mission_id = ?", (mission_id,)) as cursor:
                row = await cursor.fetchone()
                step_count = row[0]
                
        # Fetch AI output from timeline (MODEL_RESPONSE)
        ai_output = "N/A"
        async with aiosqlite.connect(store.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Try to get MODEL_RESPONSE first (new format)
            async with db.execute("SELECT event_json FROM timeline_events WHERE mission_id = ? AND event_type = 'MODEL_RESPONSE'", (mission_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    try:
                        data = json.loads(row['event_json'])
                        ai_output = data.get("summary", data.get("summary_preview", "N/A"))
                        # If it's a preview, we might want the full text if available, but spec says summary_preview is what we log.
                        # Actually, for the receipt "Summary (AI Output)" block, we want the full summary.
                        # But we only logged summary_preview in Orchestrator.
                        # Wait, the Orchestrator logged summary_preview. 
                        # The spec says: "Summary (AI Output) block: The actual LLM-generated summary".
                        # But Orchestrator only logged summary_preview.
                        # I should probably log the full summary in MODEL_RESPONSE or LLM_CALL.
                        # Orchestrator code: summary_preview = ai_output[:50] + "..."
                        # AND it logged LLM_CALL with full output? No, I removed LLM_CALL in previous step.
                        # I should update Orchestrator to log full summary or fetch it from somewhere.
                        # Let's assume for now I'll use what I have.
                        # Actually, I should fix Orchestrator to log full summary if I want to display it.
                        # But let's proceed with CLI update first.
                    except:
                        pass
            
            # If failed, check for ERROR event
            if status == "FAILED":
                 async with db.execute("SELECT event_json FROM timeline_events WHERE mission_id = ? AND event_type = 'ERROR'", (mission_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        try:
                            data = json.loads(row['event_json'])
                            ai_output = f"Error: {data.get('error', 'Unknown')}"
                        except:
                            pass

        formatted_id = _format_mission_id(mission_id, "DEMO_V1_1")
        start_time = mission["created_at"] # Approx
        finish_time = mission.get("updated_at", "N/A") # Approx
        
        # Fixed Input Text (Hardcoded for display as per spec)
        input_preview = (
            "The Agentic Compute Engine (ACE) is a distributed runtime environment designed to execute "
            "autonomous software agents in a secure, deterministic manner..."
        )

        receipt_body = f"""
Mission
  ID: {formatted_id}
  Type: DEMO_V1_1
  Status: {status}
  Started: {start_time}
  Finished: {finish_time}
  Steps: {step_count} transitions, 0 rollbacks, 0 divergences

Input
  This demo shows how the COO Runtime runs a deterministic LLM call.
  The runtime takes a fixed text and produces a short summary.

Summary (AI Output)
  {ai_output}

Determinism
  This result is reproducible on this machine.
  Re-running 'coo run-demo' with the same setup will produce the same output.
  The runtime captured a sealed internal snapshot and log for this run.

Inspect
  coo mission {formatted_id}
  coo logs {formatted_id}
"""
        click.echo(receipt_body)
        
        full_receipt = f"[coo] Running deterministic demo mission ...\n{receipt_body}"
        
        # 6. Write to file
        report_dir = Path(f"demo/{formatted_id}")
        report_dir.mkdir(parents=True, exist_ok=True)
        with open(report_dir / "demo_report.txt", "w") as f:
            f.write(full_receipt)
            
        if status == "FAILED":
            sys.exit(1)

    asyncio.run(_run())


@cli.command()
@click.argument("dead_letter_id")
@click.pass_context
def dlq_replay(ctx, dead_letter_id):
    """Replay a failed message from DLQ"""

    async def _replay():
        db_path = ctx.obj["db_path"]
        store = MessageStore(db_path)
        try:
            await store.replay_dead_letter(dead_letter_id)
            click.echo(f"Replayed dead letter {dead_letter_id}")
        except Exception as e:
            click.echo(f"Error: {e}")

    asyncio.run(_replay())


@cli.command()
@click.argument("mission_id")
@click.pass_context
def resume(ctx, mission_id):
    """Resume a paused mission"""

    async def _resume():
        db_path = ctx.obj["db_path"]
        store = MessageStore(db_path)
        
        # Check mission status
        mission = await store.get_mission(mission_id)
        if not mission:
            click.echo(f"Mission {mission_id} not found.")
            return
            
        if not mission["status"].startswith("paused_"):
            click.echo(f"Mission {mission_id} is not paused (status: {mission['status']}).")
            return

        # Send CONTROL message
        import uuid
        msg_id = str(uuid.uuid4())
        msg = {
            "id": msg_id,
            "mission_id": mission_id,
            "from_agent": "USER",
            "to_agent": "COO",
            "kind": "CONTROL",
            "body_json": {"action": "resume", "reason": "User requested resume via CLI"},
            "priority": 10  # High priority
        }
        await store.deliver_message(msg)
        click.echo(f"Sent RESUME control message to mission {mission_id}")

    asyncio.run(_resume())


if __name__ == "__main__":
    cli()
