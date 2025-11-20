import asyncio
import aiosqlite

# IMPORTANT: your real DB path from `coo init-db`
DB_PATH = r"C:\Users\cabra\.local\share\coo\coo.db"


async def main() -> None:
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

    print(f"OK: Global budget row inserted or already exists in {DB_PATH!r}.")


if __name__ == "__main__":
    asyncio.run(main())
