Tasks
 Phase 0: Core Infrastructure
 SQLite schema + migrations
 MessageStore async methods
 Models (Pydantic schemas)
 Config file skeleton
 CLI skeleton
 First test: 
test_message_store.py
 Phase 1: Orchestrator + Dummy Agents
 
orchestrator.py
 with asyncio main loop
 
Agent
 base class + 
process_stream
 generator
 
DummyCOO
, 
DummyEngineer
, 
DummyQA
 
BudgetTracker
 skeleton
 End-to-end test: mission flow with no LLMs
 Stale message reclaim implementation
 Pre-Phase 2 Fixes
 Fix logging import in 
message_store.py
 Replace deprecated datetime.utcnow()
 Update 
sandbox.yaml
 for cross-platform temp dir
 Update 
models.yaml
 to OpenRouter provider
 Phase 2: Sandbox Integration
 Build coo-sandbox:latest Dockerfile (non-root, no-pip)
 
SandboxRunner
 implementation
 
run_artifact
 with idempotency & materialization
 
recover_crashed_runs
 Security flags & cleanup
 Orchestrator integration
 Handle SANDBOX_EXECUTE emissions
 Inject RESULT message
 Startup crash recovery call
 Update 
DummyEngineer
 to emit sandbox_execute
 Test: 
test_sandbox.py
 (Unit + Docker)
 Test: 
test_orchestrator_sandbox.py
 (E2E)
 Phase 3: Real LLM Agents + Budget
 ModelClient for DeepSeek + GLM
 Central token caps enforcement
 COO/Engineer/QA prompts via PromptManager
 Prompt file structure
 Cost calculation from API responses
 Hard budget enforcement + rollback on exceed
 Global daily/monthly budget tracking
 Test: budget exceed → rollback verified
 Phase 4: Observability + Hardening
 structlog integration with secret scrubbing
 Timeline events for all major actions
 CLI commands: coo mission, coo logs, coo dlq replay
 Approval flow (CEO gate) + CONTROL messages
 Backpressure hard pause implementation
 Sandbox crash recovery
 scrub_secrets unit test
 Critical shutdown logging
 Integration tests
 README + operations guide