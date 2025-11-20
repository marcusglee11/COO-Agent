import pytest
from coo.logging_utils import scrub_secrets

def test_scrub_secrets_direct_keys():
    event = {
        "api_key": "sk-1234567890abcdef1234567890abcdef",
        "password": "supersecretpassword",
        "other": "value"
    }
    scrubbed = scrub_secrets(None, None, event)
    assert scrubbed["api_key"] == "***REDACTED***"
    assert scrubbed["password"] == "***REDACTED***"
    assert scrubbed["other"] == "value"

def test_scrub_secrets_nested_dict():
    event = {
        "config": {
            "api_key": "sk-1234567890abcdef1234567890abcdef",
            "nested": {
                "token": "secret_token"
            }
        }
    }
    scrubbed = scrub_secrets(None, None, event)
    assert scrubbed["config"]["api_key"] == "***REDACTED***"
    assert scrubbed["config"]["nested"]["token"] == "***REDACTED***"

def test_scrub_secrets_in_string():
    event = {
        "message": "Here is my api_key=sk-1234567890abcdef1234567890abcdef for you",
        "error": "Invalid token: sk-9876543210fedcba9876543210fedcba"
    }
    scrubbed = scrub_secrets(None, None, event)
    assert "***REDACTED***" in scrubbed["message"]
    assert "sk-1234567890abcdef" not in scrubbed["message"]
    assert "***REDACTED***" in scrubbed["error"]
    assert "sk-9876543210fedcba" not in scrubbed["error"]

def test_scrub_secrets_list():
    event = {
        "items": [
            "normal",
            "sk-1234567890abcdef1234567890abcdef",
            {"api_key": "secret"}
        ]
    }
    scrubbed = scrub_secrets(None, None, event)
    assert scrubbed["items"][0] == "normal"
    assert scrubbed["items"][1] == "***REDACTED***"
    assert scrubbed["items"][2]["api_key"] == "***REDACTED***"
