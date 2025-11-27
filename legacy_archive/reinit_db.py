from pathlib import Path
from coo.message_store import MessageStore
import asyncio

async def main():
    db = Path.home() / ".local/share/coo/coo.db"
    store = MessageStore(db)
    await store.initialize()
    print("Initialized:", db)

if __name__ == "__main__":
    asyncio.run(main())
