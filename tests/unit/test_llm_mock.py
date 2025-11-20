import pytest
from unittest.mock import MagicMock, patch
from coo.llm import ModelClient, SecurityViolation

@pytest.fixture
def config():
    return {
        "models": {
            "test-model": {
                "max_tokens_per_call": 100,
                "pricing": {
                    "input_per_1k": 0.01,
                    "output_per_1k": 0.02
                }
            }
        }
    }

@pytest.mark.asyncio
async def test_token_limit_enforcement(config):
    client = ModelClient(config)
    
    # Mock sync chat response
    mock_response = MagicMock()
    mock_response.content = "Test"
    mock_response.role = "assistant"
    mock_response.model = "test-model"
    mock_response.usage = {"total_tokens": 101} # Exceeds 100
    mock_response.latency_ms = 10
    
    client._sync_chat = MagicMock(return_value=mock_response)
    
    with pytest.raises(SecurityViolation):
        await client.chat("agent", {}, [], "test-model")

@pytest.mark.asyncio
async def test_cost_calculation(config):
    client = ModelClient(config)
    
    mock_response = MagicMock()
    mock_response.content = "Test"
    mock_response.role = "assistant"
    mock_response.model = "test-model"
    mock_response.usage = {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200}
    mock_response.latency_ms = 10
    
    # Temporarily increase limit for this test
    config["models"]["test-model"]["max_tokens_per_call"] = 1000
    
    client._sync_chat = MagicMock(return_value=mock_response)
    
    result = await client.chat("agent", {}, [], "test-model")
    
    # Input: 100 * 0.01 / 1000 = 0.001
    # Output: 100 * 0.02 / 1000 = 0.002
    # Total: 0.003
    assert result["cost_usd"] == pytest.approx(0.003)
