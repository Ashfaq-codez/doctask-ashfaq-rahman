from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db
from app.models.fact import Fact

router = APIRouter()

@router.get("/")
async def get_recent_facts(db: AsyncSession = Depends(get_db)):
    """Fetches the most recently extracted facts from the database."""
    # Fetch all facts (in a production app, we would order by created_at and paginate)
    query = await db.execute(select(Fact).limit(50))
    facts = query.scalars().all()
    
    return [
        {
            "id": f.id,
            "document_id": f.document_id,
            "key": f.key,
            "value": f.value
        } for f in facts
    ]