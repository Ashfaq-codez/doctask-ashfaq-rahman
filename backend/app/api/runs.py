from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.run import Run
from app.models.document import Document
from app.models.fact import Fact

router = APIRouter()

@router.get("/{run_id}")
async def get_run_status(run_id: str, db: AsyncSession = Depends(get_db)):
    """
    Fetches the current status of a Run, its associated Document, 
    and any Facts extracted by the AI so far.
    """
    # 1. Fetch the Run
    run_query = await db.execute(select(Run).where(Run.id == run_id))
    run = run_query.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    # 2. Fetch the Document attached to this Run
    doc_query = await db.execute(select(Document).where(Document.run_id == run_id))
    document = doc_query.scalar_one_or_none()
    
    # 3. Fetch Facts if the Document exists
    extracted_facts = []
    if document:
        facts_query = await db.execute(select(Fact).where(Fact.document_id == document.id))
        facts_records = facts_query.scalars().all()
        
        extracted_facts = [
            {
                "id": fact.id,
                "key": fact.key,
                "value": fact.value
            } for fact in facts_records
        ]
        
    # 4. Construct the unified response payload
    return {
        "run_id": run.id,
        "status": run.status,
        "current_stage": run.current_stage,
        "document": {
            "id": document.id if document else None,
            "file_name": document.file_name if document else None,
            "status": document.status if document else None,
        },
        "extracted_facts": extracted_facts
    }