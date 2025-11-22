from pathlib import Path
from coo.message_store import MessageStore
import asyncio

async def main():
    db_path = Path.home() / ".local/share/coo/coo.db"
    store = MessageStore(db_path)
    await store.initialize()
    print("Initialized:", db_path)

asyncio.run(main())
