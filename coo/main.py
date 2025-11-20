import asyncio
from pathlib import Path

import structlog
import yaml

from coo.message_store import MessageStore
from coo.orchestrator import Orchestrator

from coo.logging_utils import scrub_secrets

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        scrub_secrets,
        structlog.processors.JSONRenderer()
    ]
)
log = structlog.get_logger()


def load_config() -> dict:
    """
    Load orchestrator, budgets, sandbox, and model/agent config into a single
    dict in the shape expected by Orchestrator.
    """
    base_dir = Path(__file__).resolve().parent.parent
    config_dir = base_dir / "config"

    # Orchestrator + budgets + backpressure
    with open(config_dir / "orchestrator.yaml", "r", encoding="utf-8") as f:
        orch_cfg = yaml.safe_load(f) or {}

    # Model + agent definitions
    with open(config_dir / "models.yaml", "r", encoding="utf-8") as f:
        models_cfg = yaml.safe_load(f) or {}

    # Sandbox config (separate file)
    sandbox_cfg = {}
    sandbox_path = config_dir / "sandbox.yaml"
    if sandbox_path.exists():
        with open(sandbox_path, "r", encoding="utf-8") as f:
            sandbox_cfg = yaml.safe_load(f) or {}

    # Merge orchestrator + models into a single dict.
    # `orch_cfg` looks like:
    #   {
    #       "orchestrator": {...},
    #       "budgets": {...},
    #       "backpressure": {...},
    #   }
    config: dict = {}
    config.update(orch_cfg)
    config.update(models_cfg)

    # Attach sandbox config under the key Orchestrator expects
    if sandbox_cfg:
        config["sandbox"] = sandbox_cfg

    # Convenience: hoist tick_interval_seconds to the top level so that
    # Orchestrator.tick_interval picks it up.
    orch_section = orch_cfg.get("orchestrator", {})
    if "tick_interval_seconds" in orch_section and "tick_interval_seconds" not in config:
        config["tick_interval_seconds"] = orch_section["tick_interval_seconds"]

    return config


async def main() -> None:
    # DB path must match what the rest of the system expects
    db_path = Path.home() / ".local" / "share" / "coo" / "coo.db"
    
    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    config = load_config()

    # Ensure schema exists
    store = MessageStore(db_path)
    await store.initialize()

    log.info("coo_started", db_path=str(db_path), version="0.6")

    # Orchestrator now owns BudgetTracker and SandboxRunner
    orchestrator = Orchestrator(store, config)
    await orchestrator.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("coo_shutdown", reason="user_interrupt")
    except Exception as e:
        log.critical("coo_fatal_error", error=str(e))
        raise
