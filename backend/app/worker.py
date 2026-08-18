import os
import asyncio
from typing import List, Dict, Any
from celery import Celery
from dotenv import load_dotenv
from sqlalchemy import select

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # type: ignore[import-untyped]

from app.db import AsyncSessionLocal, engine
from app.models.fact import Fact
from app.models.run import Run, RunStatus
from app.models.document import Document, DocumentStatus
from app.models.conflict import Conflict, ConflictStatus
from app.agent.graph import build_agent_graph, AgentState
from app.services.parser import extract_document_text

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

REDIS_URL = os.environ.get("REDIS_URL")
if not REDIS_URL:
    raise ValueError("REDIS_URL environment variable is missing.")

celery_app = Celery("superdocs_worker", broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


async def fetch_existing_facts() -> str:
    """Fetches active historic facts from the database."""
    async with AsyncSessionLocal() as db:
        query = await db.execute(select(Fact).where(Fact.is_active == True).limit(100))  # type: ignore[arg-type]
        facts = query.scalars().all()

        if not facts:
            return "No existing facts in the database."

        formatted_facts = [f"{fact.id}: {fact.value}" for fact in facts]
        return "\n".join(formatted_facts)


async def persist_results_to_db(
    run_id_str: str,
    document_id_str: str,
    facts: List[Dict[str, Any]],
    conflicts: List[Dict[str, Any]],
    total_cost: float = 0.0,
    total_tokens: float = 0.0,
) -> None:
    """Persists extracted facts with deduplication, links conflicts, and records cost metrics."""
    async with AsyncSessionLocal() as db:
        try:
            run = await db.get(Run, run_id_str)
            doc = await db.get(Document, document_id_str)

            if doc:
                setattr(doc, "status", DocumentStatus.PROCESSED)

            new_facts_map: Dict[str, Fact] = {}
            seen_values = set()

            # 1. Save extracted facts with deduplication
            for fact_data in facts:
                val = fact_data.get("fact_value", "").strip()
                if not val or val.lower() in seen_values:
                    continue

                seen_values.add(val.lower())

                new_fact = Fact(
                    document_id=document_id_str,
                    key="extracted_statement",
                    value=val,
                    paragraph_text=fact_data.get("exact_quote", ""),
                    page_number=str(fact_data.get("page_number", "1")),
                    is_active=True,
                )
                db.add(new_fact)
                new_facts_map[val] = new_fact

            # 2. Add fallback fact for new contradicting statements if missing
            for conflict_data in conflicts:
                if conflict_data.get("type") == "contradiction":
                    text = conflict_data.get("new_fact_text", "").strip()
                    if text and text not in new_facts_map and text.lower() not in seen_values:
                        seen_values.add(text.lower())
                        fallback_fact = Fact(
                            document_id=document_id_str,
                            key="extracted_statement",
                            value=text,
                            paragraph_text=text,
                            page_number="1",
                            is_active=True,
                        )
                        db.add(fallback_fact)
                        new_facts_map[text] = fallback_fact

            await db.flush()

            # Fetch most recent historic fact from another document for linkage
            query_prev_facts = await db.execute(
                select(Fact)
                .where(Fact.document_id != document_id_str, Fact.is_active == True)  # type: ignore[arg-type]
                .order_by(Fact.created_at.desc())  # type: ignore[attr-defined]
                .limit(1)
            )
            latest_historic_fact = query_prev_facts.scalar_one_or_none()

            has_pending_conflicts = False

            # 3. Create conflict records
            for conflict_data in conflicts:
                conf_type = conflict_data.get("type", "anomaly")

                if conf_type == "anomaly":
                    new_conflict = Conflict(
                        run_id=run_id_str,
                        topic=conflict_data.get("topic", "General Anomaly"),
                        ai_reasoning=conflict_data.get("reasoning", ""),
                        status=ConflictStatus.PENDING_REVIEW,
                    )
                    db.add(new_conflict)
                    has_pending_conflicts = True

                elif conf_type == "contradiction":
                    existing_fact_id = conflict_data.get("existing_fact_id")
                    existing_fact = await db.get(Fact, str(existing_fact_id)) if existing_fact_id else None

                    if not existing_fact and latest_historic_fact:
                        existing_fact = latest_historic_fact

                    new_text = conflict_data.get("new_fact_text", "")
                    related_new_fact = new_facts_map.get(new_text)
                    if not related_new_fact and new_facts_map:
                        related_new_fact = list(new_facts_map.values())[0]

                    if existing_fact and related_new_fact:
                        new_conflict = Conflict(
                            run_id=run_id_str,
                            topic=conflict_data.get("topic", "Fact Contradiction"),
                            fact_a_id=existing_fact.id,
                            fact_b_id=related_new_fact.id,
                            ai_reasoning=conflict_data.get(
                                "reasoning", "Contradicts existing verified fact."
                            ),
                            status=ConflictStatus.PENDING_REVIEW,
                        )
                        db.add(new_conflict)
                        has_pending_conflicts = True
                    else:
                        new_conflict = Conflict(
                            run_id=run_id_str,
                            topic=conflict_data.get("topic", "Document Anomaly"),
                            ai_reasoning=conflict_data.get(
                                "reasoning", "Cross-document discrepancy detected."
                            ),
                            status=ConflictStatus.PENDING_REVIEW,
                        )
                        db.add(new_conflict)
                        has_pending_conflicts = True

            # 4. Set Run status and store tracking metrics[cite: 1]
            if run:
                setattr(run, "total_cost", total_cost)
                setattr(run, "total_tokens", total_tokens)
                if has_pending_conflicts:
                    setattr(run, "status", RunStatus.PAUSED_FOR_REVIEW)
                    setattr(run, "current_stage", "paused_for_review")
                else:
                    setattr(run, "status", RunStatus.COMPLETED)
                    setattr(run, "current_stage", "completed")

            await db.commit()
            print(f"💾 [DATABASE] Successfully saved {len(new_facts_map)} unique facts and cost metrics.")

        except Exception as e:
            await db.rollback()
            print(f"❌ [DATABASE] Failed to save results: {str(e)}")
            raise e


async def execute_agent_workflow(run_id: str, document_id: str, file_path: str):
    try:
        print(f"\n🚀 [WORKER] Initiating LangGraph execution for Run: {run_id}")
        existing_facts_context = await fetch_existing_facts()

        # Read document text safely from disk
        document_text = ""
        possible_paths = [
            file_path,
            os.path.join("storage", "uploads", os.path.basename(file_path)) if file_path else None,
            os.path.join("/app/storage/uploads", os.path.basename(file_path)) if file_path else None,
        ]
        for p in possible_paths:
            if p and os.path.exists(p):
                document_text = extract_document_text(p)
                break
                try:
                    if p.lower().endswith(".pdf"):
                        # Extract clean text from PDF pages
                        try:
                            import pypdf
                            reader = pypdf.PdfReader(p)
                            document_text = "\n".join([page.extract_text() or "" for page in reader.pages])
                        except Exception:
                            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                                document_text = f.read()
                    else:
                        with open(p, "r", encoding="utf-8", errors="ignore") as f:
                            document_text = f.read()
                    break
                except Exception as read_err:
                    print(f"⚠️ [WORKER] Could not read file at {p}: {read_err}")

        initial_state: AgentState = {
            "run_id": run_id,
            "document_id": document_id,
            "file_path": file_path,
            "document_text": document_text,
            "existing_facts": existing_facts_context,
            "extracted_facts": [],
            "conflicts": [],
            "security_flags": [],
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "estimated_cost_usd": 0.0,
            "current_stage": "initialized",
        }

        db_uri = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")

        async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
            await checkpointer.setup()
            agent_app = build_agent_graph(checkpointer=checkpointer)
            config: RunnableConfig = {"configurable": {"thread_id": run_id}}

            # Checkpoint Resumption Safety
            checkpoint_tuple = await checkpointer.aget_tuple(config)
            agent_input = None if (checkpoint_tuple and checkpoint_tuple.checkpoint) else initial_state

            final_state = await agent_app.ainvoke(agent_input, config=config)

        extracted_facts = final_state.get("extracted_facts", []) if final_state else []
        conflicts = final_state.get("conflicts", []) if final_state else []
        total_cost = float(final_state.get("estimated_cost_usd", 0.0)) if final_state else 0.0
        total_tokens = float(final_state.get("total_tokens", 0.0)) if final_state else 0.0

        await persist_results_to_db(
            run_id_str=run_id,
            document_id_str=document_id,
            facts=extracted_facts,
            conflicts=conflicts,
            total_cost=total_cost,
            total_tokens=total_tokens,
        )
        return {"status": "success", "run_id": run_id}

    finally:
        await engine.dispose()


@celery_app.task(name="process_document_task", bind=True, max_retries=3)
def process_document_task(self, run_id: str, document_id: str, file_path: str):
    try:
        return asyncio.run(execute_agent_workflow(run_id, document_id, file_path))
    except Exception as e:
        print(f"❌ [WORKER] Execution Failed: {str(e)}\n")
        raise self.retry(exc=e, countdown=10)