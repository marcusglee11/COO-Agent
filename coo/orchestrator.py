import asyncio
import uuid
import base64
import json
from typing import Dict, List, Optional
from pathlib import Path
import structlog

from coo.agents.base import Agent
from coo.agents.real_agents import RealCOO, RealEngineer, RealQA
from coo.budget import BudgetTracker, BudgetExceededError
from coo.message_store import MessageStore
from coo.models import MessageKind, MessageStatus
from coo.sandbox import SandboxRunner
from coo.llm import ModelClient
from coo.prompts import PromptManager

log = structlog.get_logger()

class Orchestrator:
    def __init__(self, store: MessageStore, config: Dict):
        self.store = store
        self.config = config
        
        # Initialize components
        self.model_client = ModelClient(config)
        self.prompt_manager = PromptManager(Path("prompts"))
        self.budget_tracker = BudgetTracker(store.db_path, config.get("budgets", {}))
        
        # Initialize Sandbox
        self.sandbox = SandboxRunner(store.db_path, config.get("sandbox", {}))
        
        # Initialize Agents
        agents_cfg = config.get("agents", {})
        self.agents: Dict[str, Agent] = {
            "COO": RealCOO(
                "COO",
                self.model_client,
                self.prompt_manager,
                self.budget_tracker,
                model_name=agents_cfg.get("COO", {}).get("model", "default"),
                temperature=agents_cfg.get("COO", {}).get("temperature", 0.5),
            ),
            "Engineer": RealEngineer(
                "Engineer",
                self.model_client,
                self.prompt_manager,
                self.budget_tracker,
                model_name=agents_cfg.get("Engineer", {}).get("model", "default"),
                temperature=agents_cfg.get("Engineer", {}).get("temperature", 0.5),
            ),
            "QA": RealQA(
                "QA",
                self.model_client,
                self.prompt_manager,
                self.budget_tracker,
                model_name=agents_cfg.get("QA", {}).get("model", "default"),
                temperature=agents_cfg.get("QA", {}).get("temperature", 0.5),
            ),
        }

        self.running = False
        self.tick_interval = config.get("tick_interval_seconds", 1)

    async def run(self):
        self.running = True
        log.info("orchestrator_started")
        
        # Recover crashed sandbox runs
        await self.sandbox.recover_crashed_runs()

        while self.running:
            try:
                await self.tick()
                await asyncio.sleep(self.tick_interval)
            except Exception as e:
                log.error("orchestrator_tick_error", error=str(e))
                await asyncio.sleep(5)  # Backoff on error

    async def tick(self):
        # 1. Reclaim stale messages
        await self.store.reclaim_stale_messages()
        
        # Backpressure check (per mission)
        # We iterate over active missions to check for backpressure
        # For simplicity in this loop, we'll check backpressure when processing messages 
        # or we can iterate missions. 
        # Since we process by agent, let's check backpressure before claiming messages for a mission.
        # But claim_pending_messages doesn't take a mission_id by default (it takes None).
        # So we might pick up messages for a mission that should be paused.
        # Ideally, we should check backpressure for all active missions.
        
        # For now, let's implement a simple check: if ANY mission has too many pending messages, 
        # we pause it.
        # We need to get active missions first.
        # This might be expensive to do every tick if there are many missions.
        # But for now it's fine.
        
        # Actually, the spec says: "If pending > 50, transition to paused_error".
        # We can do this check when we load the mission context in process_message, 
        # OR we can do a separate sweep.
        # A separate sweep is safer to prevent the queue from growing if agents are fast.
        
        # Let's do it in process_message for the specific mission we are working on.
        # That avoids iterating all missions every tick.


        # 2. Process pending messages for each agent
        for agent_name, agent in self.agents.items():
            # Claim a batch of messages
            messages = await self.store.claim_pending_messages(
                agent_name, mission_id=None, limit=1
            )
            
            if messages:
                for msg in messages:
                    await self.process_message(agent, msg)

    async def process_message(self, agent: Agent, msg: Dict):
        log.info("processing_message", msg_id=msg["id"], agent=agent.name)

        # Get mission context
        mission = await self.store.get_mission(msg["mission_id"])
        if not mission:
            log.error("mission_not_found", mission_id=msg["mission_id"])
            return
            
        # Check backpressure
        max_pending = self.config.get("backpressure", {}).get("max_pending_messages", 50)
        pending_count = await self.store.count_pending_messages(mission["id"])
        
        if pending_count > max_pending:
            log.warning(
                "backpressure_triggered", 
                mission_id=mission["id"], 
                pending=pending_count, 
                limit=max_pending
            )
            await self.store.update_mission_status(mission["id"], "paused_error")
            await self.store.log_timeline_event(
                mission["id"], 
                "backpressure_triggered", 
                {"pending": pending_count, "limit": max_pending}
            )
            return

        # Get conversation history
        # We fetch the last 10 messages to provide context
        history = await self.store.get_mission_history(mission["id"], limit=10)
        
        # Ensure the current message is in history if it wasn't committed yet?
        # Actually, deliver_message commits it. So it should be in DB.
        # But wait, we just claimed it. It's in DB.
        # So get_mission_history should find it.

        try:
            async for emission in agent.process_stream(mission, history):
                if emission.type == "message":
                    new_msg = emission.data
                    new_msg["id"] = str(uuid.uuid4())
                    new_msg["mission_id"] = msg["mission_id"]
                    new_msg["from_agent"] = agent.name
                    
                    await self.store.deliver_message(new_msg)
                    log.info(
                        "message_emitted",
                        from_agent=agent.name,
                        to_agent=new_msg["to_agent"],
                    )

                elif emission.type == "side_effect":
                    data = emission.data
                    log.info("side_effect", data=data)

                    # 1. Handle Engineer artifact persistence
                    if data.get("action") == "save_artifact":
                        artifact_id = data["artifact_id"]
                        filename = data["filename"]
                        raw_content = data["content"]
                        content_b64 = base64.b64encode(raw_content.encode("utf-8")).decode("ascii")

                        await self.store.save_artifact(
                            mission_id=mission["id"],
                            artifact_id=artifact_id,
                            filename=filename,
                            content_b64=content_b64,
                            mime_type="text/x-python",
                            created_by=agent.name,
                        )

                        await self.store.log_timeline_event(
                            mission["id"],
                            "artifact_saved",
                            {"artifact_id": artifact_id, "filename": filename},
                        )

                    # 2. Handle mission state transitions (existing behaviour)
                    if "state_transition" in data:
                        await self.store.update_mission_status(
                            mission["id"], data["state_transition"]
                        )
                        await self.store.log_timeline_event(
                            mission["id"], 
                            "mission_status_changed", 
                            {"status": data["state_transition"]}
                        )
                
                elif emission.type == "sandbox_execute":
                    data = emission.data
                    log.info("sandbox_execute_request", data=data)
                    
                    result = await self.sandbox.run_artifact(
                        mission_id=msg["mission_id"],
                        artifact_id=data["artifact_id"],
                        entrypoint=data["entrypoint"],
                        dedupe_id=data["dedupe_id"],
                        timeout=data.get("timeout", 300),
                    )
                    
                    await self.store.log_timeline_event(
                        mission["id"], 
                        "sandbox_execution", 
                        {
                            "artifact_id": data["artifact_id"],
                            "exit_code": result.exit_code,
                            "cached": result.cached
                        }
                    )
                    
                    to_agent = data.get("reply_to") or ("QA" if result.exit_code == 0 else "Engineer")
                    
                    # Inject RESULT message
                    await self.store.deliver_message({
                        "id": f"res_{data['dedupe_id']}",
                        "mission_id": msg["mission_id"],
                        "from_agent": "SYSTEM_SANDBOX",
                        "to_agent": to_agent,
                        "kind": MessageKind.RESULT.value,
                        "status": "pending",
                        "body_json": {
                            "sandbox_run_id": data["dedupe_id"],
                            "exit_code": result.exit_code,
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "result_artifact_id": result.result_artifact_id,
                            "error_class": result.error_class,
                            "cached": result.cached,
                        }
                    })

            await self.mark_message_processed(msg["id"])

        except BudgetExceededError:
            log.warning("mission_budget_exceeded", mission_id=mission["id"])
            await self.store.update_mission_status(mission["id"], "paused_budget")
            await self.store.log_timeline_event(
                mission["id"], 
                "budget_exceeded", 
                {"reason": "mission_budget_exceeded"}
            )

        except Exception as e:
            log.error("agent_processing_error", error=str(e), agent=agent.name)

    async def mark_message_processed(self, message_id: str):
        import aiosqlite

        async with aiosqlite.connect(self.store.db_path) as db:
            await db.execute(
                """
                UPDATE messages 
                SET status = 'processed', processed_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """,
                (message_id,),
            )
            await db.commit()

    async def run_mission(self, mission_id: str):
        """Run a specific mission to completion (blocking)."""
        mission = await self.store.get_mission(mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")

        # Parse config to check type
        mission_type = "UNKNOWN"
        mission_config = {}
        if mission.get("config_json"):
            try:
                mission_config = json.loads(mission["config_json"])
                mission_type = mission_config.get("mission_type", "UNKNOWN")
            except:
                pass

        if mission_type == "DEMO_V1_1":
            await self._run_demo_mission(mission, mission_config)
        else:
            raise NotImplementedError("Only DEMO_V1_1 missions are supported in run_mission for now.")

    async def _run_demo_mission(self, mission: Dict, config: Dict):
        """Execute deterministic demo mission logic."""
        import datetime
        
        mission_id = mission["id"]
        
        # Fixed Demo Content
        DEMO_SUMMARY_SOURCE_TEXT = (
            "The Agentic Compute Engine (ACE) is a distributed runtime environment designed to execute "
            "autonomous software agents in a secure, deterministic manner. Unlike traditional container "
            "orchestration systems, ACE enforces strict causality tracking through a cryptographic ledger "
            "known as the Mission Log. Every state transition, external API call, and resource modification "
            "is signed and sequenced, allowing for perfect replayability of any agent session. The system "
            "architecture separates the 'Planner' (LLM-based reasoning core) from the 'Executor' (sandboxed "
            "tool runner), ensuring that AI hallucinations cannot directly corrupt the host environment. "
            "ACE is built on a capability-based security model, where agents must explicitly request "
            "permissions for network access or filesystem writes, which are then granted or denied by a "
            "deterministic policy engine."
        )
        
        DEMO_SUMMARY_PROMPT = (
            "You are helping demonstrate a deterministic runtime.\n"
            "Summarise the following text in one short paragraph:\n\n"
            f"{DEMO_SUMMARY_SOURCE_TEXT}"
        )
        
        # Start
        await self.store.update_mission_status(mission_id, "RUNNING")
        await self.store.log_timeline_event(mission_id, "INIT", {"mission_type": "DEMO_V1_1"})
        
        try:
            messages = [
                {"role": "user", "content": DEMO_SUMMARY_PROMPT}
            ]
            
            # Log MODEL_REQUEST
            await self.store.log_timeline_event(mission_id, "MODEL_REQUEST", {
                "model": "default", # Or resolved model name if available
                "prompt_kind": "demo_summary_v1"
            })
            
            # C4: Enforce parameters (top_p removed)
            response = await self.model_client.chat(
                agent_name="COO",
                mission={"id": mission_id}, 
                messages=messages,
                model_name="default", 
                temperature=0
            )
            
            ai_output = response["content"]
            summary_preview = ai_output[:50] + "..." if len(ai_output) > 50 else ai_output

            # Log MODEL_RESPONSE
            await self.store.log_timeline_event(mission_id, "MODEL_RESPONSE", {
                "summary_preview": summary_preview,
                "summary": ai_output  # Store full summary for CLI receipt
            })
            
            # Log success
            # We keep LLM_CALL for backward compatibility if needed, but spec says MODEL_RESPONSE is key.
            # Let's stick to the spec: INIT -> MODEL_REQUEST -> MODEL_RESPONSE -> COMPLETE
            
            await self.store.update_mission_status(mission_id, "COMPLETED")
            await self.store.log_timeline_event(mission_id, "COMPLETE", {"status": "SUCCESS"})
            
        except Exception as e:
            await self.store.update_mission_status(mission_id, "FAILED")
            await self.store.log_timeline_event(mission_id, "ERROR", {"error": str(e)})
            # Re-raise to ensure CLI knows it failed if it's waiting
            raise
