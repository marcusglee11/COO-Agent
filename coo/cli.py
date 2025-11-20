import asyncio
from pathlib import Path

import click
import structlog

from coo.message_store import MessageStore

structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger()


@click.group()
def cli():
    """COO Agent CLI"""
    pass


@cli.command()
def init_db():
    """Initialize the database"""

    async def _init():
        db_path = Path.home() / ".local/share/coo/coo.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        store = MessageStore(db_path)
        await store.initialize()
        click.echo(f"Database initialized at {db_path}")
        log.info("db_initialized", path=str(db_path))

    asyncio.run(_init())


@cli.command()
def status():
    """Show system status"""

    async def _status():
        db_path = Path.home() / ".local/share/coo/coo.db"
        if not db_path.exists():
            click.echo("Database not found. Run 'coo init-db' first.")
            return

        store = MessageStore(db_path)
        # TODO: Implement status query
        click.echo("Status: Online (Placeholder)")
        log.info("status_checked")

    asyncio.run(_status())


if __name__ == "__main__":
    cli()
