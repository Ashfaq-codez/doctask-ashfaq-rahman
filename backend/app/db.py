import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

DATABASE_URL = os.environ.get("DATABASE_URL")

# FIX 1: Explicitly check for None to satisfy Pylance and prevent runtime crashes
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is missing.")

# Create the async engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Create a session factory
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# FIX 2: Correct the type hint to AsyncGenerator
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to yield database sessions for FastAPI routes.
    Ensures sessions are closed cleanly after each request.
    """
    async with AsyncSessionLocal() as session:
        yield session