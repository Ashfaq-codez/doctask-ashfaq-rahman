# SuperDocs Task Tracker & Roadmap

## Phase 1: Infrastructure & Data Modeling (✅ COMPLETED)
- [x] Scaffold FastAPI backend and React frontend[cite: 9].
- [x] Configure PostgreSQL 16 engine and Async SQLAlchemy session factory[cite: 8, 9].
- [x] Define declarative ORM schemas (`Run`, `Document`, `Fact`, `Conflict`, `EventLog`, `ReviewItem`)[cite: 9].
- [x] Generate and apply initial Alembic database migrations (`f5141b7fc326`)[cite: 9].

## Phase 2: Core Agentic Processing & Persistence (✅ COMPLETED)
- [x] Build file ingestion endpoint (`POST /api/v1/upload/`) with SHA-256 hash deduplication[cite: 9].
- [x] Configure Redis message broker and Celery asynchronous background worker[cite: 9].
- [x] Implement LangGraph state machine with structured Pydantic output schemas (`FactExtraction`, `ConflictExtraction`)[cite: 9].
- [x] Bridge Celery synchronous task runners with async database sessions[cite: 9].
- [x] Add fact deduplication layer during database persistence[cite: 9].

## Phase 3: Reasoning, Review Gate & Human-in-the-Loop (✅ COMPLETED)
- [x] Implement `detect_conflicts_node` to cross-reference extracted facts against historical memory[cite: 9].
- [x] Build `/api/v1/conflicts/pending` and `/resolve` endpoints for human gate decisions[cite: 9].
- [x] Build React Dashboard with real-time polling ("Live Sync") and conflict review cards[cite: 9].
- [x] Implement truth mutation logic (`is_active = False` on superseded records) upon review override[cite: 9].
- [x] Align PostgreSQL status enums (`DocumentStatus`, `RunStatus`, `ConflictStatus`) across API and worker layers.

## Phase 4: Production Hardening & Machine Surface (✅ COMPLETED)
- [x] Add `exact_quote` and `page_number` provenance tracking to fact extraction schemas[cite: 9].
- [x] Implement prompt injection defense node (`guardrail_sanitizer_node`) to treat adversarial instructions as data[cite: 8].
- [x] Integrate LangGraph PostgreSQL checkpointing (`AsyncPostgresSaver`) for crash recovery and resumability[cite: 9].
- [x] Add stage-by-stage token and USD cost calculation saved to the `Run` model[cite: 8].
- [x] Implement FastMCP stdio interface (`backend/app/mcp_server.py`) exposing 4 tools for autonomous machine execution[cite: 8, 9].
- [x] Containerize the entire 5-service stack via `docker-compose.yml`[cite: 9].

## Phase 5: Automated Testing & Verification (✅ COMPLETED)
- [x] Create deterministic wire-level VCR test fixtures for zero-key evaluation[cite: 9].
- [x] Build 7/7 test suite (`test_agent.py`, `test_agent_behaviors.py`) covering crash recovery, concurrency isolation, and adversarial prompt handling[cite: 9].
- [x] Provide out-of-the-box contract evaluation samples in `/samples`[cite: 9].
- [x] Complete updated root `README.md`, `ARCHITECTURE.md`, and `PROGRESS.md`[cite: 8, 9].

