import os
import sys
import json
import asyncio
import hashlib
import uuid
import time
import logging
from unittest.mock import patch

import argparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ReplayHarness")

def run_replay_harness(mission_path: str, output_dir: str, amu0_path: str, mode: str):
    """
    Runs the mission in a deterministic harness.
    Designed to be run as a subprocess with pinned environment.
    """
    logger.info(f"Starting Replay Harness. Mission: {mission_path}, Output: {output_dir}, Mode: {mode}")
    
    # Setup Python Path
    sys.path.append(os.getcwd())
    
    try:
        from coo.orchestrator import Orchestrator
        from coo.message_store import MessageStore
    except ImportError as e:
        logger.error(f"Could not import COO modules: {e}")
        sys.exit(1)

    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    db_path = os.path.join(output_dir, "mission.db")
    
    # R6 C.2: Configure SQLite for Determinism
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        # R6 A.8: Deterministic DB Enforcement
        # journal_mode=DELETE (WAL is non-deterministic across runs due to checkpointing timing)
        conn.execute("PRAGMA journal_mode = DELETE")
        conn.execute("PRAGMA synchronous = FULL")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA locking_mode = EXCLUSIVE")
        conn.execute("PRAGMA page_size = 4096")
        conn.execute("PRAGMA auto_vacuum = NONE")
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to set SQLite PRAGMAs: {e}")

    # --- Mocks ---
    class MockModelClient:
        def __init__(self, config):
            pass
        async def generate(self, prompt, **kwargs):
            # Deterministic response based on prompt hash
            prompt_hash = hashlib.sha256(str(prompt).encode("utf-8")).hexdigest()[:8]
            return f"Mock Response {prompt_hash}"

    # Import External Trace Replayer (A.7)
    try:
        from coo_runtime.runtime.external_trace_replayer import ExternalTraceReplayer
    except ImportError:
        # If running as script, path might need adjustment or assume it's in pythonpath
        # For now, let's assume pythonpath is set correctly by replay.py
        pass

    class TraceReplayClientAdapter:
        """
        Adapter for ExternalTraceReplayer to match ModelClient interface.
        """
        def __init__(self, config):
            trace_path = os.path.join(amu0_path, "external_trace.jsonl")
            self.replayer = ExternalTraceReplayer(trace_path)

        async def generate(self, prompt, **kwargs):
            return self.replayer.replay_call(prompt)

    class DeterministicUUID:
        def __init__(self):
            self.counter = 0
        def __call__(self):
            self.counter += 1
            return uuid.UUID(int=self.counter)
    
    det_uuid = DeterministicUUID()

    async def run_orchestrator():
        # Initialize Store
        store = MessageStore(db_path)
        await store.initialize() 
        
        # Load Mission
        with open(mission_path, "r") as f:
            mission_data = json.load(f)
        
        if "id" not in mission_data:
            mission_data["id"] = str(det_uuid())
        
        if "description" not in mission_data:
            mission_data["description"] = "Replay Mission"
            
        await store.create_mission(mission_data)
        
        config = {
            "agents": {
                "COO": {"model": "mock"},
                "Engineer": {"model": "mock"},
                "QA": {"model": "mock"}
            },
            "tick_interval_seconds": 0.1
        }
        
        orch = Orchestrator(store, config)
        
        # Run for fixed ticks
        task = asyncio.create_task(orch.run())
        await asyncio.sleep(1) # Run for 1 second (10 ticks)
        orch.running = False
        await task
        
    # Run with mocks
    try:
        # Select Client based on Mode
        if mode == "deep":
            ClientClass = TraceReplayClientAdapter
        else:
            ClientClass = MockModelClient

        with patch("coo.llm.ModelClient", ClientClass), \
             patch("uuid.uuid4", side_effect=det_uuid), \
             patch("time.time", return_value=1700000000.0):
             
            # Use explicit event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(run_orchestrator())
            finally:
                loop.close()
                
        logger.info("Replay Harness Complete.")
        
    except Exception as e:
        logger.error(f"Replay Execution Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mission_path")
    parser.add_argument("output_dir")
    parser.add_argument("--amu0", required=True, help="Path to AMU0")
    parser.add_argument("--mode", default="fast", choices=["fast", "deep"], help="Replay mode")
    
    args = parser.parse_args()
    
    run_replay_harness(args.mission_path, args.output_dir, args.amu0, args.mode)
