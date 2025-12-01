# COO Agent Current State Snapshot - November 29, 2025

## Project Tree Structure

```
coo-agent/
├── coo/                          # Core COO Agent implementation
│   ├── __init__.py              # Package initialization
│   ├── main.py                  # Entry point and orchestrator startup
│   ├── orchestrator.py          # Main orchestration loop with async processing
│   ├── message_store.py         # SQLite message bus with WAL mode
│   ├── sandbox.py               # Docker-based isolated code execution
│   ├── budget.py                # Hard budget enforcement with transactional guards
│   ├── llm.py                   # LLM API client with cost tracking
│   ├── models.py                # Pydantic data models for messages and missions
│   ├── prompts.py               # Prompt management for agent system prompts
│   ├── logging_utils.py         # Secret scrubbing for structured logging
│   ├── cli.py                   # CLI commands for system interaction
│   └── agents/                  # Agent implementations
│       ├── __init__.py          # Agents package initialization
│       ├── base.py              # Abstract base class for all agents
│       ├── real_agents.py       # Real LLM-powered COO, Engineer, QA agents
│       └── dummy_agents.py      # Test agents for development
├── config/                      # Configuration files
│   ├── models.yaml              # LLM model configurations and pricing
│   ├── orchestrator.yaml        # System settings, budgets, backpressure
│   └── sandbox.yaml             # Sandbox execution settings
├── docker/                      # Docker configuration
│   ├── Dockerfile.sandbox       # Network-isolated sandbox container
│   └── entrypoint.sh            # Container entrypoint script
├── prompts/                     # Agent system prompts
│   ├── coo/system.md            # COO agent system prompt
│   ├── engineer/system.md       # Engineer agent system prompt
│   └── qa/system.md             # QA agent system prompt
├── project_builder/             # Enhanced COO runtime components
│   ├── __init__.py              # Package initialization
│   ├── agents/planner.py        # Mission planning and validation
│   ├── config/                  # Advanced configuration
│   │   ├── __init__.py
│   │   ├── governance.py        # Runtime governance enforcement
│   │   └── settings.py          # Settings management
│   ├── context/                 # Context management
│   │   ├── injection.py         # Context injection utilities
│   │   ├── tokenizer.py         # Token counting and management
│   │   └── truncation.py        # Context truncation strategies
│   ├── database/                # Database utilities
│   │   ├── __init__.py
│   │   ├── migrations.py        # Schema migration management
│   │   ├── schema.sql           # Database schema definition
│   │   ├── snapshot.py          # Database snapshot utilities
│   │   └── timeline.py          # Timeline event logging
│   ├── orchestrator/            # Enhanced orchestration
│   │   ├── __init__.py
│   │   ├── budget_txn.py        # Budget transaction management
│   │   ├── fsm.py               # Finite state machine for missions
│   │   ├── missions.py          # Mission lifecycle management
│   │   ├── reclaim.py           # Message reclaim and recovery
│   │   └── routing.py           # Message routing logic
│   └── sandbox/                 # Enhanced sandbox
│       ├── __init__.py
│       ├── manifest.py          # Sandbox manifest management
│       ├── runner.py            # Sandbox execution runner
│       ├── security.py          # Security scanning and validation
│       └── workspace.py         # Workspace management
├── tests/                       # Test suite
│   ├── test_budget_txn.py       # Budget transaction tests
│   ├── test_fsm.py              # Finite state machine tests
│   ├── test_reclaim.py          # Message reclaim tests
│   ├── test_routing.py          # Message routing tests
│   ├── test_backpressure.py     # Backpressure management tests
│   ├── test_required_artifact_ids.py # Artifact ID validation tests
│   ├── test_tokenizer_replay.py # Tokenizer replay tests
│   ├── test_repair_context.py   # Repair context tests
│   ├── test_manifest_parsing.py # Manifest parsing tests
│   └── test_sandbox_security.py # Sandbox security tests
├── coo_runtime/                 # Runtime components and manifests
│   ├── __init__.py
│   ├── manifests/               # Runtime manifests
│   │   ├── ceo_private_key.pem # CEO private key
│   │   ├── ceo_public_key.pem  # CEO public key
│   │   ├── environment_manifest.json # Environment configuration
│   │   ├── freeze_manifest.json # Freeze state manifest
│   │   ├── hardware_manifest.json # Hardware requirements
│   │   ├── sandbox_digest.txt   # Sandbox image digest
│   │   ├── test_manifest.json   # Test configuration
│   │   └── tools_manifest.json  # Available tools manifest
│   ├── reference/               # Reference implementations
│   │   └── phase3_reference_mission.json # Reference mission example
│   ├── runtime/                 # Runtime execution components
│   │   ├── amendment_engine.py  # Amendment processing engine
│   │   ├── amu_capture.py       # AMU capture utilities
│   │   ├── external_trace_recorder.py # External trace recording
│   │   ├── external_trace_replayer.py # External trace replay
│   │   ├── freeze.py            # System freeze functionality
│   │   ├── replay_harness.py    # Replay execution harness
│   │   └── replay.py            # Main replay functionality
│   ├── scripts/                 # Runtime scripts
│   │   ├── apply_amendments.py  # Apply system amendments
│   │   ├── run_lint.py          # Code linting script
│   │   ├── run_migration.py     # Database migration script
│   │   ├── run_replay.py        # Replay execution script
│   │   ├── run_rollback.py      # System rollback script
│   │   ├── run_scanner.py       # Security scanning script
│   │   └── run_tests.py         # Test execution script
│   ├── tests/                   # Runtime tests
│   │   ├── e2e_proof_of_life.py # End-to-end system test
│   │   ├── run_tests.py         # Test runner
│   │   ├── test_determinism.py  # Determinism validation
│   │   ├── test_governance_integrity.py # Governance integrity test
│   │   ├── test_migration.py    # Migration testing
│   │   ├── test_r6_integration_determinism.py # R6 integration test
│   │   ├── test_replay.py       # Replay functionality test
│   │   └── test_sandbox_security.py # Sandbox security test
│   └── util/                    # Runtime utilities
│       ├── __init__.py
│       ├── amu0_utils.py        # AMU0 utility functions
│       ├── context.py           # Context management utilities
│       ├── crypto.py            # Cryptographic utilities
│       ├── output_bundle.py     # Output bundling utilities
│       ├── questions.py         # Question handling utilities
│       └── subprocess.py        # Subprocess management
├── docs/                        # Documentation
│   ├── Antigravity_Council_Review_Packet_Spec_v1.0.md # Council review specification
│   ├── Antigravity_Implementation_Packet_v0_9_7.md # Implementation packet
│   ├── CHANGELOG.MD             # System changelog
│   ├── CODE_REVIEW_STATUS.md    # Code review status tracking
│   ├── governance_digest.md     # Governance digest documentation
│   ├── GPTCOO_v1_1_ProjectBuilder_v0_9_FinalCleanSpec.md # Final specification
│   ├── IMPLEMENTATION_PLAN.md   # Implementation planning document
│   ├── Review_Packet_Reminder.md # Review packet reminders
│   ├── TASKS.md                 # Task tracking documentation
│   └── WALKTHROUGH.md           # System walkthrough guide
├── specs/                       # Technical specifications
│   ├── Alignment_Layer_v1.4.md  # Alignment layer specification
│   ├── Antigravity_Implementation_Packet_v0_9_7.md # Implementation packet
│   ├── COO_RUNTIME_SPECIFICATION_v1.0.md # Runtime specification
│   └── GPTCOO_v1_1_ProjectBuilder_v0_9_PatchedSpec.md # Patched specification
├── legacy_archive/              # Legacy and archived files
├── e2e_test_env/                # End-to-end testing environment
├── council_review/              # Council review materials
├── pyproject.toml               # Python project configuration
├── readme.md                    # Main project documentation
└── ARCHITECTURE.md              # System architecture specification
```

