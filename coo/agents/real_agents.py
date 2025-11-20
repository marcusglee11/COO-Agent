import uuid
import json
from typing import Any, AsyncGenerator, Dict, List
from coo.agents.base import Agent, Emission
from coo.models import MessageKind

class RealCOO(Agent):
    async def process_stream(
        self, mission: Dict[str, Any], messages: List[Dict[str, Any]]
    ) -> AsyncGenerator[Emission, None]:
        # 0. Handle CONTROL messages (User/System intervention)
        if messages and messages[-1]["kind"] == MessageKind.CONTROL.value:
            control_msg = messages[-1]
            body = control_msg.get("body_json", {})
            if body.get("action") == "resume":
                yield Emission(
                    type="side_effect",
                    data={"state_transition": "executing"}
                )
                return

        # 1. Call LLM to get plan/task
        response = await self.call_llm(mission, messages)
        content = response["content"]
        
        # 2. Parse content (assuming simple text or JSON)
        # For v1, we assume the LLM outputs a task description directly or JSON.
        # Let's assume it outputs JSON with {"task": "..."} or just text.
        
        # Simple logic: Emit TASK to Engineer
        yield Emission(
            type="message",
            data={
                "id": str(uuid.uuid4()),
                "to_agent": "Engineer",
                "kind": MessageKind.TASK.value,
                "status": "pending",
                "body_json": {"content": content}
            }
        )

class RealEngineer(Agent):
    async def process_stream(
        self, mission: Dict[str, Any], messages: List[Dict[str, Any]]
    ) -> AsyncGenerator[Emission, None]:
        # 1. Call LLM to write code
        response = await self.call_llm(mission, messages)
        content = response["content"]
        
        # 2. Extract code (naive: assume content IS the code or contains it)
        # In a real system, we'd parse markdown code blocks.
        # For v1, let's assume the LLM returns a JSON with {"filename": "main.py", "code": "..."}
        # OR we just take the content as code if it looks like python.
        
        # Let's try to parse JSON
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                 content = content.split("```")[1] # Might be python
            
            data = json.loads(content)
            filename = data.get("filename", "main.py")
            code = data.get("code", "")
        except:
            # Fallback: treat whole content as code (or error)
            filename = "main.py"
            code = content
            
        # 3. Security Check: Validate filename
        if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
             # Security violation!
             # For now, we just sanitize or reject. Let's reject by emitting an error message back to self?
             # Or just sanitize to a safe default.
             filename = "safe_main.py"
        
        if not filename.endswith(".py"):
            filename += ".py"

        artifact_id = str(uuid.uuid4())
        
        # We'll use a side_effect to request artifact creation
        yield Emission(
            type="side_effect",
            data={
                "action": "save_artifact",
                "artifact_id": artifact_id,
                "filename": filename,
                "content": code
            }
        )
        
        # 4. Emit sandbox_execute
        yield Emission(
            type="sandbox_execute",
            data={
                "artifact_id": artifact_id,
                "entrypoint": f"python {filename}",
                "timeout": 300,
                "dedupe_id": f"run_{uuid.uuid4()}", # Should be deterministic if possible, but UUID is safe for now
                "reply_to": "QA",
            },
        )

class RealQA(Agent):
    async def process_stream(
        self, mission: Dict[str, Any], messages: List[Dict[str, Any]]
    ) -> AsyncGenerator[Emission, None]:
        # 1. Call LLM to review
        response = await self.call_llm(mission, messages)
        content = response["content"]
        
        # 2. Parse JSON
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                 content = content.split("```")[1]
            
            data = json.loads(content)
            verdict = data.get("verdict", "rejected").lower()
            reasoning = data.get("reasoning", "No reasoning provided.")
        except:
            # Fallback
            verdict = "rejected"
            reasoning = f"Failed to parse QA response: {content}"

        # 3. Decision
        if verdict == "approved":
            yield Emission(
                type="message",
                data={
                    "id": str(uuid.uuid4()),
                    "to_agent": "COO",
                    "kind": MessageKind.RESULT.value,
                    "status": "pending",
                    "body_json": {"content": "Approved", "details": reasoning}
                }
            )
            # Also complete mission?
            yield Emission(
                type="side_effect",
                data={"state_transition": "completed"}
            )
        else:
            yield Emission(
                type="message",
                data={
                    "id": str(uuid.uuid4()),
                    "to_agent": "Engineer",
                    "kind": MessageKind.TASK.value, # Send back to Engineer
                    "status": "pending",
                    "body_json": {"content": f"Rejected: {reasoning}", "details": content}
                }
            )
