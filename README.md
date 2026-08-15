# SuperDocs: Human-Gated Distributed AI Agentic System

SuperDocs is an event-driven, distributed document auditing and intelligence platform. It ingests multi-format documents, extracts verifiable atomic facts with source quotes, tracks state checkpoints in PostgreSQL, audits contradictions against historical corpus memory, and routes conflicting findings through an interactive Human-in-the-Loop (HITL) review gate.

---

## 🏛 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Gateway                        │
│             (POST /api/v1/upload/ · GET /facts)             │
└──────────────────────────────┬──────────────────────────────┘
                               │ Dispatches Asynchronous Task
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Redis Message Broker                      │
└──────────────────────────────┬──────────────────────────────┘
                               │ Consumes Task
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Celery Background Worker                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │             LangGraph State Machine                   │  │
│  │                                                       │  │
│  │   [Guardrail Sanitizer] (Prompt Injection Defense)    │  │
│  │            │                                          │  │
│  │            ▼                                          │  │
│  │   [Extract Facts Node]  (Exact Quote & Page Citations)│  │
│  │            │                                          │  │
│  │            ▼                                          │  │
│  │   [Detect Conflicts]    (Historical Truth Memory)     │  │
│  │            ▲                                          │  │
│  │            │ Resumable Checkpointer                   │  │
│  │            ▼ (AsyncPostgresSaver)                     │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────┘
                               │ Persists Unverified Conflicts / Verified Facts
                               ▼
┌──────────────────────────────┴──────────────────────────────┐
│                    PostgreSQL 16 Engine                     │
│        (Runs, Documents, Facts, Conflicts, Checkpoints)     │
└──────────────────────────────┬──────────────────────────────┘
                               ▲
                 Reads / Writes Resolution State
                               │
┌──────────────────────────────┴──────────────────────────────┐
│       React HITL Dashboard & Model Context Protocol (MCP)   │
└─────────────────────────────────────────────────────────────┘

```

### Core Behaviors & Technical Guarantees

* **Visible Multi-Stage Reasoning (Behavior 1):** Explicit pipeline transitions (`guardrail_sanitizer` → `extract_facts` → `detect_conflicts`) observable in real time.
* **Crash Resumption & Checkpointing (Behavior 2):** Every state transition is preserved in PostgreSQL via `AsyncPostgresSaver`. If a container or worker process dies mid-execution, it continues from the last checkpoint without duplicate LLM calls or lost state.
* **Granular Human-in-the-Loop Gate (Behavior 3):** Discrepancies and anomalies are gated in the review desk. Approving an override marks superseded facts as inactive (`is_active = False`) in database memory; rejecting preserves historical truth.
* **Machine Drivable (Behavior 4):** Headless MCP server (`app/mcp_server.py`) provides stdio tools for external AI agents to trigger audits, inspect pending reviews, and apply gate decisions.
* **Strict Fact Provenance (Behavior 5):** Extracted facts mandate verbatim `exact_quote` references and page/paragraph pointers.
* **Zero-Configuration Setup (Behavior 6):** Containerized via Docker Compose to boot from a clean clone with a single command.
* **Offline Deterministic Verification (Behavior 7):** Comprehensive test suite operates offline without requiring a live OpenAI API key via wire-level VCR fixtures.
* **Prompt Injection Resistance (Behavior 8):** Adversarial instructions embedded in source text (e.g., *"Ignore previous instructions"*) are sanitized and quarantined as inert audit findings rather than executed.
* **Thread-Isolated Concurrency (Behavior 9):** Independent `run_id` state partitions prevent cross-talk and race conditions during simultaneous document uploads.
* **Granular Cost & Token Tracking (Behavior 10):** Tracks input/output token counts, execution latency, and USD cost per stage, persisted to the `runs` record.

---

## 🚀 1-Command Startup

Ensure Docker and Docker Compose are running.

### 1. Clone the repository:

```bash
git clone <repo_url>
cd doctask-ashfaq-rahman