## File Purpose Summaries

### Core COO Agent Files

**`coo/main.py`** - Entry point that loads configuration, initializes the database, and starts the main orchestrator loop with structured logging and error handling.

**`coo/orchestrator.py`** - Main orchestration engine that processes messages from the SQLite queue, manages agent coordination, handles backpressure, and orchestrates the COO→Engineer→QA workflow.

**`coo/message_store.py`** - SQLite-based message bus implementation with WAL mode, providing atomic message claiming, delivery, stale message reclaim, and comprehensive database operations for missions and artifacts.

**`coo/sandbox.py`** - Docker-based isolated code execution system with network isolation, resource limits, idempotency checks, crash recovery, and secure workspace management.

**`coo/budget.py`** - Hard budget enforcement system with transactional guards, pre-call cost estimation, post-call enforcement, and automatic rollback on budget exceedance.

**`coo/llm.py`** - LLM API client with OpenRouter integration, cost calculation, token limit enforcement, proactive truncation, and ThreadPoolExecutor for sync HTTP calls.

**`coo/models.py`** - Pydantic data models defining MessageKind, MessageStatus, MissionStatus enums and Message/Mission base models with validation.

**`coo/prompts.py`** - Prompt management system that loads agent-specific system prompts and builds conversation context with mission information and message history.

