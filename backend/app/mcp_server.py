import os
import hashlib
import uuid
from fastmcp import FastMCP # type: ignore
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models.conflict import Conflict, ConflictStatus
from app.models.fact import Fact
from app.models.run import Run, RunStatus
from app.models.document import Document, DocumentStatus
from app.worker import process_document_task

mcp = FastMCP("SuperDocs Agentic Interface")

@mcp.tool()
async def upload_document_text(filename: str, content: str) -> str:
    """Upload a new document text directly to the SuperDocs system for auditing."""
    run_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    
    file_path = os.path.join("storage", "uploads", filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    deterministic_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        
    async with AsyncSessionLocal() as db:
        new_run = Run(id=run_id, status=RunStatus.PENDING) # type: ignore
        db.add(new_run)
        await db.commit()
        
        new_doc = Document(
            id=document_id,
            run_id=run_id,
            file_name=filename,
            file_type="text/plain",
            file_hash=deterministic_hash,
            storage_path=file_path,
            status=DocumentStatus.UPLOADED # type: ignore
        )
        db.add(new_doc)
        await db.commit()
        
    process_document_task.delay(run_id, document_id, file_path) # type: ignore
    return f"Successfully ingested {filename}. Audit pipeline started with Run ID: {run_id}."

@mcp.tool()
async def get_pending_reviews() -> str:
    """Fetch all pending document conflicts that require human resolution."""
    async with AsyncSessionLocal() as db:
        query = await db.execute(
            select(Conflict).where(Conflict.status == ConflictStatus.PENDING_REVIEW.value) # type: ignore
        )
        conflicts = query.scalars().all()
        
        if not conflicts:
            return "System Clear. No pending conflicts require review."
            
        report = ["PENDING CONFLICTS:"]
        for c in conflicts:
            report.append(f"- ID: {c.id}\n  Topic: {c.topic}\n  AI Reasoning: {c.ai_reasoning}\n")
        return "\n".join(report)

@mcp.tool()
async def resolve_document_conflict(conflict_id: str, decision: str, updated_fact_text: str = "") -> str:
    """
    Resolve a pending document conflict and update the verified facts state.
    Arguments:
        decision: 'resolved_kept_a', 'resolved_kept_b', or 'resolved_manual_edit'
        updated_fact_text: Required if decision is 'resolved_manual_edit'
    """
    valid_decisions = ["resolved_kept_a", "resolved_kept_b", "resolved_manual_edit"]
    if decision not in valid_decisions:
        return f"Error: decision must be one of {valid_decisions}."
        
    async with AsyncSessionLocal() as db:
        conflict = await db.get(Conflict, conflict_id)
        if not conflict:
            return f"Error: Conflict {conflict_id} not found."
            
        conflict.status = decision # type: ignore
        
        # Check if both foreign keys are present
        fact_a_id = getattr(conflict, "fact_a_id", None)
        fact_b_id = getattr(conflict, "fact_b_id", None)

        if fact_a_id is not None and fact_b_id is not None:
            fact_a = await db.get(Fact, fact_a_id)
            fact_b = await db.get(Fact, fact_b_id)
            
            if decision == "resolved_kept_a" and fact_b:
                fact_b.is_active = False # type: ignore
            elif decision == "resolved_kept_b" and fact_a:
                fact_a.is_active = False # type: ignore
            elif decision == "resolved_manual_edit" and updated_fact_text:
                if fact_b:
                    fact_b.value = updated_fact_text # type: ignore
                    fact_b.is_active = True # type: ignore
                if fact_a:
                    fact_a.is_active = False # type: ignore
                    
        await db.commit()
        return f"Successfully resolved conflict {conflict_id} with decision '{decision}'."

@mcp.tool()
async def query_verified_facts() -> str:
    """Retrieve all active verified facts extracted across documents."""
    async with AsyncSessionLocal() as db:
        query = await db.execute(select(Fact).where(Fact.is_active == True).limit(100)) # type: ignore
        facts = query.scalars().all()
        
        if not facts:
            return "The verified facts database is currently empty."
            
        report = ["VERIFIED ACTIVE FACTS DATABASE:"]
        for f in facts:
            report.append(f"- [{f.id}]: {f.value}")
        return "\n".join(report)

if __name__ == "__main__":
    mcp.run()