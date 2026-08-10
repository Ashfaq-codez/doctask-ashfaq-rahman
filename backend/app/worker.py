import os
import asyncio
from celery import Celery
from dotenv import load_dotenv

# Database and Model imports
from app.db import AsyncSessionLocal
from app.models.fact import Fact
from app.models.run import Run, RunStatus
from app.models.document import Document, DocumentStatus
from app.models.conflict import Conflict, ConflictStatus
from app.agent.graph import agent_executor, AgentState

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

REDIS_URL = os.environ.get("REDIS_URL")

if not REDIS_URL:
    raise ValueError("REDIS_URL environment variable is missing.")

celery_app = Celery(
    "superdocs_worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

async def persist_results_to_db(run_id_str: str, document_id_str: str, facts: list[str], conflicts: list[str]) -> None:
    """Safely opens an async database session to save the graph's output."""
    
    async with AsyncSessionLocal() as db:
        try:
            # 1. Update the Run and Document statuses
            run = await db.get(Run, run_id_str)
            if run:
                run.status = RunStatus.COMPLETED      # type: ignore
                run.current_stage = "completed"       # type: ignore

            doc = await db.get(Document, document_id_str)
            if doc:
                doc.status = DocumentStatus.PROCESSED # type: ignore

            # 2. Insert the extracted facts
            for fact_text in facts:
                new_fact = Fact(
                    document_id=document_id_str,
                    key="extracted_statement",
                    value=fact_text             
                )
                db.add(new_fact)
                
            # 3. Insert the detected conflicts/anomalies
            for anomaly_text in conflicts:
                new_conflict = Conflict(
                    run_id=run_id_str,
                    topic="Document Anomaly",
                    ai_reasoning=anomaly_text,
                    status=ConflictStatus.PENDING_REVIEW # Flags it for human intervention
                )
                db.add(new_conflict)

            await db.commit()
            print(f"💾 [DATABASE] Successfully saved {len(facts)} facts and {len(conflicts)} conflicts.")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ [DATABASE] Failed to save results: {str(e)}")
            raise e

@celery_app.task(name="process_document_task")
def process_document_task(run_id: str, document_id: str, file_path: str):
    """Executes the LangGraph agent and saves the results."""
    print(f"\n🚀 [WORKER] Initiating LangGraph execution for Run: {run_id}")
    
    initial_state: AgentState = {
        "run_id": run_id,
        "document_id": document_id,
        "file_path": file_path,
        "document_text": "",
        "extracted_facts": [],
        "conflicts": [],
        "current_stage": "initialized"
    }
    
    try:
        final_state = agent_executor.invoke(initial_state)
        extracted_facts = final_state.get('extracted_facts', [])
        conflicts = final_state.get('conflicts', [])
        
        print(f"✅ [WORKER] Graph Execution Complete!")
        print(f"▶ Extracted Facts: {extracted_facts}")
        print(f"▶ Detected Conflicts: {conflicts}")
        
        # Bridge the sync worker to the async database safely
        asyncio.run(persist_results_to_db(run_id, document_id, extracted_facts, conflicts))
        
        return {"status": "success", "run_id": run_id}
        
    except Exception as e:
        print(f"❌ [WORKER] Execution Failed: {str(e)}\n")
        return {"status": "failed", "run_id": run_id, "error": str(e)}