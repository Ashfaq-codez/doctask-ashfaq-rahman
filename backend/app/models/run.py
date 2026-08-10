from sqlalchemy import Column, String, Float, DateTime, Enum
from sqlalchemy.sql import func
import enum
import uuid
from .base import Base

class RunStatus(str, enum.Enum):
    PENDING = "pending"
    CLASSIFYING = "classifying"
    EXTRACTING = "extracting"
    PAUSED_FOR_REVIEW = "paused_for_review"  # The human gate
    COMPLETED = "completed"
    FAILED = "failed"

class Run(Base):
    """
    Tracks the overarching execution of the agentic pipeline.
    This fulfills the requirement to track costs, latency, and status stage-by-stage.
    """
    __tablename__ = "runs"

    # We use UUIDs so that external systems (MCP/API) can reference runs securely
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    status = Column(Enum(RunStatus), default=RunStatus.PENDING, index=True)
    current_stage = Column(String, default="upload")

    # Metrics Tracking - crucial for the "knows what it cost" requirement
    total_cost = Column(Float, default=0.0)
    total_tokens = Column(Float, default=0.0)
    latency_seconds = Column(Float, default=0.0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())