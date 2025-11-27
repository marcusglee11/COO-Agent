import asyncio
import aiosqlite
from pathlib import Path

# Use standard COO database location
DB_PATH = Path.home() / ".local" / "share" / "coo" / "coo.db"


async def main() -> None:
    """Initialize global budget in the database"""
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Please run 'python -m coo.cli init-db' first to create the database schema.")
        return
    
    try:
        # Connect directly to the SQLite DB
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO budgets_global (
                    id,
                    daily_budget_usd,
                    daily_spent_usd,
                    monthly_budget_usd,
                    monthly_spent_usd,
                    updated_at
                )
                VALUES (
                    1,
                    1.0,   -- daily budget in USD
                    0.0,
                    5.0,   -- monthly budget in USD
                    0.0,
                    CURRENT_TIMESTAMP
                );
                """
            )
            await db.commit()

            print(f"SUCCESS: Global budget row initialized in {DB_PATH}")
    
    except aiosqlite.OperationalError as e:
        print(f"ERROR: Database operation failed: {e}")
        print("The database schema may be incomplete. Please run 'python -m coo.cli init-db'")


if __name__ == "__main__":
    asyncio.run(main())
