from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db
from app.models.fact import Fact
from app.models.document import Document

# No prefix here — let main.py define the mounting prefix
router = APIRouter(tags=["facts"])

@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
async def get_recent_facts(db: AsyncSession = Depends(get_db)):
    """Fetches active verified facts and their parent document metadata."""
    try:
        query = (
            select(Fact, Document)
            .outerjoin(Document, Fact.document_id == Document.id)
            .where(Fact.is_active == True)
            .order_by(Fact.created_at.desc())
            .limit(50)
        )
        
        result = await db.execute(query)
        results = result.all()
        
        output = []
        for row in results:
            fact_obj: Fact = row[0]
            doc_obj = row[1]
            output.append({
                "id": str(fact_obj.id),
                "document_id": str(fact_obj.document_id),
                "document_name": getattr(doc_obj, "file_name", "Historical Record") if doc_obj else "Historical Record",
                "key": getattr(fact_obj, "key", "extracted_statement") or "extracted_statement",
                "value": getattr(fact_obj, "value", "No value recorded"),
                "paragraph_text": getattr(fact_obj, "paragraph_text", "") or "",
                "page_number": str(getattr(fact_obj, "page_number", "1") or "1")
            })
        return output
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))