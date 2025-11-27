import asyncio
from pathlib import Path
from coo.sandbox import SandboxRunner
from coo.message_store import MessageStore
import structlog
import logging

# Configure logging to print to stdout
structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logging.basicConfig(level=logging.DEBUG)

async def main():
    db_path = Path("debug.db")
    store = MessageStore(db_path)
    await store.initialize()
    
    runner = SandboxRunner(db_path, {"temp_dir": "debug_workspace"})
    
    print("Running hello world...")
    result = await runner.run_script('print("Hello World")')
    print(f"Exit Code: {result.exit_code}")
    print(f"Stdout: {result.stdout}")
    print(f"Stderr: {result.stderr}")
    print(f"Error Class: {result.error_class}")

if __name__ == "__main__":
    asyncio.run(main())
