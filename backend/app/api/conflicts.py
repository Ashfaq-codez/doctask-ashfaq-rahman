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
from app.services.parser import extract_document_text

router = APIRouter(tags=["conflicts"])


def extract_clean_document_text(file_path: str) -> str:
    """Safely extracts plain text from TXT, MD, or binary PDF files."""
    if not os.path.exists(file_path):
        return "[Error: File not found on disk]"

    if file_path.lower().endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            pages_text = []
            for i, page in enumerate(reader.pages):
                txt = page.extract_text() or ""
                if txt.strip():
                    pages_text.append(f"--- PAGE {i + 1} ---\n{txt.strip()}")
            
            result = "\n\n".join(pages_text)
            return result if result.strip() else "[PDF contains scanned images with no extractable text layer]"
        except Exception as e:
            return f"[Error parsing PDF stream: {str(e)}]"

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"[Error reading document file: {str(e)}]"


@router.get("/pending")
async def get_pending_conflicts(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    FactA = aliased(Fact)
    FactB = aliased(Fact)

    query = (
        select(
            Conflict, 
            FactA.paragraph_text, 
            FactB.paragraph_text, 
            FactA.document_id,
            FactB.document_id
        )
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
        fact_a_text: str = row[1] or ""
        fact_b_text: str = row[2] or getattr(conflict_obj, "new_fact_text", "") or ""
        doc_a_id: str = str(row[3] or "")
        doc_b_id: str = str(row[4] or "")

        output.append({
            "id": str(conflict_obj.id),
            "run_id": str(conflict_obj.run_id) if getattr(conflict_obj, "run_id", None) is not None else None,
            "topic": getattr(conflict_obj, "topic", "General"),
            "ai_reasoning": getattr(conflict_obj, "ai_reasoning", None) or getattr(conflict_obj, "reasoning", ""),
            "status": str(conflict_obj.status.value if hasattr(conflict_obj.status, "value") else conflict_obj.status),
            "fact_a_text": fact_a_text,
            "fact_b_text": fact_b_text,
            "document_id": doc_a_id or doc_b_id,  # Points to baseline doc first
            "doc_a_id": doc_a_id,
            "doc_b_id": doc_b_id
        })

    return output

@router.post("/{conflict_id}/resolve")
async def resolve_conflict(conflict_id: str, payload: Dict[str, Any], db: AsyncSession = Depends(get_db)) -> Dict[str, str]:
    """Resolves the conflict and updates truth state."""
    conflict = await db.get(Conflict, conflict_id)
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")

    status_val = payload.get("status", payload.get("decision", "RESOLVED"))
    
    try:
        status_enum = ConflictStatus(status_val)
        setattr(conflict, "status", status_enum)
    except Exception:
        setattr(conflict, "status", status_val)

    fact_a_id = getattr(conflict, "fact_a_id", None)
    if str(status_val).upper() == "RESOLVED_KEPT_B" and fact_a_id is not None:
        fact_a = await db.get(Fact, str(fact_a_id))
        if fact_a:
            setattr(fact_a, "is_active", False)

    await db.commit()
    return {"status": "success"}


@router.get("/document-text/{document_id}")
async def get_document_text(document_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, str]:
    """Reads and extracts clean text for a document from storage."""
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

    text_content = extract_document_text(valid_path)
    return {"text": text_content}
    """Reads and extracts text for a document from storage."""
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

    text_content = extract_clean_document_text(valid_path)
    return {"text": text_content}