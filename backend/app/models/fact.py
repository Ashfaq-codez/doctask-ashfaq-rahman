import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime

# Import Base from models.base
from app.models.base import Base

class Fact(Base):
    __tablename__ = "facts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, nullable=False)
    key = Column(String, nullable=False)
    value = Column(Text, nullable=False)
    paragraph_text = Column(Text, nullable=True)
    page_number = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)