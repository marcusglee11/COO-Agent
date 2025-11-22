import pytest
from project_builder.context.truncation import truncate_repair_context, MAX_REPAIR_CONTEXT_CHARS

def test_truncate_short():
    text = "short"
    assert truncate_repair_context(text) == text

def test_truncate_exact():
    text = "a" * MAX_REPAIR_CONTEXT_CHARS
    assert truncate_repair_context(text) == text

def test_truncate_long():
    text = "a" * (MAX_REPAIR_CONTEXT_CHARS + 100)
    truncated = truncate_repair_context(text)
    assert len(truncated) == MAX_REPAIR_CONTEXT_CHARS
    assert truncated == text[:MAX_REPAIR_CONTEXT_CHARS]

def test_truncate_unicode():
    # Multibyte chars
    char = "👍" # 1 codepoint
    text = char * (MAX_REPAIR_CONTEXT_CHARS + 10)
    truncated = truncate_repair_context(text)
    assert len(truncated) == MAX_REPAIR_CONTEXT_CHARS
    assert truncated == text[:MAX_REPAIR_CONTEXT_CHARS]
