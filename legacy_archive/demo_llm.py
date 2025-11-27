import asyncio
from pathlib import Path
from coo.llm import ModelClient
from coo.prompts import PromptManager

# IMPORTANT: set this to a real OpenRouter model ID, e.g.
# "deepseek/deepseek-chat" or "glm-4-9b-chat"
MODEL_ID = "deepseek/deepseek-chat"

config = {
    "models": {
        MODEL_ID: {
            "max_tokens_per_call": 256,
            "pricing": {
                "input_per_1k": 0.00014,
                "output_per_1k": 0.00028,
            },
        }
    }
}


async def main():
    client = ModelClient(config)
    prompts = PromptManager(Path("prompts"))

    mission = {
        "id": "demo_mission",
        "description": "Tiny demo mission: just answer a question."
    }
    history: list[dict] = []

    messages = prompts.build_messages("COO", mission, history)
    messages.append({
        "role": "user",
        "content": "In one sentence, describe what this COO system does."
    })

    result = await client.chat(
        agent_name="COO",
        mission=mission,
        messages=messages,
        model_name=MODEL_ID,  # <- use the real model ID here
    )

    print("\n=== LLM Response ===\n")
    print(result["content"])

    print("\n=== Usage ===")
    print(result["usage"])

    print("\n=== Cost (USD) ===")
    print(result["cost_usd"])


if __name__ == "__main__":
    asyncio.run(main())
