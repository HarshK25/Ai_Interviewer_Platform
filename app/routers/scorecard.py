from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.score import Scorecard
from app.utils.file_storage import storage
import io

router = APIRouter(prefix="/scorecard", tags=["Scorecard"])


@router.get("/{session_id}")
async def get_scorecard(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get scorecard data for a completed session."""
    result = await db.execute(
        select(Scorecard).where(Scorecard.session_id == session_id)
    )
    scorecard = result.scalar_one_or_none()
    if not scorecard:
        raise HTTPException(404, "Scorecard not ready yet. The session may still be processing.")
    return scorecard


@router.get("/{session_id}/pdf")
async def download_scorecard_pdf(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download the PDF scorecard for a completed session."""
    result = await db.execute(
        select(Scorecard).where(Scorecard.session_id == session_id)
    )
    scorecard = result.scalar_one_or_none()
    if not scorecard or not scorecard.pdf_s3_key:
        raise HTTPException(404, "PDF not yet generated")

    pdf_bytes = await storage.download(scorecard.pdf_s3_key)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=scorecard_{session_id}.pdf"},
    )
