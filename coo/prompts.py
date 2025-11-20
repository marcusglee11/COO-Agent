import os
from pathlib import Path
from typing import Dict, Any, List
import structlog

log = structlog.get_logger()

class PromptManager:
    def __init__(self, prompts_dir: Path):
        self.prompts_dir = prompts_dir
        if not self.prompts_dir.exists():
            log.warning("prompts_dir_not_found", path=str(prompts_dir))
            self.prompts_dir.mkdir(parents=True, exist_ok=True)

    def _read_prompt(self, rel_path: str) -> str:
        path = self.prompts_dir / rel_path
        if not path.exists():
            # Fallback defaults
            if "coo" in rel_path:
                return "You are the Chief Operating Officer. Manage the mission."
            if "engineer" in rel_path:
                return "You are a Senior Software Engineer. Write code."
            if "qa" in rel_path:
                return "You are a QA Engineer. Review code."
            return "You are a helpful assistant."
        return path.read_text(encoding="utf-8")

    def build_messages(
        self, 
        agent_name: str, 
        mission: Dict[str, Any], 
        history: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        Constructs message list:
        1. Agent System Prompt
        2. Mission Context
        3. Last K History
        """
        messages = []
        
        # 1. Agent System Prompt
        system_prompt = self._read_prompt(f"{agent_name.lower()}/system.md")
        messages.append({"role": "system", "content": system_prompt})
        
        # 2. Mission Context
        mission_context = f"Mission ID: {mission['id']}\nDescription: {mission['description']}"
        messages.append({"role": "system", "content": mission_context})
        
        # 3. Last K History (K=5)
        k = 5
        recent_history = history[-k:] if history else []
        
        for msg in recent_history:
            # Map internal message format to OpenAI format
            # Internal: from_agent, body_json (needs parsing?)
            # We assume body_json is already dict or we treat it as string
            
            role = "user" # Default? Or do we map agents to roles?
            # If from_agent == self, it's 'assistant'. Else 'user'.
            if msg["from_agent"] == agent_name:
                role = "assistant"
            else:
                role = "user"
                
            content = str(msg.get("body_json", ""))
            messages.append({"role": role, "content": content})
            
        return messages
