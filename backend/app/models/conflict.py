from sqlalchemy import Column, String, ForeignKey, Enum, Text
from sqlalchemy.sql import func
from sqlalchemy import DateTime
import enum
import uuid
from .base import Base

class ConflictStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review" # Waiting for the human gate
    RESOLVED_KEPT_A = "resolved_kept_a"
    RESOLVED_KEPT_B = "resolved_kept_b"
    RESOLVED_MANUAL_EDIT = "resolved_manual_edit"

class Conflict(Base):
    """
    Represents a disagreement between two documents or a new document and the existing state.
    """
    __tablename__ = "conflicts"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    
    # What is the topic of disagreement? (e.g., "Contract End Date")
    topic = Column(String, nullable=False)
    
    # The conflicting data points
    fact_a_id = Column(String, ForeignKey("facts.id"), nullable=True)
    fact_b_id = Column(String, ForeignKey("facts.id"), nullable=True)
    
    # Why the AI thinks they conflict (e.g., "Doc A says Oct 1, Doc B says Nov 1")
    ai_reasoning = Column(Text, nullable=False)
    
    status = Column(Enum(ConflictStatus), default=ConflictStatus.PENDING_REVIEW, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)