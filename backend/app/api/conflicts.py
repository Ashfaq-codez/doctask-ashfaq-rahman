import os
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import aliased
from app.db import get_db
from app.models.conflict import Conflict, ConflictStatus
from app.models.fact import Fact
from app.models.document import Document

router = APIRouter(tags=["conflicts"])


@router.get("/pending")
async def get_pending_conflicts(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    """Fetches pending conflicts, their exact quotes, and the target document ID."""
    FactA = aliased(Fact)
    FactB = aliased(Fact)

    query = (
        select(Conflict, FactA.paragraph_text, FactB.paragraph_text, FactB.document_id)
        .outerjoin(FactA, Conflict.fact_a_id == FactA.id)  # type: ignore[arg-type]
        .outerjoin(FactB, Conflict.fact_b_id == FactB.id)  # type: ignore[arg-type]
        .where(Conflict.status == ConflictStatus.PENDING_REVIEW)
        .order_by(Conflict.created_at.desc())  # type: ignore[attr-defined]
    )

    result = await db.execute(query)
    results = result.all()

    output = []
    for row in results:
        conflict_obj: Conflict = row[0]
        fact_a_text: str = row[1] or "Historic context not found."
        fact_b_text: str = row[2] or getattr(conflict_obj, "new_fact_text", None) or "New context not found."
        doc_id: str = str(row[3] or getattr(conflict_obj, "document_id", "") or "")

        output.append({
            "id": str(conflict_obj.id),
            "run_id": str(conflict_obj.run_id) if getattr(conflict_obj, "run_id", None) is not None else None,
            "topic": getattr(conflict_obj, "topic", "General"),
            "ai_reasoning": getattr(conflict_obj, "ai_reasoning", None) or getattr(conflict_obj, "reasoning", ""),
            "status": str(conflict_obj.status.value if hasattr(conflict_obj.status, "value") else conflict_obj.status),
            "fact_a_text": fact_a_text,
            "fact_b_text": fact_b_text,
            "document_id": doc_id
        })

    return output


@router.post("/{conflict_id}/resolve")
async def resolve_conflict(conflict_id: str, payload: Dict[str, Any], db: AsyncSession = Depends(get_db)) -> Dict[str, str]:
    """Resolves the conflict and updates truth state."""
    conflict = await db.get(Conflict, conflict_id)
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")

    status_val = payload.get("status", "RESOLVED")
    
    # Try mapping to enum member if matching
    try:
        status_enum = ConflictStatus(status_val)
        setattr(conflict, "status", status_enum)
    except Exception:
        setattr(conflict, "status", status_val)

    # State mutation: If superseded, deactivate historic fact
    fact_a_id = getattr(conflict, "fact_a_id", None)
    if status_val in ["RESOLVED_KEPT_B", "resolved_kept_b"] and fact_a_id is not None:
        fact_a = await db.get(Fact, str(fact_a_id))
        if fact_a:
            setattr(fact_a, "is_active", False)

    await db.commit()
    return {"status": "success"}


@router.get("/document-text/{document_id}")
async def get_document_text(document_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, str]:
    """Reads the raw text for a document from storage."""
    doc = await db.get(Document, document_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found in database.")

    file_path = getattr(doc, "storage_path", None)
    file_name = getattr(doc, "file_name", "")

    possible_paths = [
        file_path,
        os.path.join("storage", "uploads", file_name) if file_name else None,
        os.path.join("backend", "storage", "uploads", file_name) if file_name else None,
        os.path.join("..", "storage", "uploads", file_name) if file_name else None,
        os.path.join("/app/storage/uploads", file_name) if file_name else None,
    ]

    valid_path = None
    for path in possible_paths:
        if path and isinstance(path, str) and os.path.exists(path):
            valid_path = path
            break

    if not valid_path:
        raise HTTPException(status_code=404, detail="Document file not found on the server disk.")

    try:
        with open(valid_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return {"text": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")