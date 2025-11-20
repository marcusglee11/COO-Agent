import pytest
import sqlite3
import aiosqlite
from pathlib import Path
from coo.budget import BudgetTracker, BudgetExceededError

@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    # Use sync sqlite3 for setup to avoid async fixture issues
    with sqlite3.connect(path) as db:
        # Create tables
        db.execute("""
            CREATE TABLE missions (
                id TEXT PRIMARY KEY,
                status TEXT,
                description TEXT,
                spent_cost_usd REAL DEFAULT 0.0,
                max_cost_usd REAL DEFAULT 1.0
            )
        """)
        db.execute("""
            CREATE TABLE budgets_global (
                id INTEGER PRIMARY KEY,
                daily_budget_usd REAL DEFAULT 10.0,
                daily_spent_usd REAL DEFAULT 0.0,
                monthly_budget_usd REAL DEFAULT 100.0,
                monthly_spent_usd REAL DEFAULT 0.0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("INSERT INTO budgets_global (id) VALUES (1)")
        db.commit()
    return path

@pytest.fixture
def config():
    return {}

@pytest.fixture
def model_conf():
    return {
        "max_tokens_per_call": 1000,
        "pricing": {
            "input_per_1k": 0.001,
            "output_per_1k": 0.002
        }
    }

@pytest.mark.asyncio
async def test_budget_allows_small_call(db_path, config, model_conf):
    tracker = BudgetTracker(str(db_path), config)
    mission_id = "m1"
    
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("INSERT INTO missions (id, max_cost_usd) VALUES (?, ?)", (mission_id, 1.0))
        await db.commit()
        
    async with await tracker.guard(mission_id, "agent", model_conf) as guard:
        # Reservation should happen
        pass
        
        await guard.commit(actual_cost=0.001, actual_tokens=100)
        
    async with aiosqlite.connect(str(db_path)) as db:
        async with db.execute("SELECT spent_cost_usd FROM missions WHERE id=?", (mission_id,)) as cursor:
            row = await cursor.fetchone()
            assert row[0] == 0.001

@pytest.mark.asyncio
async def test_budget_blocks_when_mission_exceeded(db_path, config, model_conf):
    tracker = BudgetTracker(str(db_path), config)
    mission_id = "m2"
    
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("INSERT INTO missions (id, max_cost_usd, spent_cost_usd) VALUES (?, ?, ?)", (mission_id, 1.0, 0.999))
        await db.commit()
        
    # Worst case cost for 1000 tokens @ 0.002/1k = 0.002
    # 0.999 + 0.002 = 1.001 > 1.0
    
    with pytest.raises(BudgetExceededError):
        async with await tracker.guard(mission_id, "agent", model_conf) as guard:
            pass

@pytest.mark.asyncio
async def test_global_budget_blocks(db_path, config, model_conf):
    tracker = BudgetTracker(str(db_path), config)
    mission_id = "m3"
    
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("INSERT INTO missions (id, max_cost_usd) VALUES (?, ?)", (mission_id, 100.0))
        await db.execute("UPDATE budgets_global SET daily_spent_usd = 9.999")
        await db.commit()
        
    # Worst case 0.002
    # 9.999 + 0.002 = 10.001 > 10.0
    
    with pytest.raises(BudgetExceededError):
        async with await tracker.guard(mission_id, "agent", model_conf) as guard:
            pass
