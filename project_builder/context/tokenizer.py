def resolve_tokenizer_id(model_config: dict) -> str:
    """
    Pure function. Returns the stable identifier string for the tokenizer.
    Does NOT access DB.
    
    Logic:
    - If config['provider'] == 'openai' -> return 'tiktoken/cl100k_base'
    - Else -> return config['tokenizer'] or raise ValueError
    """
    provider = model_config.get('provider', '').lower()
    if provider == 'openai':
        return 'tiktoken/cl100k_base'
    
    tokenizer = model_config.get('tokenizer')
    if not tokenizer:
        raise ValueError("Non-OpenAI models must specify a 'tokenizer' field in config.")
    
    return tokenizer