```

### 2. Configure Environment:

Copy the example environment file:

```bash
cp .env.example .env

```

*(Note: If `OPENAI_API_KEY` is left blank, the system automatically runs in deterministic offline mode.)*

### 3. Launch Services:

```bash
docker compose up --build -d

```

### Service Endpoints:

* **Interactive HITL Dashboard:** [http://localhost:5173](http://localhost:5173)
* **FastAPI Backend & OpenAPI Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **PostgreSQL Database:** `localhost:5432`
* **Redis Broker:** `localhost:6379`
* **Celery Worker:** Running in background

---

## 🧪 Automated Behavior Test Suite (Keyless)

Run the full automated test suite inside the container without an API key:

```bash
docker exec -it superdocs_api pytest tests/ -v

```

This runs the 7 unit and integration tests covering:

1. Full graph traversal with deterministic wire replay.
2. Checkpointer crash resumability with `MemorySaver` and `AsyncPostgresSaver`.
3. Multi-instance concurrent execution isolation.
4. Prompt injection detection and defense.
5. Verifiable fact citation and provenance quote checks.
6. Atomic fact deduplication.

---

## 🔌 Running the MCP Server (Model Context Protocol)

The system exposes its entire auditing interface over stdio via FastMCP. Test and drive the machine tools using the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector docker exec -i superdocs_api python -m app.mcp_server

```

### Exposed MCP Tools:

* `start_document_audit(file_path: str)`: Dispatches background agentic audit for a document on disk.
* `get_pending_conflicts()`: Retrieves all pending contradictions and anomalies awaiting human review.
* `resolve_conflict_gate(conflict_id: str, decision: str)`: Applies an approval or override decision (`RESOLVED_KEPT_A` / `RESOLVED_KEPT_B`).
* `list_verified_facts()`: Queries active, verified facts with citations and quote provenance.

---

## 📂 Project Structure

```text
.
├── ARCHITECTURE.md
├── CHANGELOG.md
├── DECISIONS.md
├── PROGRESS.md
├── README.md
├── TASKS.md
├── TODO.md
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── agent/                # LangGraph State Machine & Node Definitions
│   │   │   └── graph.py
│   │   ├── api/                  # FastAPI Endpoints (Upload, Runs, Conflicts, Facts)
│   │   │   ├── conflicts.py
│   │   │   ├── documents.py
│   │   │   ├── facts.py
│   │   │   ├── review.py
│   │   │   ├── runs.py
│   │   │   └── upload.py
│   │   ├── db.py                 # Async SQLAlchemy Engine & Session Factory
│   │   ├── main.py               # FastAPI Entrypoint & Router Ingestion
│   │   ├── mcp_server.py         # FastMCP Server (stdio tools)
│   │   ├── models/               # SQLAlchemy ORM Models
│   │   │   ├── base.py
│   │   │   ├── conflict.py
│   │   │   ├── document.py
│   │   │   ├── event.py
│   │   │   ├── fact.py
│   │   │   ├── review.py
│   │   │   └── run.py
│   │   └── worker.py             # Celery Task & State Checkpoint Persistence
│   ├── migrations/               # Alembic Migration Versions & Environment
│   │   ├── env.py
│   │   └── versions/
│   ├── tests/                    # Keyless Deterministic Replay Test Suite
│   │   ├── fixtures/             # Wire Payloads
│   │   │   ├── raw_conflict_detection.json
│   │   │   └── raw_fact_extraction.json
│   │   ├── test_agent.py
│   │   └── test_agent_behaviors.py
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx               # Review Desk & Live Sync UI
│   │   ├── App.css
│   │   ├── index.css
│   │   └── main.tsx
│   ├── Dockerfile
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
├── samples/                      # Out-of-the-Box Evaluation Contracts
│   ├── sample_contract_anomaly.txt
│   ├── sample_contract_v1.txt
│   └── sample_contract_v2_contradiction.txt
└── storage/
    └── uploads/                  # Shared Storage Volume


