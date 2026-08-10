from sqlalchemy import Column, String, ForeignKey, Enum, Text, DateTime
from sqlalchemy.sql import func
import enum
import uuid
from .base import Base

class ReviewDecision(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"

class ReviewItem(Base):
    """
    Individual items waiting for human approval. 
    Allows granular item-by-item approval without discarding the rest of the batch.
    """
    __tablename__ = "review_items"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    
    # What type of item is the human reviewing? (e.g., "extraction", "conflict", "compliance_finding")
    item_type = Column(String, index=True, nullable=False)
    
    # A reference to the specific record (e.g., a Fact ID or Conflict ID)
    reference_id = Column(String, nullable=False)
    
    # What the AI proposes to do
    proposed_action = Column(Text, nullable=False)
    
    # The human's final call
    decision = Column(Enum(ReviewDecision), nullable=True)
    human_comments = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)