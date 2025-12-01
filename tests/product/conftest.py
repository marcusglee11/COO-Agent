import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture(autouse=True)
def mock_model_client():
    """Mock ModelClient for all product tests to avoid network calls and ensure determinism."""
    # Patch where it is used: coo.orchestrator imports ModelClient
    with patch("coo.orchestrator.ModelClient") as MockClient:
        mock_instance = MockClient.return_value
        # Mock chat method
        async def mock_chat(*args, **kwargs):
            return {
                "content": "The Agentic Compute Engine (ACE) is a secure, distributed runtime for autonomous agents. It ensures determinism via a signed Mission Log and separates reasoning from execution to prevent corruption.",
                "model": "mock-model",
                "cost_usd": 0.0,
                "usage": {"total_tokens": 100}
            }
        mock_instance.chat.side_effect = mock_chat
        yield MockClient
