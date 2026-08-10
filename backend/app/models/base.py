from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

class Base(AsyncAttrs, DeclarativeBase):
    """
    The foundational class for all SQLAlchemy models.
    Inheriting from AsyncAttrs ensures safe asynchronous lazy-loading of relationships.
    """
    pass