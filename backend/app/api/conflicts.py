import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import aliased
from app.db import get_db
from app.models.conflict import Conflict, ConflictStatus
from app.models.fact import Fact
from app.models.document import Document

router = APIRouter()

@router.get("/pending")
async def get_pending_conflicts(db: AsyncSession = Depends(get_db)):
    """Fetches conflicts, their exact quotes, and the target document ID."""
    FactA = aliased(Fact)
    FactB = aliased(Fact)
    
    query = await db.execute(
        select(Conflict, FactA.paragraph_text, FactB.paragraph_text, FactB.document_id) # type: ignore
        .outerjoin(FactA, Conflict.fact_a_id == FactA.id)
        .outerjoin(FactB, Conflict.fact_b_id == FactB.id)
        .where(Conflict.status == ConflictStatus.PENDING_REVIEW.value)  # type: ignore
    )
    
    results = query.all()
    
    return [
        {
            "id": row[0].id,
            "run_id": row[0].run_id,
            "topic": row[0].topic,
            "ai_reasoning": row[0].ai_reasoning,
            "status": row[0].status,
            "fact_a_text": row[1] or "Historic context not found.",
            "fact_b_text": row[2] or "New context not found.",
            "document_id": row[3] 
        } for row in results
    ]

@router.post("/{conflict_id}/resolve")
async def resolve_conflict(conflict_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    """Resolves the conflict."""
    conflict = await db.get(Conflict, conflict_id)
    if conflict:
        conflict.status = payload.get("status") # type: ignore
        await db.commit()
    return {"status": "success"}

@router.get("/document-text/{document_id}")
async def get_document_text(document_id: str, db: AsyncSession = Depends(get_db)):
    """Reads the raw text from the server, hunting across possible path structures."""
    doc = await db.get(Document, document_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found in database.")
    
    file_path = getattr(doc, "storage_path", None)
    file_name = getattr(doc, "file_name", "")
    
    # We create a list of everywhere the file could possibly be based on where you run Uvicorn
    possible_paths = [
        file_path,
        os.path.join("storage", "uploads", file_name),
        os.path.join("backend", "storage", "uploads", file_name),
        os.path.join("..", "storage", "uploads", file_name)
    ]
    
    valid_path = None
    for path in possible_paths:
        if path and isinstance(path, str) and os.path.exists(path):
            valid_path = path
            break
            
    if not valid_path:
        # If it still fails, print the paths it tried to the terminal so we can debug it instantly
        print(f"❌ [API] Could not find {file_name}. Looked in: {possible_paths}")
        raise HTTPException(status_code=404, detail="Document file not found on the server disk.")
    
    try:
        with open(valid_path, "r", encoding="utf-8") as f:
            return {"text": f.read()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")
    """Reads the raw text using the correct storage_path column."""
    doc = await db.get(Document, document_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found in database.")
    
    # CRITICAL FIX: Using the actual column name from your schema
    file_path = getattr(doc, "storage_path", None)
    
    if not file_path:
        file_name = getattr(doc, "file_name", "")
        file_path = os.path.join("storage", "uploads", file_name)
        
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Document file not found on the server disk.")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return {"text": f.read()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")