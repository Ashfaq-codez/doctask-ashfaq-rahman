import enum
import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Enum
from sqlalchemy.sql import func
from .base import Base

class DocumentStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    CLASSIFIED = "CLASSIFIED"
    EMBEDDED = "EMBEDDED"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    IGNORED_DUPLICATE = "IGNORED_DUPLICATE"

class Document(Base):
    """
    Represents a single file uploaded to the system.
    Tied to a specific Run to ensure concurrent runs do not corrupt state.
    """
    __tablename__ = "documents"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=True)  # e.g., 'application/pdf', 'text/plain'
    
    # SHA-256 hash to detect duplicate files across runs
    file_hash = Column(String, index=True, nullable=False) 
    
    status = Column(Enum(DocumentStatus), default=DocumentStatus.UPLOADED, index=True)
    
    # Store where the physical file lives (MinIO, local disk, S3)
    storage_path = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())