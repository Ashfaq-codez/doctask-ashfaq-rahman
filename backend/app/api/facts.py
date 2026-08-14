from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db
from app.models.fact import Fact
from app.models.document import Document

router = APIRouter()

@router.get("/")
async def get_recent_facts(db: AsyncSession = Depends(get_db)):
    """Fetches facts and their documents using the correct schema columns."""
    
    query = await db.execute(
        select(Fact, Document)
        .join(Document, Fact.document_id == Document.id)
        .limit(50)
    )
    
    results = query.all()
    
    return [
        {
            "id": row[0].id,
            "document_id": row[0].document_id,
            # CRITICAL FIX: Mapping directly to your actual column name
            "document_name": getattr(row[1], "file_name", "Historical Record"),
            "key": getattr(row[0], "key", "extracted_statement") or "extracted_statement",
            "value": getattr(row[0], "value", "No value recorded"),
            "paragraph_text": getattr(row[0], "paragraph_text", ""),
            "page_number": getattr(row[0], "page_number", "1")
        } for row in results
    ]