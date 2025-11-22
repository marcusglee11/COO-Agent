import json
from typing import Any, Protocol
from project_builder.context.truncation import TRUNCATION_MARKER
from project_builder.config.settings import MAX_ARTIFACT_TOKENS

class Tokenizer(Protocol):
    def count_tokens(self, text: str) -> int: ...
    def truncate(self, text: str, max_tokens: int) -> str: ...

def build_context_components(
    system_prompt: str,
    mission_description: str,
    task: dict[str, Any],
    snapshot_files: list[tuple[str, bytes, str]],
    repair_context: str | None,
    qa_feedback: str | None,
    file_tree_str: str,
    tokenizer: Tokenizer,
    max_tokens: int = MAX_ARTIFACT_TOKENS
) -> list[str]:
    """
    Returns ordered list of text components for the LLM.
    Enforces bucket priority and deterministic ordering.
    """
    components = []
    current_tokens = 0
    
    # 1. Base Components
    base_parts = [
        system_prompt,
        f"Mission: {mission_description}",
        f"Task: {task['description']}",
    ]
    if repair_context:
        base_parts.append(f"Repair Context:\n{repair_context}")
    if qa_feedback:
        base_parts.append(f"QA Feedback:\n{qa_feedback}")
    base_parts.append(f"Project Files:\n{file_tree_str}")
    
    for part in base_parts:
        components.append(part)
        current_tokens += tokenizer.count_tokens(part)
        
    if current_tokens >= max_tokens:
        return components

    remaining_tokens = max_tokens - current_tokens
    
    # 2. Identify Buckets
    context_files = []
    if task.get('context_files'):
        try:
            context_files = json.loads(task['context_files'])
        except (json.JSONDecodeError, TypeError):
            pass
            
    bucket_a = []
    bucket_b = []
    
    # snapshot_files is sorted by file_path ASC from snapshot_query
    for path, content, created_at in snapshot_files:
        # Path Traversal Protection
        if ".." in path or path.startswith("/") or path.startswith("\\"):
            continue

        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            continue # Skip binary files
            
        if path in context_files:
            bucket_a.append((path, text))
        else:
            bucket_b.append((path, text, created_at))
            
    # Sort Bucket B: created_at DESC, then file_path ASC
    bucket_b.sort(key=lambda x: (x[2], x[0]), reverse=True)
    # Wait, reverse=True makes created_at DESC (good) but file_path DESC (bad).
    # We want created_at DESC, file_path ASC.
    # So we sort by file_path ASC first, then created_at DESC (stable sort).
    bucket_b.sort(key=lambda x: x[0]) # file_path ASC
    bucket_b.sort(key=lambda x: x[2], reverse=True) # created_at DESC
    
    # 3. Fill Budget
    # Bucket A (Priority)
    for path, text in bucket_a:
        if remaining_tokens <= 0:
            break
        entry = f"File: {path}\n```\n{text}\n```"
        tokens = tokenizer.count_tokens(entry)
        
        if tokens > remaining_tokens:
            # Truncate
            overhead = tokenizer.count_tokens(f"File: {path}\n```\n\n{TRUNCATION_MARKER}\n```")
            available = remaining_tokens - overhead
            if available > 0:
                truncated_text = tokenizer.truncate(text, available)
                entry = f"File: {path}\n```\n{truncated_text}\n{TRUNCATION_MARKER}\n```"
                components.append(entry)
            remaining_tokens = 0
            break
        else:
            components.append(entry)
            remaining_tokens -= tokens
            
    # Bucket B (Recency/Remainder)
    for path, text, _ in bucket_b:
        if remaining_tokens <= 0:
            break
        entry = f"File: {path}\n```\n{text}\n```"
        tokens = tokenizer.count_tokens(entry)
        
        if tokens > remaining_tokens:
            # Truncate
            overhead = tokenizer.count_tokens(f"File: {path}\n```\n\n{TRUNCATION_MARKER}\n```")
            available = remaining_tokens - overhead
            if available > 0:
                truncated_text = tokenizer.truncate(text, available)
                entry = f"File: {path}\n```\n{truncated_text}\n{TRUNCATION_MARKER}\n```"
                components.append(entry)
            remaining_tokens = 0
            break
        else:
            components.append(entry)
            remaining_tokens -= tokens
            
    return components
