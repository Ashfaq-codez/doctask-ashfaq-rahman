# Architectural Specification: SuperDocs Agentic Auditor

## 1. High-Level System Architecture


```
                   ┌────────────────────────┐
                   │  React Dashboard (Vite) │
                   │    (Neo-Brutalist UI)  │
                   └───────────┬────────────┘
                               │ HTTP / SSE
                   ┌───────────▼────────────┐
                   │    FastAPI Gateway     │
                   └─────┬────────────┬─────┘
                         │            │
       ┌─────────────────┴─┐        ┌─┴─────────────────┐
       │ REST Endpoints    │        │ FastMCP Server    │
       │ (/upload, /facts) │        │ (Machine Tools)   │
       └─────────────────┬─┘        └─┬─────────────────┘
                         │            │
                         ▼            ▼
                   ┌────────────────────────┐
                   │   Redis Task Broker    │
                   └───────────┬────────────┘
                               │
                               ▼
                   ┌────────────────────────┐
                   │ Celery Background      │
                   │ Worker Process         │
                   └───────────┬────────────┘
                               │
                               ▼
                   ┌────────────────────────┐
                   │ LangGraph Orchestrator │
                   └───────────┬────────────┘
                               │
    ┌──────────────────────────┼──────────────────────────┐
    ▼                          ▼                          ▼

┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│  Guardrail &  │          │ Atomic Fact   │          │ Conflict &    │
│  Sanitizer    │ ───────► │ Extraction    │ ───────► │ Anomaly       │
│  (Node 0)     │          │ (Node 1)      │          │ Audit (Node 2)│
└───────────────┘          └───────────────┘          └───────────────┘
│                          │                          │
└──────────────────────────┼──────────────────────────┘
│ Checkpoints & State
▼
┌────────────────────────┐
│ PostgreSQL Database    │
│ (State, Facts, Runs)   │
└────────────────────────┘

```

---

## 2. Core State Machine (LangGraph Flow)

The multi-stage execution pipeline is managed by a compiled LangGraph state machine using typed transitions:


```

[START]
│
▼
[guardrail_sanitizer_node] ── (Scans document for prompt injection / malicious overrides)
│
▼
[extract_facts_node]       ── (Extracts atomic statements with exact source substring quotes)
│
▼
[detect_conflicts_node]    ── (Audits newly extracted facts against persistent historic memory)
│
▼
[END]

```

### Resumption & Crash Resilience
Every node transition executes against an `AsyncPostgresSaver` checkpointer bound to a persistent `thread_id` (derived from the `run_id`). If the host process is terminated at any step, the worker inspects the checkpoint tuple upon boot and resumes execution from the exact prior node state without re-running finished tasks.

---

## 3. Database Schema

### `runs`
* `id` (VARCHAR PK): Unique Run UUID.
* `status` (ENUM): `PENDING`, `CLASSIFYING`, `EXTRACTING`, `PAUSED_FOR_REVIEW`, `COMPLETED`, `FAILED`.
* `current_stage` (VARCHAR): Visible workflow step indicator.
* `total_cost` (FLOAT): Total estimated USD spend across all LLM nodes.
* `total_tokens` (FLOAT): Aggregated input/output token consumption.

### `documents`
* `id` (VARCHAR PK): Unique Document identifier.
* `run_id` (VARCHAR FK): Foreign key referencing parent Run.
* `file_name` (VARCHAR): Client-provided or sanitized filename.
* `file_hash` (VARCHAR INDEX): SHA-256 hash for incremental deduplication.
* `storage_path` (VARCHAR): File location on disk.
* `status` (ENUM): `UPLOADED`, `CLASSIFIED`, `EMBEDDED`, `PROCESSED`, `FAILED`, `IGNORED_DUPLICATE`.

### `facts`
* `id` (VARCHAR PK): Fact UUID.
* `document_id` (VARCHAR FK): Reference to source Document.
* `key` (VARCHAR): Fact category descriptor.
* `value` (TEXT): Normalized atomic proposition statement.
* `paragraph_text` (TEXT): Verbatim provenance quote from the source.
* `page_number` (VARCHAR): Citation page or section reference.
* `is_active` (BOOLEAN): Active truth flag (toggled to false upon review gate override).

### `conflicts`
* `id` (VARCHAR PK): Conflict UUID.
* `run_id` (VARCHAR FK): Reference to originating Run.
* `topic` (VARCHAR): Domain clause / issue name.
* `fact_a_id` (VARCHAR FK): Pointer to historical baseline Fact.
* `fact_b_id` (VARCHAR FK): Pointer to contradicting new Fact.
* `ai_reasoning` (TEXT): Audit explanation detailing the discrepancy.
* `status` (ENUM): `PENDING_REVIEW`, `RESOLVED_KEPT_A`, `RESOLVED_KEPT_B`, `RESOLVED_MANUAL_EDIT`.