**`coo/logging_utils.py`** - Secret scrubbing processor for structlog that redacts API keys, tokens, and passwords using regex patterns to prevent sensitive data leakage.

**`coo/cli.py`** - Command-line interface providing init-db, status, mission inspection, logs, dead-letter replay, and mission resume functionality.

### Agent Implementation Files

**`coo/agents/base.py`** - Abstract base class for all agents with async generator interface, LLM calling with budget tracking, and emission handling.

**`coo/agents/real_agents.py`** - Real LLM-powered implementations of COO (planning), Engineer (code generation), and QA (code review) agents with JSON parsing and sandbox integration.

**`coo/agents/dummy_agents.py`** - Test agents for development that emit predefined responses without requiring LLM calls.

### Configuration Files

**`config/models.yaml`** - LLM model configurations including OpenRouter settings, pricing per 1K tokens, and agent-specific model assignments with temperature settings.

**`config/orchestrator.yaml`** - System orchestration settings including tick intervals, budget limits, backpressure thresholds, and safety margins for mission execution.

**`config/sandbox.yaml`** - Sandbox execution configuration specifying temporary workspace directory for isolated code execution.

### Docker and Security

**`docker/Dockerfile.sandbox`** - Network-isolated container definition with non-root user, pre-installed Python packages, and disabled pip to prevent runtime package installation.

**`docker/entrypoint.sh`** - Container entrypoint script that sets up the sandbox environment and executes provided commands securely.

### Agent Prompts

**`prompts/coo/system.md`** - System prompt defining the COO agent's role as mission coordinator responsible for decomposing CEO tasks into actionable Engineer instructions.

**`prompts/engineer/system.md`** - System prompt defining the Engineer agent's role as senior developer responsible for writing complete, runnable Python code based on COO specifications.

**`prompts/qa/system.md`** - System prompt defining the QA agent's role as code reviewer responsible for approving or rejecting code execution results based on exit codes and output validation.

### Project Builder Components

**`project_builder/orchestrator/fsm.py`** - Finite state machine implementation for mission task lifecycle management with transactional state transitions and governance enforcement.

**`project_builder/sandbox/security.py`** - Security scanning utility that recursively checks for symbolic links in sandbox workspaces to prevent directory traversal attacks.

**`project_builder/database/migrations.py`** - Database schema migration management system for evolving the COO runtime database structure.

**`project_builder/context/tokenizer.py`** - Token counting and management system for controlling context window usage and preventing token overflow.

### Test Files

**`tests/test_budget_txn.py`** - Comprehensive budget transaction tests including success cases, limit enforcement, repair budget testing, and concurrent access validation.

## Missing Features Expected in a COO Agent

Based on my analysis of the codebase, here are 3 missing features that would be expected in a production COO agent system:

### 1. **Multi-Mission Resource Scheduling and Priority Management**
The current system handles multiple missions but lacks sophisticated resource scheduling. A production COO agent should implement:
- Priority-based mission scheduling with configurable scheduling algorithms (FIFO, priority queue, weighted fair sharing)
- Resource allocation management (CPU, memory, LLM token quotas per mission)
- Mission preemption and suspension capabilities
- Load balancing across multiple orchestrator instances
- Mission dependency management and DAG execution

### 2. **Advanced Context Management and Memory Systems**
The current context management is basic (last 5 messages). A production system needs:
- Conversation summarization with configurable compression strategies
- Vector database integration for semantic memory retrieval
- Long-term memory persistence across missions
- Context-aware artifact and code reference management
- Hierarchical context windows with importance weighting
- Multi-modal context support (code, documentation, images)

### 3. **Comprehensive Monitoring, Alerting, and Analytics**
The current observability is limited to structured logging and basic CLI tools. A production COO agent should include:
- Real-time metrics dashboard with Prometheus/Grafana integration
- Automated alerting for budget thresholds, mission failures, and security violations
- Performance analytics and optimization recommendations
- Cost analysis and spending prediction models
- Agent performance profiling and bottleneck identification
- SLA monitoring and compliance reporting
- Integration with external monitoring systems (PagerDuty, Slack, email)