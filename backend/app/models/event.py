from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Integer
from sqlalchemy.sql import func
import uuid
from .base import Base

class EventLog(Base):
    """
    An immutable ledger of every action the system takes.
    Answers: "what changed, when, and because of which source."
    """
    __tablename__ = "event_logs"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    
    # Which LangGraph node generated this event? (e.g., "classification", "extraction")
    node_name = Column(String, index=True, nullable=False)
    
    # Granular cost and performance tracking
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    latency_seconds = Column(Float, default=0.0)
    
    # Details of the event (can store JSON string of the exact prompt/response)
    event_details = Column(String, nullable=True)

    timestamp = Column(DateTime(timezone=True), server_default=func.now())