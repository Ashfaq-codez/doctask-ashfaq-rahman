import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import all of our active routers exactly once
from app.api import upload, runs, conflicts, facts

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Define Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SuperDocs Agentic Backend...")
    yield
    logger.info("Shutting down SuperDocs Agentic Backend cleanly...")

# 1. Initialize FastAPI (Exactly ONCE)
app = FastAPI(
    title="SuperDocs Agentic System API",
    description="A robust, human-gated AI distributed system for document analysis.",
    version="1.0.0",
    lifespan=lifespan
)

# 2. Setup CORS for the React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Register all API Routers
app.include_router(upload.router, prefix="/api/v1/upload", tags=["Upload"])
app.include_router(runs.router, prefix="/api/v1/runs", tags=["Runs"])
app.include_router(conflicts.router, prefix="/api/v1/conflicts", tags=["Conflicts"])
app.include_router(facts.router, prefix="/api/v1/facts", tags=["Facts"])

# 4. Health Check Endpoint
@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "healthy", "service": "SuperDocs Agent API"}