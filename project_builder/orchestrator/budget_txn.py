import sqlite3

def try_charge_budget(conn: sqlite3.Connection, mission_id: str, task_id: str | None, cost: float, is_repair_attempt: bool) -> bool:
    """
    Atomically attempts to charge `cost` to the mission budget, and if
    is_repair_attempt, also to the task repair budget. Returns True on success
    (COMMIT), False on failure (ROLLBACK).
    """
    cur = conn.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE;")

        # 1. Main mission budget
        cur.execute(
            """
            UPDATE missions
            SET spent_cost_usd = spent_cost_usd + :cost
            WHERE id = :mid
              AND spent_cost_usd + :cost <= max_cost_usd;
            """,
            {"cost": cost, "mid": mission_id},
        )
        cur.execute("SELECT changes()")
        main_ok = cur.fetchone()[0] == 1

        repair_ok = True
        if is_repair_attempt and task_id:
            cur.execute(
                """
                UPDATE mission_tasks
                SET repair_budget_spent_usd = repair_budget_spent_usd + :cost
                WHERE id = :tid
                  AND repair_budget_spent_usd + :cost <= (
                      SELECT repair_budget_usd FROM missions WHERE id = :mid
                  );
                """,
                {"cost": cost, "tid": task_id, "mid": mission_id},
            )
            cur.execute("SELECT changes()")
            repair_ok = cur.fetchone()[0] == 1

        if main_ok and repair_ok:
            conn.commit()
            return True
        else:
            conn.rollback()
            return False
            
    except Exception:
        conn.rollback()
        raise
