import aiosqlite
import structlog
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone

log = structlog.get_logger()

class BudgetExceededError(Exception):
    pass

class BudgetGuard:
    def __init__(
        self, 
        db_path: Path, 
        config: Dict, 
        mission_id: str, 
        agent_name: str, 
        model_conf: Dict
    ):
        self.db_path = db_path
        self.config = config
        self.mission_id = mission_id
        self.agent_name = agent_name
        self.model_conf = model_conf
        self.reservation = 0.0
        self.conn = None

    async def __aenter__(self):
        self.conn = await aiosqlite.connect(str(self.db_path))
        try:
            await self.conn.execute("BEGIN IMMEDIATE")
            
            # 1. Calculate worst-case cost
            max_tokens = self.model_conf.get("max_tokens_per_call", 4000)
            pricing = self.model_conf.get("pricing", {})
            
            # Worst case: Max tokens for both input (prompt) and output (completion)
            # We assume the prompt could be up to max_tokens (or context window limit) 
            # and output up to max_tokens.
            # A safer conservative estimate for reservation:
            input_price = pricing.get("input_per_1k", 0.001)
            output_price = pricing.get("output_per_1k", 0.002)
            
            self.reservation = (
                (max_tokens / 1000.0) * input_price + 
                (max_tokens / 1000.0) * output_price
            )
            
            # 2. Check Budgets
            # Mission Budget
            async with self.conn.execute(
                "SELECT spent_cost_usd, max_cost_usd FROM missions WHERE id = ?", 
                (self.mission_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    raise ValueError(f"Mission {self.mission_id} not found")
                
                spent = row[0]
                max_cost = row[1]
                
                if spent + self.reservation > max_cost:
                    await self.conn.rollback()
                    raise BudgetExceededError(f"Mission budget exceeded: {spent} + {self.reservation} > {max_cost}")

            # Global Budget
            async with self.conn.execute("SELECT * FROM budgets_global WHERE id = 1") as cursor:
                row = await cursor.fetchone()
                if row:
                    daily_spent = row[2]
                    daily_budget = row[1]
                    monthly_spent = row[4]
                    monthly_budget = row[3]
                    updated_at = row[5]
                    
                    # Check for reset (simplified: if date changed)
                    # In real impl, parse date. For now assume updated_at is recent.
                    # TODO: Implement reset logic based on date(updated_at)
                    
                    if daily_spent + self.reservation > daily_budget:
                        await self.conn.rollback()
                        raise BudgetExceededError(f"Daily budget exceeded")
                        
                    if monthly_spent + self.reservation > monthly_budget:
                        await self.conn.rollback()
                        raise BudgetExceededError(f"Monthly budget exceeded")

            # 3. Reserve
            await self.conn.execute(
                "UPDATE missions SET spent_cost_usd = spent_cost_usd + ? WHERE id = ?",
                (self.reservation, self.mission_id)
            )
            await self.conn.execute(
                "UPDATE budgets_global SET daily_spent_usd = daily_spent_usd + ?, monthly_spent_usd = monthly_spent_usd + ? WHERE id = 1",
                (self.reservation, self.reservation)
            )
            await self.conn.commit()
            
            # CRITICAL: Close connection to release lock during LLM call
            await self.conn.close()
            self.conn = None
            
            return self
            
        except Exception:
            if self.conn:
                await self.conn.close()
                self.conn = None
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # If exception occurred during LLM call, we need to refund the reservation
        if exc_type:
            # Refund reservation
            async with aiosqlite.connect(str(self.db_path)) as db:
                await db.execute("BEGIN IMMEDIATE")
                await db.execute(
                    "UPDATE missions SET spent_cost_usd = spent_cost_usd - ? WHERE id = ?",
                    (self.reservation, self.mission_id)
                )
                await db.execute(
                    "UPDATE budgets_global SET daily_spent_usd = daily_spent_usd - ?, monthly_spent_usd = monthly_spent_usd - ? WHERE id = 1",
                    (self.reservation, self.reservation)
                )
                await db.commit()

    async def commit(self, actual_cost: float, actual_tokens: int):
        # New transaction to adjust
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute("BEGIN IMMEDIATE")
            
            # Subtract reservation, add actual
            diff = actual_cost - self.reservation
            
            await db.execute(
                "UPDATE missions SET spent_cost_usd = spent_cost_usd + ? WHERE id = ?",
                (diff, self.mission_id)
            )
            await db.execute(
                "UPDATE budgets_global SET daily_spent_usd = daily_spent_usd + ?, monthly_spent_usd = monthly_spent_usd + ? WHERE id = 1",
                (diff, diff)
            )
            
            # Check if we blew the budget with actuals
            async with db.execute("SELECT spent_cost_usd, max_cost_usd FROM missions WHERE id = ?", (self.mission_id,)) as cursor:
                row = await cursor.fetchone()
                if row and row[0] > row[1]:
                     # We exceeded, but we already spent it. 
                     # We should probably raise so orchestrator pauses.
                     await db.commit()
                     raise BudgetExceededError(f"Mission budget exceeded after commit: {row[0]} > {row[1]}")
            
            await db.commit()
            
            # Reset reservation so __aexit__ doesn't refund it if called after commit
            self.reservation = 0.0


class BudgetTracker:
    def __init__(self, db_path: Path, config: Dict):
        self.db_path = db_path
        self.config = config

    async def guard(
        self,
        mission_id: str,
        agent_name: str,
        model_conf: Dict,
    ) -> BudgetGuard:
        return BudgetGuard(self.db_path, self.config, mission_id, agent_name, model_conf)
