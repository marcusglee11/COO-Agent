COO: The Deterministic Agent Runtime

Version: 0.6-FINAL (Pre-Implementation) Status: Active Development

COO is a self-directed multi-agent system designed for deterministic execution, hard budget enforcement, and total sandbox isolation. Unlike event-driven or purely autonomous frameworks, COO uses a polling-based architecture backed by SQLite as the single source of truth.

You play the CEO. You provide natural-language missions. COOAgent plans. EngineerAgent codes. QAAgent reviews.

🏗 Architecture

The system runs as a single Python process (coo orchestrator) communicating with agents via a local SQLite message bus. Code execution is delegated to ephemeral, network-isolated Docker containers.
Code snippet

graph TD
    CEO[CEO / CLI Chat] <--> DB[(SQLite Message Bus)]
    Orchestrator[Orchestrator Daemon] <--> DB
    Orchestrator -- "Sync HTTP / ThreadPool" --> LLM[LLM APIs]
    Orchestrator -- "SANDBOX_EXECUTE" --> Docker[Docker Sandbox]
    Docker -- "Artifacts" --> DB

Key Design Decisions

    SQLite as Message Bus: No RabbitMQ or Redis. coo.db (WAL mode) handles all state, queues, and locking.

    Hard Budget Enforcement: Deterministic pre-call checks and post-call rollbacks. If an agent overspends, the transaction is reverted.

    Network-None Sandbox: Code runs in coo-sandbox:latest with --network none. No runtime pip install allowed.

    Streaming UX: The CLI polls the DB for STREAM messages to provide a live console experience without WebSockets.

🚀 Getting Started

Prerequisites

    Python 3.11+

    Docker Engine (User must have permission to run containers without sudo)

    API Keys for DeepSeek (primary) and/or GLM-4 (fallback)

1. Installation

Clone the repository and set up the environment:
Bash

git clone https://github.com/yourusername/coo-agent.git
cd coo-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

2. Build the Sandbox Image

Critical: The system does not allow agents to install packages at runtime. You must build the "fat" image containing all allowed dependencies (numpy, pandas, pytest, etc.) beforehand.
Bash

docker build -t coo-sandbox:latest -f docker/Dockerfile.sandbox .

3. Configuration

Copy the configuration templates:
Bash

cp config/models.yaml.example config/models.yaml
cp config/orchestrator.yaml.example config/orchestrator.yaml

Edit config/models.yaml to add your API keys or reference environment variables (e.g., DEEPSEEK_API_KEY).

4. Initialize Database

Create the SQLite database and apply the schema:
Bash

coo init-db

Database location: ~/.local/share/coo/coo.db

💻 Usage

The system requires two terminal windows: one for the background orchestrator and one for your interaction.

Terminal 1: The Orchestrator

Starts the main loop, handles message routing, and manages the thread pool for LLM calls.
Bash

coo orchestrator

Terminal 2: The Interface

Use the CLI to send missions and view status.

Start a new mission:
Bash

coo chat
# > CEO: "Create a Python script to calculate Fibonacci sequence and unit test it."

Monitor progress:
Bash

coo status                  # List all active missions and budget spent
coo mission <id> --follow   # Stream logs and agent conversation
coo logs --mission <id>     # View structured logs

Budget & Control:
Bash

coo metrics --daily         # View daily spend vs limit
coo dlq list                # Inspect Dead Letter Queue

🛡 Security & Limits

The Sandbox

    Network: none (No internet access inside container).

    User: 1000:1000 (Non-root).

    Privileges: --security-opt=no-new-privileges.

    Filesystem: Ephemeral bind-mount workspace; destroyed after execution.

Budget Governance

    Per-Agent Caps: Hard token limits per call (e.g., Engineer: 8k tokens).

    Global Limits: Daily and Monthly hard caps (defined in orchestrator.yaml).

    Backpressure: Missions with >50 pending messages are auto-paused.

📂 Project Structure

coo-agent/
├── coo/
│   ├── orchestrator.py    # Main event loop & thread pool
│   ├── message_store.py   # SQLite async wrapper
│   ├── budget.py          # Transactional budget guard
│   ├── sandbox.py         # Docker wrapper
│   └── agents/            # Base agent & implementations
├── config/                # YAML configuration
├── docker/                # Sandbox Dockerfile
├── prompts/               # System prompts (Markdown)
└── tests/                 # pytest suite

🤝 Contributing

    Strict Types: All code must be fully typed (mypy strict mode).

    No Async HTTP: We use ThreadPoolExecutor for LLM calls to keep the core loop simple.

    Migrations: Database schema changes must be reflected in message_store.py (v1.0 has no migration tool, just schema recreation).

📜 License

[License Name] - See LICENSE file for details.
