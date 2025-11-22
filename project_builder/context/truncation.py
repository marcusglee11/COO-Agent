TRUNCATION_MARKER = "[...TRUNCATED BY COO...]"
MAX_REPAIR_CONTEXT_CHARS = 2000

def truncate_repair_context(text: str) -> str:
    """
    Truncates repair_context to exactly the first 2000 Unicode code points.
    No word-boundary logic, no "smart" trimming.
    """
    if text is None:
        return ""
    return text[:MAX_REPAIR_CONTEXT_CHARS]
