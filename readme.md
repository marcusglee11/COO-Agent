# COO Agent

**COO (Chief Operating Officer) Agent** is a multi-agent autonomous system built with SQLite-based message orchestration, secure sandboxed code execution, and fine-grained budget control.

## Architecture

The system implements a **COO → Engineer → QA** workflow:
- **COO**: Plans tasks and coordinates work
- **Engineer**: Writes Python code based on COO's specifications
- **QA**: Reviews and either approves or rejects the Engineer's work

All agents communicate via a SQLite message bus with idempotent message processing, automatic retries, and dead-letter queuing.

## Features

- **Multi-Agent Orchestration**: Async message-based coordination between specialized agents
- **Secure Sandbox**: Docker-based isolated code execution with no network access
- **Budget Control**: Per-mission and global budget tracking with hard limits
- **Observability**: Structured logging with secret scrubbing, timeline events for debugging
- **CLI Tools**: Inspect missions, view logs, replay failed messages, resume paused missions
- **Crash Recovery**: Automatic recovery of sandbox runs and stale messages
- **Backpressure**: Intelligent flow control to prevent system overload

## Quick Start

### Prerequisites
- Python 3.12+
- Docker (for sandbox execution)
- OpenRouter API key

### Installation

```bash
# Clone the repository
cd coo-agent

# Install dependencies
pip install -r requirements.txt

# Set up environment
export OPENROUTER_API_KEY="your-api-key-here"

# Build sandbox Docker image
docker build -f docker/Dockerfile.sandbox -t coo-sandbox:latest .

# Initialize database
python -m coo.cli init-db
```

### Running the Agent

```bash
# Start the orchestrator
python -m coo.main
```

### Creating a Mission

```python
import asyncio
from pathlib import Path
from coo.message_store import MessageStore
from coo.models import MessageKind

async def create_mission():
    db_path = Path.home() / ".local" / "share" / "coo" / "coo.db"
    store = MessageStore(db_path)
    
    # Create mission
    mission = {
        "id": "mission-001",
        "description": "Create a hello world script",
        "max_cost_usd": 0.10,
        "max_loops": 10
    }
    await store.create_mission(mission)
    
    # Send initial task
    await store.deliver_message({
        "id": "msg-001",
        "mission_id": "mission-001",
        "from_agent": "USER",
        "to_agent": "COO",
        "kind": MessageKind.TASK.value,
        "body_json": {"content": "Write a Python script that prints 'Hello, World!'"}
    })

asyncio.run(create_mission())
```

## CLI Commands

```bash
# View mission status
python -m coo.cli mission <mission-id>

# View timeline events for a mission
python -m coo.cli logs <mission-id>

# Replay a dead-letter message
python -m coo.cli dlq-replay <dead-letter-id>

# Resume a paused mission
python -m coo.cli resume <mission-id>

# Initialize/reset database
python -m coo.cli init-db
```

## Configuration

Configuration files are located in `config/`:

### `config/models.yaml`
```yaml
models:
  default:
    provider: "openrouter"
    router_model: "deepseek/deepseek-chat"
    max_tokens_per_call: 8000
    pricing:
      input_per_1k: 0.00014
      output_per_1k: 0.00028

agents:
  COO:
    model: "default"
    temperature: 0.6
  Engineer:
    model: "default"
    temperature: 0.4
  QA:
    model: "default"
    temperature: 0.3
```

### `config/orchestrator.yaml`
```yaml
orchestrator:
  tick_interval_seconds: 1.0

budgets:
  global_daily_usd: 10.0
  global_monthly_usd: 100.0

backpressure:
  max_pending_messages: 50
  resume_threshold: 30
```

### `config/sandbox.yaml`
```yaml
temp_dir: "coo-workspace"
```

## Database Schema

The system uses SQLite with the following tables:
- **missions**: Mission metadata, budget, status
- **messages**: Message queue with locking and retries
- **artifacts**: Code files and outputs (base64 encoded)
- **sandbox_runs**: Execution history with idempotency
- **dead_letters**: Failed messages for manual replay
- **timeline_events**: Structured event log for debugging
- **budgets**: Global daily/monthly spend tracking

## Security

- **Secret Scrubbing**: Automatic redaction of API keys, passwords, and tokens from logs
- **Sandbox Isolation**: No network, limited CPU/memory, non-root user
- **Path Validation**: Filename sanitization to prevent directory traversal
- **Token Limits**: Enforced per-call token caps to prevent abuse
- **Budget Hard Limits**: Transactions rolled back if budget exceeded

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=coo --cov-report=html
```

### Project Structure

```
coo-agent/
├── coo/
│   ├── main.py              # Entry point
│   ├── orchestrator.py      # Main orchestration loop
│   ├── message_store.py     # SQLite message bus
│   ├── sandbox.py           # Docker sandbox runner
│   ├── budget.py            # Budget tracking and guards
│   ├── llm.py               # LLM API client
│   ├── prompts.py           # Prompt loading
│   ├── logging_utils.py     # Secret scrubbing
│   ├── cli.py               # CLI commands
│   ├── models.py            # Pydantic models
│   └── agents/
│       ├── base.py          # Agent base class
│       ├── real_agents.py   # COO, Engineer, QA
│       └── dummy_agents.py  # Test agents
├── config/                  # YAML configuration
├── prompts/                 # Agent system prompts
├── tests/                   # Unit and integration tests
└── docker/                  # Sandbox Dockerfile
```

## Monitoring and Debugging

### Timeline Events
All major system events are logged to the `timeline_events` table:
```bash
python -m coo.cli logs <mission-id>
```

### Structured Logs
The system outputs JSON logs with automatic secret scrubbing:
```python
import structlog
log = structlog.get_logger()
log.info("event_name", key="value", mission_id="123")
```

### Mission Status
Check mission progress:
```bash
python -m coo.cli mission <mission-id>
```

## Operations Guide

### Pausing a Mission
Missions can be paused automatically (budget exceeded, errors) or manually:
```python
await store.update_mission_status(mission_id, "paused_manual")
```

### Resuming a Mission
Send a CONTROL message:
```bash
python -m coo.cli resume <mission-id>
```

### Dead Letter Queue
Failed messages go to the DLQ after max retries. Replay them:
```bash
python -m coo.cli dlq-replay <dead-letter-id>
```

### Budget Management
- Check current spend in database: `SELECT * FROM budgets`
- Reset monthly budget: Delete row for current month
- Adjust limits: Edit `config/orchestrator.yaml`

### Crash Recovery
The orchestrator automatically recovers:
- Stale messages (reclaimed after timeout)
- Crashed sandbox runs (marked failed after 10 minutes)

On restart, call `await self.sandbox.recover_crashed_runs()`.

## Troubleshooting

### LLM API Errors
- Check `OPENROUTER_API_KEY` is set
- Verify API key is valid
- Check rate limits in logs

### Sandbox Failures
- Ensure Docker is running: `docker ps`
- Rebuild sandbox image: `docker build -f docker/Dockerfile.sandbox -t coo-sandbox:latest .`
- Check logs for timeout/OOM errors

### Budget Exceeded
- Increase `max_cost_usd` for mission
- Increase global budget in `config/orchestrator.yaml`
- Check pricing in `config/models.yaml` matches actual costs

### Mission Stuck
- Check message status: `SELECT * FROM messages WHERE mission_id = ?`
- Look for deadlocks in logs
- Resume paused mission: `python -m coo.cli resume <mission-id>`

## License

[Your License Here]

## Contributing

[Your Contributing Guidelines Here]