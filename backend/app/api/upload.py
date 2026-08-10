import os
import hashlib
from app.worker import process_document_task
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.models.run import Run, RunStatus
from app.models.document import Document, DocumentStatus

router = APIRouter()

STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "storage", "uploads")
os.makedirs(STORAGE_DIR, exist_ok=True)

async def calculate_hash(file_bytes: bytes) -> str:
    """Calculate SHA-256 hash to detect duplicate files for incremental updates."""
    return hashlib.sha256(file_bytes).hexdigest()

@router.post("/")
async def upload_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """
    Accepts a document, creates a new Run, and tracks the Document.
    This fulfills the requirement that every upload starts a traceable Run.
    """
    try:
        # Read the file and calculate its hash
        file_bytes = await file.read()
        file_hash = await calculate_hash(file_bytes)
        
        # FIX: Provide a safe fallback if the client omits the filename
        safe_filename = file.filename or f"unnamed_upload_{file_hash[:8]}.bin"
        
        # Save the physical file safely
        file_path = os.path.join(STORAGE_DIR, safe_filename)
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        # 1. Initialize a new Run
        new_run = Run(status=RunStatus.PENDING, current_stage="upload")
        db.add(new_run)
        await db.commit()
        await db.refresh(new_run)

        # 2. Register the Document under this Run
        new_doc = Document(
            run_id=new_run.id,
            file_name=safe_filename,  # Use the safe filename here too
            file_type=file.content_type,
            file_hash=file_hash,
            storage_path=file_path,
            status=DocumentStatus.UPLOADED
        )
        db.add(new_doc)
        await db.commit()

        # TODO: Trigger the Celery worker / LangGraph orchestrator here
        # Trigger the Celery worker in the background
        process_document_task.delay(  # type: ignore
            run_id=str(new_run.id),
            document_id=str(new_doc.id),
            file_path=file_path
        )

        return {
            "message": "Document uploaded and Run initialized successfully.",
            "run_id": new_run.id,
            "document_id": new_doc.id
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    """
    Accepts a document, creates a new Run, and tracks the Document.
    This fulfills the requirement that every upload starts a traceable Run.
    """
    try:
        # Read the file and calculate its hash
        file_bytes = await file.read()
        file_hash = await calculate_hash(file_bytes)
        
        # Save the physical file
        file_path = os.path.join(STORAGE_DIR, file.filename)
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        # 1. Initialize a new Run
        new_run = Run(status=RunStatus.PENDING, current_stage="upload")
        db.add(new_run)
        await db.commit()
        await db.refresh(new_run)

        # 2. Register the Document under this Run
        new_doc = Document(
            run_id=new_run.id,
            file_name=file.filename,
            file_type=file.content_type,
            file_hash=file_hash,
            storage_path=file_path,
            status=DocumentStatus.UPLOADED
        )
        db.add(new_doc)
        await db.commit()

        # TODO: Here is where we will trigger the Celery worker / LangGraph orchestrator

        return {
            "message": "Document uploaded and Run initialized successfully.",
            "run_id": new_run.id,
            "document_id": new_doc.id
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")