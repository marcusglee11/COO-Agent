import asyncio
import uuid
from pathlib import Path

from coo.message_store import MessageStore
from coo.models import MessageKind


async def seed():
    # Use the same DB path as the main app
    db_path = Path.home() / ".local" / "share" / "coo" / "coo.db"
    store = MessageStore(db_path)
    await store.initialize()

    mission_id = f"mission_pi_{uuid.uuid4().hex[:8]}"
    print(f"Seeding Monte Carlo Pi mission: {mission_id}")

    description = (
        "Monte Carlo Pi estimation test: "
        "Engineer and Sandbox should collaborate to produce a Python script "
        "that estimates π using 1,000,000 Monte Carlo samples and prints the estimate."
    )

    await store.create_mission(
        {
            "id": mission_id,
            "description": description,
        }
    )

    # Initial user task to COO
    msg_id = str(uuid.uuid4())
    task_text = (
        "Please create a Python script that estimates π using 1,000,000 "
        "Monte Carlo random samples in the unit square. The script should:\n"
        "- Use random points (x, y) in [0, 1] × [0, 1]\n"
        "- Count how many points fall inside the unit circle (x^2 + y^2 <= 1)\n"
        "- Estimate π ≈ 4 * (inside / total)\n"
        "- Print the estimate of π clearly to stdout.\n"
        "Keep the code simple and self-contained (no external libraries beyond the standard library)."
    )

    await store.deliver_message(
        {
            "id": msg_id,
            "mission_id": mission_id,
            "from_agent": "USER",
            "to_agent": "COO",
            "kind": MessageKind.TASK.value,
            "status": "pending",
            "body_json": {"task": task_text},
        }
    )

    print(f"Seeded Monte Carlo Pi mission {mission_id} with initial message {msg_id}")


if __name__ == "__main__":
    asyncio.run(seed())
