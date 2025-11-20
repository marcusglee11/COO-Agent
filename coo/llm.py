import os
import time
import structlog
import httpx
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import asyncio

log = structlog.get_logger()

class SecurityViolation(Exception):
    pass

@dataclass
class LLMResponse:
    content: str
    role: str
    model: str
    usage: Dict[str, int]
    cost_usd: float
    latency_ms: float

class ModelClient:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            log.warning("OPENROUTER_API_KEY not set. LLM calls will fail.")
        
        self.base_url = "https://openrouter.ai/api/v1"
        # Use sync client for thread pool
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://github.com/coo-agent",
                "X-Title": "COO Agent",
            },
            timeout=60.0
        )
        self.executor = ThreadPoolExecutor(max_workers=5)

    def close(self):
        self.client.close()
        self.executor.shutdown()

    def _calculate_cost(self, model_conf: Dict, usage: Dict[str, int]) -> float:
        pricing = model_conf.get("pricing", {})
        
        input_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0))
        output_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0))
        
        input_cost = pricing.get("input_per_1k", 0) * (input_tokens / 1000.0)
        output_cost = pricing.get("output_per_1k", 0) * (output_tokens / 1000.0)
        
        return input_cost + output_cost

    def get_model_conf(self, model_name: str) -> Dict:
        return self.config.get("models", {}).get(model_name, {})

    async def chat(
        self, 
        agent_name: str,
        mission: Dict[str, Any],
        messages: List[Dict[str, str]], 
        model_name: str,
    ) -> Dict[str, Any]:
        
        model_conf = self.get_model_conf(model_name)
        max_tokens_per_call = model_conf.get("max_tokens_per_call", 4000)
        
        # Run sync call in thread pool
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            self.executor,
            self._sync_chat,
            messages,
            model_name,
            max_tokens_per_call
        )
        
        # Enforce token limit
        total_tokens = response.usage.get("total_tokens", 0)
        if total_tokens > max_tokens_per_call:
            raise SecurityViolation(f"Token limit exceeded: {total_tokens} > {max_tokens_per_call}")
            
        cost = self._calculate_cost(model_conf, response.usage)
        
        return {
            "content": response.content,
            "usage": response.usage,
            "cost_usd": cost,
            "role": response.role,
            "model": response.model,
            "latency_ms": response.latency_ms
        }

    def _sync_chat(
        self, 
        messages: List[Dict[str, str]], 
        model: str,
        max_tokens: int
    ) -> LLMResponse:
        start_time = time.time()
        
        # Proactive truncation (simplified: character count approximation)
        # 1 token ~= 4 chars. 
        # Limit prompt to 50% of max_tokens to leave room for response.
        max_prompt_tokens = max_tokens // 2
        max_prompt_chars = max_prompt_tokens * 4
        
        # Truncate last message content if too long
        # (Naive implementation, better would be to drop oldest history)
        if messages:
            last_msg = messages[-1]
            if len(last_msg.get("content", "")) > max_prompt_chars:
                last_msg["content"] = last_msg["content"][:max_prompt_chars] + "... (truncated)"

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        
        try:
            log.info("llm_request", model=model, message_count=len(messages))
            response = self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            
            latency = (time.time() - start_time) * 1000
            
            choice = data["choices"][0]
            content = choice["message"]["content"]
            role = choice["message"]["role"]
            usage = data.get("usage", {})
            
            log.info(
                "llm_response", 
                model=model, 
                latency_ms=latency, 
                tokens=usage.get("total_tokens")
            )
            
            return LLMResponse(
                content=content,
                role=role,
                model=model,
                usage=usage,
                cost_usd=0.0, # Calculated later
                latency_ms=latency
            )
            
        except httpx.HTTPStatusError as e:
            log.error("llm_api_error", status=e.response.status_code, error=e.response.text)
            raise
        except Exception as e:
            log.error("llm_call_failed", error=str(e))
            raise
