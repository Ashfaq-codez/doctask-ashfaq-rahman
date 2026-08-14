# SuperDocs: Human-Gated Distributed AI Agentic System

SuperDocs is a production-grade, event-driven document analysis pipeline. It extracts atomic facts from uploaded contracts, maintains persistent memory across multi-document sets to detect logical contradictions and anomalies, and enforces a strict Human-in-the-Loop (HITL) review gate before facts enter the verified telemetry store.

---

## 🏛 Architecture Overview

┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Ingestion                      │
│                  (POST /api/v1/upload/)                     │
└──────────────────────────────┬──────────────────────────────┘
│ Dispatches Asynchronous Job
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
│  │   [Load File] ──► [Extract Facts] ──► [Audit/Detect]  │  │
│  │   (PDF/DOCX/TXT)   (Grounded Quote)   (Historic Mem)  │  │
│  │                           ▲                           │  │
│  │                           │ Resumable Checkpointer    │  │
│  │                           ▼ (PostgresSaver)           │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────┘
│ Writes Unverified Conflicts / Verified Facts
▼
┌──────────────────────────────┴──────────────────────────────┐
│                    PostgreSQL 16 Engine                     │
│           (Runs, Documents, Facts, Conflicts)               │
└──────────────────────────────┬──────────────────────────────┘
▲
Reads / Writes Resolution State
│
┌──────────────────────────────┴──────────────────────────────┐
│            React HITL Desk & Model Context Protocol (MCP)   │
└─────────────────────────────────────────────────────────────┘


### Core Capabilities
* **Asynchronous & Distributed:** Ingestion requests immediately return a `Run` ID; Celery workers handle heavy LLM extraction and cross-audit workflows in the background.
* **Grounded Provenance:** Native multi-format parsing (PDF, DOCX, TXT) extracting verifiable facts with `page_number` and verbatim `exact_quote` references.
* **Agentic Reasoning & Contradiction Detection:** Evaluates newly extracted facts against historical database memory to surface cross-document contradictions and document anomalies.
* **Human-in-the-Loop Memory Mutation:** Human auditor decisions update the database truth state (`is_active = False` on superseded records) to eliminate false positives in subsequent runs.
* **Resumability & Crash Proofing:** PostgreSQL checkpointing (`AsyncPostgresSaver`) records graph execution state after every node, allowing interrupted jobs to resume without duplicate LLM calls.
* **Standard Model Context Protocol (MCP):** Integrates FastMCP over standard I/O for client tools (`upload_document_text`, `get_pending_reviews`, `resolve_document_conflict`, `query_verified_facts`).

---

## 🚀 1-Command Startup

Ensure Docker and Docker Compose are installed and running on your system.

1. **Clone the repository and enter the directory:**
   ```bash
   git clone <repo_url>
   cd superdocs
Configure Environment Variables:
Create a .env file in the root directory:

Code snippet
OPENAI_API_KEY=your_openai_api_key_here
Start the complete stack:

Bash
docker compose up --build -d
All five services will launch:

Frontend UI: http://localhost:5173

FastAPI Backend & Swagger Docs: http://localhost:8000/docs

PostgreSQL: localhost:5432

Redis Broker: localhost:6379

Celery Worker: Running in background

🧪 Live-Key-Free Testing Suite
The testing suite validates end-to-end graph parsing, checkpointer resumability, and concurrent run isolation using deterministic wire-level VCR response fixtures without requiring an active OpenAI key or making live network requests.

Run the test suite inside the container:

Bash
docker exec -it superdocs_api pytest
🔌 Running the MCP Server (Model Context Protocol)
The system exposes its auditing tools through the Model Context Protocol. You can test and drive the tools via the MCP Inspector:

Bash
npx @modelcontextprotocol/inspector docker exec -i superdocs_api python -m app.mcp_server
Open the URL provided in the console to execute tools:

upload_document_text: Ingest document text for asynchronous auditing.

get_pending_reviews: Fetch pending anomalies and cross-document contradictions.

resolve_document_conflict: Resolve conflicts and mutate the verified database state.

query_verified_facts: Query all active, verified facts.

## 📂 Project Structure

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
│   │   ├── db.py                 # Async PostgreSQL Engine & Session Factory
│   │   ├── main.py               # FastAPI App Lifespan & Routing Entrypoint
│   │   ├── mcp_server.py         # FastMCP Server (stdio tools)
│   │   ├── models/               # SQLAlchemy Declarative Models
│   │   │   ├── base.py
│   │   │   ├── conflict.py
│   │   │   ├── document.py
│   │   │   ├── event.py
│   │   │   ├── fact.py
│   │   │   ├── review.py
│   │   │   └── run.py
│   │   └── worker.py             # Celery Task & LangGraph Checkpointer Engine
│   ├── migrations/               # Alembic Migration Versions & Environment
│   │   ├── env.py
│   │   └── versions/
│   ├── tests/                    # Zero-Key VCR Deterministic Replay Test Suite
│   │   ├── fixtures/             # Raw OpenAI Wire Payloads
│   │   │   ├── raw_conflict_detection.json
│   │   │   └── raw_fact_extraction.json
│   │   └── test_agent.py
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx               # HITL Audit Desk & Real-Time Sync Dashboard
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
└── uploads/                  # Shared Container Volume for File Ingestion