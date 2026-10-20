# Rules.md

This document outlines the core operational rules, coding standards, architectural invariants, and safety boundaries for the **CentrAlign Autonomous AI Employee Runtime**.

Every contributor, agent, and subsystem must strictly adhere to these guidelines to ensure reliability, auditability, and production-grade safety.

## 1. Architectural Invariants

### 1.1 Separation of Reasoning and Determinism

- **Probabilistic layers** (LLM planners, natural-language intent parsing, and error diagnosis) handle ambiguity and strategy.
- **Deterministic layers** (state-machine execution, schema validation, policy checks, memory lookup, and independent verification) govern execution, permissions, and audit logging.

### 1.2 The Execution Loop Is Sacred

Every task must execute through the immutable state-machine progression:

\[
\text{GOAL} \longrightarrow \text{UNDERSTAND} \longrightarrow \text{PLAN} \longrightarrow \text{EXECUTE} \longrightarrow \text{OBSERVE} \longrightarrow \text{ADAPT} \longrightarrow \text{VERIFY} \longrightarrow \text{COMPLETE}
\]

### 1.3 An Actor Cannot Grade Its Own Homework

The component that executes a step is strictly forbidden from verifying its success. Every plan step must declare an explicit **Verification Predicate** evaluated independently by `core/verifier.py` against the system of record.

### 1.4 Zero-Trust Tool Boundary

All tools and connectors (`BaseConnector`) must validate their inputs using Pydantic models, declare their `RiskLevel`, and return standardized `ToolResult` structures containing execution status, output data, error traces, and screenshot paths.

## 2. Coding & Quality Standards

### 2.1 Strict Type Hinting

All Python code must include complete type annotations. Untyped functions or loose `Any` types without justification are prohibited.

### 2.2 Pydantic v2 Models

All data structures crossing system boundaries (state transitions, tool arguments, memory stores, audit events, and evidence bundles) must be modeled using Pydantic `BaseModel` classes with strict validation.

### 2.3 Idempotency & Failure Recovery

- Connectors must be designed to fail gracefully.
- Transient network or UI errors must trigger exponential backoff.
- Schema and validation errors must trigger the `ADAPT` phase to analyze the exception, mutate parameters, and persist an episodic memory lesson.

### 2.4 No Hardcoded Secrets or Configs

All configurations, ports, paths, and API keys must be loaded from environment variables (`.env`) or explicit configuration schemas (`company_memory.json`).

## 3. Security, Policy & Human-in-the-Loop (HITL) Rules

### 3.1 Blast-Radius Classification

Every tool action must be classified into one of three risk tiers:

- `READ_ONLY`: Safe inspection queries (no state change).
- `LOW_MUTATION`: Internal standard updates (e.g., vendor registration).
- `HIGH_FINANCIAL`: Financial mutations, external API calls, or actions exceeding organizational policy thresholds.

### 3.2 Mandatory HITL Interception

Any action classified as `HIGH_FINANCIAL` or exceeding configured organizational limits (e.g., payouts greater than ₹50,000) must automatically trigger a runtime pause (`WAITING_FOR_APPROVAL`), serialize a state checkpoint to disk, and await explicit human authorization before proceeding.

### 3.3 Audit Trail Immutability

Every phase transition, tool invocation, error catch, memory update, and verification check must be appended to the run's chronological audit log with precise timestamps and metadata.

## 4. Testing & Verification Rules

### 4.1 Automated Test Coverage

All core modules (`runtime.py`, `memory.py`, `policy.py`, and `verifier.py`) must have corresponding unit and integration tests under `tests/`.

### 4.2 Playwright Screenshot Evidence

Any browser-based interaction (`BrowserConnector`) must capture full-page PNG screenshots on both success and failure, storing them inside `./workspace/evidence/<run_id>/` for auditability.

### 4.3 Clean-Room Execution

The test suite and demo runner (`run_demo.py`) must be fully reproducible from a fresh workspace checkout without manual intervention.
