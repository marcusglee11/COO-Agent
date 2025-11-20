from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional

@dataclass
class Emission:
    type: str  # "message", "side_effect", "sandbox_execute"
    data: Dict[str, Any]


class Agent(ABC):
    def __init__(self, name: str, model_client=None, prompt_manager=None, budget_tracker=None, model_name: str = "default"):
        self.name = name
        self.model_client = model_client
        self.prompt_manager = prompt_manager
        self.budget_tracker = budget_tracker
        self.model_name = model_name
        self.timeout_seconds: int = 300

    @abstractmethod
    async def process_stream(
        self, mission: Dict[str, Any], messages: List[Dict[str, Any]]
    ) -> AsyncGenerator[Emission, None]:
        """Process incoming messages and yield emissions"""
        pass

    async def call_llm(self, mission: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.model_client or not self.budget_tracker:
            raise RuntimeError("Agent not initialized with LLM/Budget components")

        model_conf = self.model_client.get_model_conf(self.model_name)

        async with await self.budget_tracker.guard(
            mission_id=mission["id"],
            agent_name=self.name,
            model_conf=model_conf,
        ) as guard:

            # Build messages
            messages = self.prompt_manager.build_messages(self.name, mission, history)

            # Call LLM
            result = await self.model_client.chat(
                agent_name=self.name,
                mission=mission,
                messages=messages,
                model_name=self.model_name,
            )

            # Commit budget with actuals
            await guard.commit(
                actual_cost=result["cost_usd"],
                actual_tokens=result["usage"]["total_tokens"],
            )

        return result
