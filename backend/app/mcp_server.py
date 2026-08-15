import os
from typing import List, Dict, Any, cast
from celery import Task
from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models.fact import Fact
from app.models.conflict import Conflict, ConflictStatus
from app.models.run import Run, RunStatus
from app.models.document import Document, DocumentStatus
from app.worker import process_document_task

# Initialize FastMCP Server
mcp = FastMCP("SuperDocs Agentic Auditor")


@mcp.tool()
async def list_verified_facts() -> List[Dict[str, Any]]:
    """Retrieves all active, verified facts with citations from the persistent truth store."""
    async with AsyncSessionLocal() as db:
        query = await db.execute(
            select(Fact)
            .where(Fact.is_active == True)  # type: ignore[arg-type]
            .order_by(Fact.created_at.desc())  # type: ignore[attr-defined]
        )
        facts = query.scalars().all()
        return [
            {
                "id": str(f.id),
                "document_id": str(f.document_id),
                "fact_statement": str(f.value),
                "provenance_quote": str(getattr(f, "paragraph_text", "") or ""),
                "page_number": str(getattr(f, "page_number", "1") or "1"),
            }
            for f in facts
        ]


@mcp.tool()
async def get_pending_conflicts() -> List[Dict[str, Any]]:
    """Fetches all unresolved conflicts and contradictions awaiting human gate approval."""
    async with AsyncSessionLocal() as db:
        query = await db.execute(
            select(Conflict)
            .where(Conflict.status == ConflictStatus.PENDING_REVIEW)
            .order_by(Conflict.created_at.desc())  # type: ignore[attr-defined]
        )
        conflicts = query.scalars().all()
        return [
            {
                "conflict_id": str(c.id),
                "run_id": str(c.run_id) if getattr(c, "run_id", None) is not None else None,
                "topic": str(getattr(c, "topic", "General")),
                "reasoning": str(getattr(c, "ai_reasoning", None) or getattr(c, "reasoning", "")),
                "status": str(c.status.value if hasattr(c.status, "value") else c.status),
            }
            for c in conflicts
        ]


@mcp.tool()
async def resolve_conflict_gate(conflict_id: str, decision: str) -> Dict[str, str]:
    """
    Executes a machine or human decision on a pending conflict.
    Accepts: 'RESOLVED_KEPT_A' (retain historic fact), 'RESOLVED_KEPT_B' (override with new fact).
    """
    async with AsyncSessionLocal() as db:
        conflict = await db.get(Conflict, conflict_id)
        if not conflict:
            return {"status": "error", "message": f"Conflict {conflict_id} not found."}

        # Resolve enum status
        if decision in ConflictStatus.__members__:
            setattr(conflict, "status", ConflictStatus[decision])
        else:
            setattr(conflict, "status", ConflictStatus.RESOLVED_KEPT_A)

        # If new fact overrides original, deactivate original
        fact_a_id = getattr(conflict, "fact_a_id", None)
        if decision in ["RESOLVED_KEPT_B", "resolved_kept_b"] and fact_a_id is not None:
            fact_a = await db.get(Fact, str(fact_a_id))
            if fact_a:
                setattr(fact_a, "is_active", False)

        await db.commit()
        return {
            "status": "success",
            "conflict_id": conflict_id,
            "resolved_status": str(conflict.status.value if hasattr(conflict.status, "value") else conflict.status),
        }


@mcp.tool()
async def start_document_audit(file_path: str) -> Dict[str, str]:
    """Ingests a document from disk, starts a traceable Run, and queues the agentic workflow."""
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File does not exist on disk: {file_path}"}

    async with AsyncSessionLocal() as db:
        # 1. Initialize Run
        new_run = Run(status=RunStatus.PENDING, current_stage="upload")
        db.add(new_run)
        await db.commit()
        await db.refresh(new_run)

        # 2. Register Document
        new_doc = Document(
            run_id=new_run.id,
            file_name=os.path.basename(file_path),
            file_type="text/plain",
            file_hash=str(hash(file_path)),
            storage_path=file_path,
            status=DocumentStatus.UPLOADED,
        )
        db.add(new_doc)
        await db.commit()
        await db.refresh(new_doc)

        # 3. Trigger Celery Task
        task_runner = cast(Task, process_document_task)
        task_runner.delay(
            run_id=str(new_run.id),
            document_id=str(new_doc.id),
            file_path=file_path,
        )

        return {
            "status": "success",
            "run_id": str(new_run.id),
            "document_id": str(new_doc.id),
            "message": "Audit dispatched to background worker.",
        }


if __name__ == "__main__":
    mcp.run(transport="stdio")