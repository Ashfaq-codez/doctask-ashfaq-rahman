import json
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.conflict import Conflict
from app.models.document import Document
from app.models.fact import Fact
from app.models.run import Run

router = APIRouter(tags=["runs"])


@router.get("/latest", response_model=Dict[str, Any])
async def get_latest_run_telemetry(db: AsyncSession = Depends(get_db)):
    """Fetches real-time telemetry, stage progression, and cost metrics for the most recent run."""
    try:
        query = await db.execute(select(Run).order_by(Run.created_at.desc()).limit(1))
        latest_run = query.scalar_one_or_none()

        if not latest_run:
            return {
                "id": None,
                "status": "IDLE",
                "current_stage": "ready",
                "total_cost": 0.0,
                "total_tokens": 0.0,
            }

        return {
            "id": str(latest_run.id),
            "status": str(
                latest_run.status.value
                if hasattr(latest_run.status, "value")
                else latest_run.status
            ),
            "current_stage": getattr(latest_run, "current_stage", "completed")
            or "completed",
            "total_cost": float(getattr(latest_run, "total_cost", 0.0) or 0.0),
            "total_tokens": float(getattr(latest_run, "total_tokens", 0.0) or 0.0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/export")
async def export_final_report(
    format: str = Query("md", enum=["md", "txt", "json"]),
    db: AsyncSession = Depends(get_db),
):
    """
    Exports the finalized audit report containing active ground truth facts 
    and human-verified overrides as a downloadable document (.md, .txt, or .json).
    """
    try:
        query_run = await db.execute(select(Run).order_by(Run.created_at.desc()).limit(1))
        latest_run = query_run.scalar_one_or_none()

        query_facts = await db.execute(
            select(Fact).where(Fact.is_active == True)  # type: ignore[arg-type]
        )
        active_facts = query_facts.scalars().all()

        query_conflicts = await db.execute(
            select(Conflict).order_by(Conflict.created_at.desc())  # type: ignore[attr-defined]
        )
        all_conflicts = query_conflicts.scalars().all()

        timestamp_str = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")

        # 1. JSON Format Export
        if format == "json":
            payload = {
                "report_metadata": {
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                    "run_id": str(latest_run.id) if latest_run else None,
                    "status": str(latest_run.status.value if latest_run and hasattr(latest_run.status, "value") else "COMPLETED"),
                    "total_cost_usd": float(getattr(latest_run, "total_cost", 0.0) or 0.0),
                    "total_tokens": float(getattr(latest_run, "total_tokens", 0.0) or 0.0),
                },
                "verified_active_facts": [
                    {
                        "id": str(f.id),
                        "statement": f.value,
                        "category": f.key,
                        "citation_page": f.page_number,
                        "exact_quote": f.paragraph_text,
                    }
                    for f in active_facts
                ],
                "resolution_audit_log": [
                    {
                        "conflict_id": str(c.id),
                        "topic": c.topic,
                        "status": str(c.status.value if hasattr(c.status, "value") else c.status),
                        "ai_reasoning": c.ai_reasoning,
                    }
                    for c in all_conflicts
                ],
            }
            content_bytes = json.dumps(payload, indent=2).encode("utf-8")
            filename = f"final_audit_report_{timestamp_str}.json"
            return Response(
                content=content_bytes,
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        # 2. Markdown / Plain Text Format Export
        report_lines = [
            "==================================================================",
            "                   DOCTASK FINAL AUDIT REPORT                     ",
            "==================================================================",
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Run Reference: {latest_run.id if latest_run else 'N/A'}",
            f"Audit Status: {latest_run.status.value if latest_run and hasattr(latest_run.status, 'value') else 'COMPLETED'}",
            f"Execution Spend: ${getattr(latest_run, 'total_cost', 0.0):.4f} USD | Tokens Processed: {getattr(latest_run, 'total_tokens', 0.0):,.0f}",
            "==================================================================",
            "",
            "1. FINAL GROUND TRUTH KNOWLEDGE STORE (VERIFIED ACTIVE FACTS)",
            "------------------------------------------------------------------",
        ]

        if not active_facts:
            report_lines.append("No active verified facts recorded in knowledge base.")
        else:
            for idx, fact in enumerate(active_facts, 1):
                report_lines.extend([
                    f"[{idx}] {fact.value}",
                    f"    - Category: {fact.key}",
                    f"    - Provenance: Page {fact.page_number}",
                    f"    - Source Quote: \"{fact.paragraph_text}\"",
                    "",
                ])

        report_lines.extend([
            "------------------------------------------------------------------",
            "2. HUMAN REVIEW RESOLUTIONS & DECISION AUDIT TRAIL",
            "------------------------------------------------------------------",
        ])

        if not all_conflicts:
            report_lines.append("No conflicts or cross-document anomalies encountered.")
        else:
            for c_idx, conf in enumerate(all_conflicts, 1):
                status_str = conf.status.value if hasattr(conf.status, "value") else str(conf.status)
                report_lines.extend([
                    f"[{c_idx}] Topic: {conf.topic}",
                    f"    - Decision: {status_str}",
                    f"    - Reasoning: {conf.ai_reasoning}",
                    "",
                ])

        report_lines.append("========================== END OF REPORT ==========================")

        file_ext = "md" if format == "md" else "txt"
        filename = f"final_audit_report_{timestamp_str}.{file_ext}"
        content_text = "\n".join(report_lines)

        return Response(
            content=content_text.encode("utf-8"),
            media_type="text/markdown" if format == "md" else "text/plain",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/{run_id}")
async def get_run_status(run_id: str, db: AsyncSession = Depends(get_db)):
    """Fetches the status of a specific Run, its Document, and extracted Facts."""
    run_query = await db.execute(select(Run).where(Run.id == run_id))  # type: ignore[arg-type]
    run = run_query.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    doc_query = await db.execute(select(Document).where(Document.run_id == run_id))  # type: ignore[arg-type]
    document = doc_query.scalar_one_or_none()

    extracted_facts = []
    if document:
        facts_query = await db.execute(select(Fact).where(Fact.document_id == document.id))  # type: ignore[arg-type]
        facts_records = facts_query.scalars().all()

        extracted_facts = [
            {
                "id": str(fact.id),
                "key": getattr(fact, "key", "extracted_statement"),
                "value": fact.value,
                "exact_quote": getattr(fact, "paragraph_text", "") or "",
                "page_number": str(getattr(fact, "page_number", "1") or "1"),
            }
            for fact in facts_records
        ]

    return {
        "run_id": str(run.id),
        "status": str(
            run.status.value if hasattr(run.status, "value") else run.status
        ),
        "current_stage": run.current_stage,
        "total_cost": float(getattr(run, "total_cost", 0.0) or 0.0),
        "total_tokens": float(getattr(run, "total_tokens", 0.0) or 0.0),
        "document": {
            "id": str(document.id) if document else None,
            "file_name": document.file_name if document else None,
            "status": str(
                document.status.value
                if hasattr(document.status, "value")
                else document.status
            )
            if document
            else None,
        },
        "extracted_facts": extracted_facts,
    }