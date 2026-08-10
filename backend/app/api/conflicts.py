from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, timezone

from app.db import get_db
from app.models.conflict import Conflict, ConflictStatus

router = APIRouter()

# 1. Define the exact payload we expect from the human reviewer
class ConflictResolution(BaseModel):
    status: ConflictStatus

@router.get("/pending")
async def get_pending_conflicts(db: AsyncSession = Depends(get_db)):
    """Fetches all conflicts and anomalies currently awaiting human review."""
    
    # FIX: Use string comparison or explicit value comparison to bypass Pylance's boolean evaluation check
    query = await db.execute(
        select(Conflict).where(Conflict.status == ConflictStatus.PENDING_REVIEW.value)  # type: ignore
    )
    conflicts = query.scalars().all()
    
    return [
        {
            "id": c.id,
            "run_id": c.run_id,
            "topic": c.topic,
            "ai_reasoning": c.ai_reasoning,
            "status": c.status,
            "created_at": c.created_at
        } for c in conflicts
    ]

@router.post("/{conflict_id}/resolve")
async def resolve_conflict(conflict_id: str, resolution: ConflictResolution, db: AsyncSession = Depends(get_db)):
    """Applies the human operator's decision and marks the conflict as resolved."""
    
    # 1. Fetch the exact conflict
    conflict = await db.get(Conflict, conflict_id)
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")
        
    if conflict.status != ConflictStatus.PENDING_REVIEW.value:  # type: ignore
        raise HTTPException(status_code=400, detail="Conflict is already resolved")

    # 2. Apply the human decision (using type: ignore for Pylance/SQLAlchemy compatibility)
    conflict.status = resolution.status                     # type: ignore
    conflict.resolved_at = datetime.now(timezone.utc)       # type: ignore
    
    # 3. Save the resolution
    await db.commit()
    
    return {
        "message": "Conflict resolved successfully",
        "conflict_id": conflict.id,
        "new_status": conflict.status
    }