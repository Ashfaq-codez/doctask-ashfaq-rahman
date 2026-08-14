import os
import asyncio
from celery import Celery
from dotenv import load_dotenv
from sqlalchemy import select

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver # type: ignore

from app.db import AsyncSessionLocal, engine
from app.models.fact import Fact
from app.models.run import Run, RunStatus
from app.models.document import Document, DocumentStatus
from app.models.conflict import Conflict, ConflictStatus
from app.agent.graph import agent_executor, AgentState

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

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
    """Fetches ONLY active historic facts from the database."""
    async with AsyncSessionLocal() as db:
        query = await db.execute(select(Fact).where(Fact.is_active == True).limit(100)) # type: ignore
        facts = query.scalars().all()
        
        if not facts:
            return "No existing facts in the database."
        
        formatted_facts = [f"{fact.id}: {fact.value}" for fact in facts]
        return "\n".join(formatted_facts)

async def persist_results_to_db(run_id_str: str, document_id_str: str, facts: list[dict], conflicts: list[dict]) -> None:
    async with AsyncSessionLocal() as db:
        try:
            run = await db.get(Run, run_id_str)
            if run:
                run.status = RunStatus.COMPLETED      # type: ignore
                run.current_stage = "completed"       # type: ignore

            doc = await db.get(Document, document_id_str)
            if doc:
                doc.status = DocumentStatus.PROCESSED # type: ignore

            new_facts_map = {}
            for fact_data in facts:
                new_fact = Fact(
                    document_id=document_id_str, 
                    key="extracted_statement", 
                    value=fact_data["fact_value"],
                    paragraph_text=fact_data.get("exact_quote", ""), 
                    page_number=str(fact_data.get("page_number", "1")),
                    is_active=True
                )
                db.add(new_fact)
                new_facts_map[fact_data["fact_value"]] = new_fact
                
            for conflict_data in conflicts:
                if conflict_data["type"] == "contradiction":
                    text = conflict_data["new_fact_text"]
                    if text not in new_facts_map:
                        fallback_fact = Fact(document_id=document_id_str, key="extracted_statement", value=text, is_active=True)
                        db.add(fallback_fact)
                        new_facts_map[text] = fallback_fact

            await db.flush() 

            for conflict_data in conflicts:
                if conflict_data["type"] == "anomaly":
                    existing = await db.execute(
                        select(Conflict).where(
                            Conflict.topic == conflict_data["topic"],
                            Conflict.ai_reasoning == conflict_data["reasoning"],
                            Conflict.status == ConflictStatus.PENDING_REVIEW
                        )
                    )
                    if existing.first():
                        continue 

                    new_conflict = Conflict(
                        run_id=run_id_str,
                        topic=conflict_data["topic"],
                        ai_reasoning=conflict_data["reasoning"],
                        status=ConflictStatus.PENDING_REVIEW
                    )
                    db.add(new_conflict)
                    
                elif conflict_data["type"] == "contradiction":
                    existing_fact = await db.get(Fact, conflict_data["existing_fact_id"])
                    if not existing_fact:
                        continue 
                        
                    existing_contra = await db.execute(
                        select(Conflict).where(
                            Conflict.topic == conflict_data["topic"],
                            Conflict.fact_a_id == existing_fact.id,
                            Conflict.status == ConflictStatus.PENDING_REVIEW
                        )
                    )
                    if existing_contra.first():
                        continue 
                    
                    related_new_fact = new_facts_map[conflict_data["new_fact_text"]]
                    new_conflict = Conflict(
                        run_id=run_id_str,
                        topic=conflict_data["topic"],
                        fact_a_id=existing_fact.id, 
                        fact_b_id=related_new_fact.id,                       
                        ai_reasoning=conflict_data["reasoning"],
                        status=ConflictStatus.PENDING_REVIEW
                    )
                    db.add(new_conflict)

            await db.commit()
            print(f"💾 [DATABASE] Successfully saved {len(facts)} facts and processed {len(conflicts)} conflicts.")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ [DATABASE] Failed to save results: {str(e)}")
            raise e

async def execute_agent_workflow(run_id: str, document_id: str, file_path: str):
    try:
        print(f"\n🚀 [WORKER] Initiating LangGraph execution for Run: {run_id}")
        existing_facts_context = await fetch_existing_facts()
        
        initial_state: AgentState = {
            "run_id": run_id,
            "document_id": document_id,
            "file_path": file_path,
            "document_text": "",
            "existing_facts": existing_facts_context, 
            "extracted_facts": [],
            "conflicts": [],
            "current_stage": "initialized"
        }
        
        db_uri = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")
        
        async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
            await checkpointer.setup()
            agent_app = agent_executor.builder.compile(checkpointer=checkpointer)
            config: RunnableConfig = {"configurable": {"thread_id": run_id}}
            
            # CHECKPOINT RESUMPTION SAFETY
            # If checkpoint exists for this thread, passing None instructs LangGraph to resume state
            checkpoint_tuple = await checkpointer.aget_tuple(config)
            agent_input = None if (checkpoint_tuple and checkpoint_tuple.checkpoint) else initial_state
            
            final_state = await agent_app.ainvoke(agent_input, config=config)
        
        extracted_facts = final_state.get('extracted_facts', [])
        conflicts = final_state.get('conflicts', [])
        
        await persist_results_to_db(run_id, document_id, extracted_facts, conflicts)
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