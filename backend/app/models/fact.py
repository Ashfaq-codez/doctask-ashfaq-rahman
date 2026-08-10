from sqlalchemy import Column, String, ForeignKey, Float, Text
import uuid
from .base import Base

class Fact(Base):
    """
    An individual piece of information extracted from a Document.
    This guarantees provenance: we know exactly where every claim comes from.
    """
    __tablename__ = "facts"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    
    # What did we extract?
    key = Column(String, index=True, nullable=False)   # e.g., "Start Date", "Total Amount"
    value = Column(Text, nullable=False)               # e.g., "October 1st, 2024", "$45,000"
    
    # Provenance - The exact location in the source
    page_number = Column(String, nullable=True)
    paragraph_text = Column(Text, nullable=True)
    
    # The LLM's confidence in this extraction (useful for flagging human review)
    confidence_score = Column(Float, nullable=True)