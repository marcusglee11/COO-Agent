import asyncio
from pathlib import Path

import click
import structlog

from coo.message_store import MessageStore

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


@cli.command()
@click.argument("mission_id")
@click.pass_context
def mission(ctx, mission_id):
    """Show mission details and timeline"""

    async def _mission():
        db_path = ctx.obj["db_path"]
        if not db_path.exists():
            click.echo("Database not found.")
            return

        store = MessageStore(db_path)
        mission = await store.get_mission(mission_id)
        if not mission:
            click.echo(f"Mission {mission_id} not found.")
            return

        click.echo(f"Mission: {mission['id']}")
        click.echo(f"Status: {mission['status']}")
        click.echo(f"Budget: ${mission['spent_cost_usd']:.4f} / ${mission['max_cost_usd']:.2f}")
        click.echo(f"Description: {mission['description']}")
        click.echo("-" * 40)
        click.echo("Recent Timeline:")
        
        import aiosqlite
        async with aiosqlite.connect(store.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM timeline_events WHERE mission_id = ? ORDER BY created_at DESC LIMIT 20",
                (mission_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    click.echo(f"[{row['created_at']}] {row['event_type']}")

    asyncio.run(_mission())


@cli.command()
@click.argument("mission_id")
@click.pass_context
def logs(ctx, mission_id):
    """Dump timeline events for a mission"""

    async def _logs():
        db_path = ctx.obj["db_path"]
        store = MessageStore(db_path)
        
        import aiosqlite
        async with aiosqlite.connect(store.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM timeline_events WHERE mission_id = ? ORDER BY created_at ASC",
                (mission_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    click.echo(f"{row['created_at']} {row['event_type']} {row['event_json']}")

    asyncio.run(_logs())


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
