# COO-Agent Mission Orchestrator — Architecture v0.7-ALIGNED
**"A Deterministic Multi-Agent Orchestrator Running on the COO Runtime"**

---

## 0. Authority, Scope, and Status

### 0.1 Authority Chain

This document is **subordinate** to:

- LifeOS Core Specification v1.1 (Constitutional authority)
- Alignment Layer v1.4
- COO Runtime Specification v1.0
- Implementation Packet v1.0
- Antigravity Instruction Packet — Phase 4 COO Runtime v1.0

If this document conflicts with any of the above, the higher-level specification wins.

### 0.2 Scope

This document specifies the architecture of the **COO-Agent Mission Orchestrator** (“coo-agent”), implemented primarily under:

- `coo/`
- `project_builder/`

It describes:

- How the orchestrator coordinates agents (COO, Engineer, QA).
- How it uses a deterministic message bus and sandbox.
- How it integrates with the **COO Runtime** (`coo_runtime/`) as a workload executed under LifeOS governance.

This document **does not** redefine:

- The COO Runtime finite state machine (FSM).
- AMU₀ semantics, freeze protocol, or migration sequence.
- Council behaviour, CSO behaviour, or CEO interaction rules.

All of those are defined in the higher-level specs.

### 0.3 Status

- **Version:** 0.7-ALIGNED  
- **Date:** 2025-11-29  
- **Status:** Architecture aligned with current implementation; some sections define near-term target behaviour.

---

## 1. System Placement in LifeOS

### 1.1 Layer Placement

Within the LifeOS architecture:

- **Intake / Routing / Council / CSO**: Interpret CEO intent, perform governance, produce governed missions.
- **COO Runtime**: Deterministic execution engine (FSM, freeze, AMU₀, migration, replay, rollback).
- **COO-Agent (this document)**: A **mission orchestrator** that runs *inside* the COO Runtime as a governed workload, or standalone in dev mode.

The COO-Agent:

- Receives a mission definition (from a Canonical Mission Descriptor or equivalent).
- Uses its internal agent team (COO, Engineer, QA) to plan, write, test, and execute code within a sandbox.
- Emits artefacts and logs that are captured by the COO Runtime’s flight recorder and replay mechanisms.

### 1.2 Modes of Operation

1. **Governed Runtime Mode (Primary)**  
   - COO-Agent is launched by the COO Runtime as part of a TMD-approved mission.  
   - All external effects (LLM calls, HTTP, sandbox I/O) are subject to **Freeze Protocol** and **Deep Replay** as specified in the COO Runtime and Alignment Layer.  
   - CEO / Council / CSO do *not* interact directly with the COO-Agent. They see only the mission-level inputs and outputs.

2. **Dev / Standalone Mode (Secondary)**  
   - COO-Agent can be run directly from the CLI for development and experimentation.  
   - CEO-style “chat” interfaces and ad-hoc missions are allowed here as a *convenience only*.  
   - This mode is explicitly outside constitutional guarantees and must not be mistaken for governed LifeOS operation.

---

## 2. High-Level Architecture

### 2.1 Repository Structure (Relevant Domains)

The `coo-agent` repository contains three major domains:

- **1) COO-Agent Core (`coo/`)**  
  - Orchestrator loop, message bus, sandbox integration, budgets, LLM client, CLI, basic agents.

- **2) Project Builder Enhancements (`project_builder/`)**  
  - Advanced FSM for mission tasks, planner, routing, reclaim, timeline logging, security-hardening, context management.

- **3) COO Runtime (`coo_runtime/`)**  
  - Canonical runtime implementation (AMU₀ capture, freeze, replay, rollback, manifests, tests, scripts) per COO Runtime Spec v1.0 and Implementation Packet v1.0.

This architecture document is primarily about **(1) + (2)** as the **Mission Orchestrator**, and about how they must behave when invoked under **(3)**.

### 2.2 Conceptual Diagram

At a high level, in governed mode:

```text
LifeOS Intake / Council / CSO
        ↓ (governed mission)
      COO Runtime (FSM, Freeze, AMU₀, Replay)
        ↓ (TMD-approved workload)
   COO-Agent Mission Orchestrator
        ↓
  Agent Team + Sandbox + Message Bus
        ↓
    Artefacts + Logs → Flight Recorder
