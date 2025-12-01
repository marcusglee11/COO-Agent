# COO Agent Architecture Gap Analysis - November 29, 2025

## Executive Summary

**Drift Score: 6.5/10** - The implementation significantly deviates from the v0.6-FINAL architecture specification, with both missing features and unplanned additions.

## Features Listed in Architecture but MISSING from Code

### 1. **Critical Missing Features**

**STREAM Message Implementation**
- **Architecture Spec**: STREAM messages for live UX progress updates (§4.2, §4.7)
- **Current Status**: STREAM message kind exists in models but no implementation
- **Impact**: No real-time progress streaming to CEO

**Approval Flow (CEO Gate)**
- **Architecture Spec**: APPROVAL messages with CEO gate functionality (§4.2, §4.7)
- **Current Status**: APPROVAL message kind exists but no approval workflow
- **Impact**: No CEO approval/rejection mechanism

**Advanced CLI Commands**
- **Architecture Spec**: `coo chat`, `coo metrics --daily`, `coo dlq list/show` (§4.7)
- **Current Status**: Only basic CLI commands implemented (init-db, status, mission, logs, dlq-replay, resume)
- **Impact**: Limited operational capabilities

**Agent Registry Table**
- **Architecture Spec**: `agents` table with capabilities, performance metrics (§4.1)
- **Current Status**: Table schema exists but no population or usage
- **Impact**: No agent performance tracking or capability management

**Budget Increase Requests**
- **Architecture Spec**: `budget_increase_requests` field with max 3 requests per mission (§4.5)
- **Current Status**: Field exists in schema but no implementation
- **Impact**: No budget escalation mechanism

**Message Timeout Handling**
- **Architecture Spec**: `timeout_at` field with timeout enforcement (§4.1)
- **Current Status**: Field exists but no timeout logic implemented
- **Impact**: Messages can hang indefinitely

### 2. **Schema Deviations**

**Artifacts Table Mismatch**
- **Architecture Spec**: `type`, `mime_type`, `size_bytes`, `content`, `storage_type`, `path`, `checksum` fields
- **Current Implementation**: `filename`, `content_b64`, `created_by` fields only
- **Impact**: Limited artifact metadata and storage capabilities

**Missing Database Fields**
- **Architecture Spec**: `previous_status`, `loop_count_limit`, `message_count` in missions table
- **Current Status**: Some fields missing, schema simplified
- **Impact**: Reduced mission tracking capabilities

### 3. **Configuration Gaps**

**Model Configuration Mismatch**
- **Architecture Spec**: DeepSeek + GLM models with specific pricing
- **Current Implementation**: OpenRouter with different pricing structure
- **Impact**: Different cost calculations than specified

**Missing Configuration Options**
- **Architecture Spec**: `max_concurrent_missions`, `heartbeat_timeout_seconds`, `safety_margin`
- **Current Status**: Some config options not implemented
- **Impact**: Reduced configurability

## Files in Code NOT Accounted for in Architecture

### 1. **Project Builder Components (Major Addition)**

**Entire project_builder/ directory** - Not mentioned in architecture
- Enhanced orchestrator with FSM, routing, reclaim, missions
- Advanced sandbox with manifest, security, workspace, runner
- Context management with tokenizer, truncation, injection
- Database utilities with migrations, snapshots, timeline
- Agent planner with validation and governance

**Impact**: This represents a completely separate, more advanced implementation parallel to the core COO system

### 2. **COO Runtime Components (Major Addition)**

**Entire coo_runtime/ directory** - Not in architecture
- Runtime execution components (amendment_engine, freeze, replay)
- AMU0 utilities and verification systems
- Cryptographic utilities and signature validation
- Manifest management and governance enforcement
- External trace recording and replay

**Impact**: Enterprise-grade runtime system not specified in original architecture

### 3. **Enhanced Test Suite**

**Advanced test files** - Beyond basic unit tests specified
- Integration tests with full system flow
- Governance enforcement tests
- Planner validation tests
- Budget transaction concurrency tests
- FSM state transition tests

### 4. **Security and Governance**

**Enhanced security features** - Not in original spec
- AMU0 verification and canonical hash calculation
- Governance enforcement with digest validation
- Platform verification (Windows rejection in PROD)
- Manifest path validation with regex contracts
- Cryptographic signature validation

### 5. **Additional Configuration**

**Enhanced config system** - Beyond simple YAML files
- Governance configuration with allowed digests
- Settings management with environment variables
- Runtime configuration for AMU0 tracking

## Specific Implementation Deviations

### 1. **Database Schema Evolution**

**Project Builder Schema** - Completely different from architecture spec
- Added `mission_tasks` table with complex state management
- Enhanced `artifacts` table with versioning and deletion tracking
- Added repair budget and attempt tracking
- Timeline events linked to specific tasks

### 2. **Budget System Enhancement**

**Advanced Budget Transactions** - Beyond simple budget guards
- Repair budget tracking separate from main mission budget
- Concurrent access protection with IMMEDIATE transactions
- Task-level budget allocation and tracking

### 3. **Sandbox Security Hardening**

**Enhanced Security** - Beyond basic Docker isolation
- Entrypoint hardening against TOCTOU attacks
- Symlink scanning and purging
- Read-only workspace verification
- Governance-based digest validation

### 4. **Agent System Architecture**

**Dual Implementation** - Both simple and advanced versions
- Basic agents in `coo/agents/` following architecture
- Advanced agents in `project_builder/agents/` with validation
- Planner agent with required artifact validation
- Context injection and truncation systems

## Root Causes of Architecture Drift

### 1. **Specification vs. Reality Gap**
- Architecture was "pre-implementation" theoretical design
- Real-world requirements drove additional complexity
- Security and governance requirements evolved

### 2. **Parallel Development Tracks**
- Core COO system (following architecture)
- Project Builder system (enterprise enhancements)
- COO Runtime system (production hardening)

### 3. **Enterprise Requirements**
- AMU0 verification for deterministic replay
- Cryptographic signatures for governance
- Advanced budget management for cost control
- Comprehensive security scanning

### 4. **Testing and Quality Assurance**
- Extensive test suite beyond basic integration
- Concurrency testing for budget transactions
- Governance validation testing
- End-to-end system flow validation

## Recommendations

### 1. **Architecture Documentation Update**
- Create separate architecture documents for each subsystem
- Document the evolution from v0.6-FINAL to current state
- Specify the interaction between core, project_builder, and coo_runtime

### 2. **Integration Strategy**
- Define clear boundaries between subsystems
- Document migration paths between simple and advanced implementations
- Specify when to use which implementation level

### 3. **Feature Completion**
- Implement missing STREAM and APPROVAL message flows
- Add missing CLI commands (chat, metrics, advanced dlq)
- Complete agent registry functionality
- Implement message timeout handling

### 4. **Configuration Harmonization**
- Align configuration schemas across all subsystems
- Document configuration precedence and inheritance
- Provide migration tools for configuration updates

## Conclusion

The current implementation represents a significant evolution beyond the original v0.6-FINAL architecture, incorporating enterprise-grade features for security, governance, and deterministic replay. While this drift has created a more robust system, it has also introduced complexity that needs to be properly documented and managed. The **6.5/10 drift score** reflects both the successful implementation of core concepts and the substantial additions that go beyond the original specification.