from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import logging
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.interview_session import InterviewSession
from app.models.resume import Resume
from app.services.question_generator import question_generator
from app.services.voice_engine import voice_engine
from app.models.question import Question
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interview", tags=["Interview"])


class CreateSessionRequest(BaseModel):
    resume_id: Optional[str] = None
    job_role: str
    job_description: Optional[str] = ""
    total_questions: Optional[int] = 5


@router.post("/sessions")
async def create_session(
    payload: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an interview session and pre-generate all questions."""
    try:
        # Verify resume belongs to user (optional — sessions can run without a resume)
        resume = None
        if payload.resume_id:
            resume_result = await db.execute(
                select(Resume).where(Resume.id == payload.resume_id, Resume.user_id == current_user.id)
            )
            resume = resume_result.scalar_one_or_none()
            if not resume:
                raise HTTPException(404, "Resume not found")

        # Create session
        session = InterviewSession(
            user_id=current_user.id,
            resume_id=payload.resume_id,
            job_role=payload.job_role,
            job_description=payload.job_description,
            total_questions=payload.total_questions,
            status="pending",
        )
        db.add(session)
        await db.flush()  # get session.id before generating questions

        # Generate questions via RAG + LLM
        try:
            generated_questions = await question_generator.generate_session_questions(
                session_id=str(session.id),
                user_id=str(current_user.id),
                job_role=payload.job_role,
                job_description=payload.job_description or "",
                num_questions=payload.total_questions,
            )
        except Exception as llm_err:
            logger.error(f"LLM question generation failed: {llm_err}", exc_info=True)
            raise HTTPException(
                status_code=503,
                detail=f"LLM question generation failed: {str(llm_err)}"
            )

        # Save questions (TTS audio skipped — generated on-demand)
        for i, q_data in enumerate(generated_questions):
            audio_key = None
            try:
                audio_key = await voice_engine.synthesize_speech(
                    text=q_data["question_text"],
                    session_id=str(session.id),
                    q_num=i + 1,
                )
            except Exception as e:
                logger.warning(f"TTS synthesis skipped for q{i+1}: {e}")

            question = Question(
                session_id=session.id,
                sequence_num=i + 1,
                question_text=q_data["question_text"],
                question_type=q_data.get("question_type", "general"),
                difficulty=q_data.get("difficulty", "medium"),
                target_skills=q_data.get("target_skills", []),
                source="rag_generated",
                audio_s3_key=audio_key,
            )
            db.add(question)

        await db.commit()
        await db.refresh(session)

        return {
            "session_id": str(session.id),
            "status": session.status,
            "job_role": session.job_role,
            "total_questions": session.total_questions,
            "message": "Session created. Questions ready. Connect via WebSocket to start.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_session failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Session creation error: {str(e)}")


@router.post("/sessions/{session_id}/start")
async def start_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark session as active (called just before WebSocket connection)."""
    import uuid as _uuid
    # Explicit UUID cast to avoid string vs UUID type mismatch in asyncpg
    try:
        sid = _uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(400, "Invalid session_id format")

    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == sid,
            InterviewSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    logger.info(f"start_session: sid={sid} user={current_user.id} found={session is not None}")
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status != "pending":
        raise HTTPException(400, f"Session is already {session.status}")

    session.status = "active"
    session.started_at = datetime.now(timezone.utc)
    await db.commit()
    return {"session_id": session_id, "status": "active"}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@router.get("/sessions/{session_id}/questions")
async def get_session_questions(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Question)
        .where(Question.session_id == session_id)
        .order_by(Question.sequence_num)
    )
    return result.scalars().all()


@router.patch("/sessions/{session_id}/abort")
async def abort_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    session.status = "aborted"
    await db.commit()
    return {"message": "Session aborted"}


@router.post("/sessions/{session_id}/complete")
async def complete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a session as completed and trigger background scorecard generation.
    Called by the frontend after the last answer is submitted in REST mode.
    """
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    if session.status == "completed":
        return {"session_id": session_id, "status": "completed", "message": "Already completed"}

    if session.status == "aborted":
        raise HTTPException(400, "Cannot complete an aborted session")

    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    await db.commit()

    # Trigger background scorecard PDF generation
    try:
        from app.tasks.pdf_tasks import generate_scorecard_task
        generate_scorecard_task.delay(session_id)
    except Exception as e:
        # Celery may not be running in dev — log and continue
        import logging
        logging.getLogger(__name__).warning(f"Celery task dispatch failed (scorecard will not be generated automatically): {e}")

    return {
        "session_id": session_id,
        "status": "completed",
        "message": "Session marked complete. Scorecard generation triggered.",
    }
