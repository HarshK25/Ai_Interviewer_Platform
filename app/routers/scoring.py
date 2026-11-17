from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.score import Score, Scorecard
from app.models.answer import Answer
from app.models.question import Question
from app.models.interview_session import InterviewSession
from app.services.scoring_engine import scoring_engine
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scoring", tags=["Scoring"])


class ScoreAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    transcript: str
    job_role: Optional[str] = None  # fallback: looked up from session


@router.get("/session/{session_id}")
async def get_session_scores(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all scores for a specific session."""
    result = await db.execute(
        select(Score).where(Score.session_id == session_id)
    )
    scores = result.scalars().all()
    if not scores:
        raise HTTPException(404, "No scores found for this session")
    return scores


@router.get("/session/{session_id}/summary")
async def get_score_summary(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated score summary for a session."""
    result = await db.execute(
        select(
            func.avg(Score.accuracy_score).label("avg_accuracy"),
            func.avg(Score.clarity_score).label("avg_clarity"),
            func.avg(Score.depth_score).label("avg_depth"),
            func.avg(Score.relevance_score).label("avg_relevance"),
            func.avg(Score.overall_score).label("avg_overall"),
            func.count(Score.id).label("total_answers"),
        ).where(Score.session_id == session_id)
    )
    row = result.one()
    return {
        "session_id": session_id,
        "avg_accuracy": round(row.avg_accuracy or 0, 2),
        "avg_clarity": round(row.avg_clarity or 0, 2),
        "avg_depth": round(row.avg_depth or 0, 2),
        "avg_relevance": round(row.avg_relevance or 0, 2),
        "avg_overall": round(row.avg_overall or 0, 2),
        "total_answers": row.total_answers,
    }


# ─── REST Score-Answer (called by frontend interview page) ────────────────────
@router.post("/score-answer")
async def score_answer_rest(
    payload: ScoreAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Score a single transcribed answer via REST (used by the frontend interview
    room as a simpler alternative to the full WebSocket loop).

    Flow:
      1. Look up session → get job_role (and verify ownership)
      2. Look up question → get question text
      3. Create / upsert Answer row with the transcript
      4. Run LLM scoring engine
      5. Persist score → return score data to frontend
    """
    # 1. Verify session ownership
    session_result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == payload.session_id,
            InterviewSession.user_id == current_user.id,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    job_role = payload.job_role or session.job_role

    # 2. Look up question
    question_result = await db.execute(
        select(Question).where(Question.id == payload.question_id)
    )
    question = question_result.scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Question not found")

    # 3. Upsert Answer row (create if missing, update transcript if exists)
    answer_result = await db.execute(
        select(Answer).where(Answer.question_id == payload.question_id)
    )
    answer = answer_result.scalar_one_or_none()

    if answer is None:
        answer = Answer(
            question_id=question.id,
            session_id=session.id,
            transcript=payload.transcript,
            word_count=len(payload.transcript.split()),
        )
        db.add(answer)
        await db.flush()
    else:
        answer.transcript = payload.transcript
        answer.word_count = len(payload.transcript.split())
        await db.flush()

    # 4. Score with LLM
    try:
        score_data = await scoring_engine.score_answer(
            question=question.question_text,
            answer=payload.transcript,
            job_role=job_role,
        )
    except Exception as e:
        logger.error(f"Scoring error: {e}")
        score_data = {
            "accuracy_score": 0.0,
            "clarity_score": 0.0,
            "depth_score": 0.0,
            "relevance_score": 0.0,
            "overall_score": 0.0,
            "feedback": "Scoring unavailable — check LLM API key configuration.",
            "strengths": [],
            "improvements": [],
        }

    # 5. Persist or update Score row
    score_result = await db.execute(
        select(Score).where(Score.answer_id == answer.id)
    )
    existing_score = score_result.scalar_one_or_none()

    if existing_score is None:
        await scoring_engine.save_score(db, str(answer.id), str(session.id), score_data)
    else:
        existing_score.accuracy_score = score_data["accuracy_score"]
        existing_score.clarity_score = score_data["clarity_score"]
        existing_score.depth_score = score_data["depth_score"]
        existing_score.relevance_score = score_data["relevance_score"]
        existing_score.overall_score = score_data["overall_score"]
        existing_score.llm_feedback = score_data.get("feedback", "")
        existing_score.strengths = score_data.get("strengths", [])
        existing_score.improvements = score_data.get("improvements", [])
        existing_score.raw_llm_json = score_data

    await db.commit()

    return score_data
