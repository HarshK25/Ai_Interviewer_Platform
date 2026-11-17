from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.interview_session import InterviewSession
from app.models.score import Score, Scorecard

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate stats for the logged-in candidate."""
    # Total completed sessions
    sessions_result = await db.execute(
        select(func.count()).where(
            InterviewSession.user_id == current_user.id,
            InterviewSession.status == "completed",
        )
    )
    total_completed = sessions_result.scalar() or 0

    # Average overall score — aggregate from Score table (per-answer scores)
    avg_result = await db.execute(
        select(func.avg(Score.overall_score))
        .join(InterviewSession, Score.session_id == InterviewSession.id)
        .where(
            InterviewSession.user_id == current_user.id,
            Score.overall_score > 0,  # exclude empty/failed scores
        )
    )
    avg_score = avg_result.scalar()
    avg_score = round(float(avg_score), 2) if avg_score else None

    # Best session score — max average score per session
    best_result = await db.execute(
        select(func.max(Score.overall_score))
        .join(InterviewSession, Score.session_id == InterviewSession.id)
        .where(
            InterviewSession.user_id == current_user.id,
            Score.overall_score > 0,
        )
    )
    best_score = best_result.scalar()
    best_score = round(float(best_score), 2) if best_score else None

    # Hire recommendations — from Scorecard if available, else derive from avg score
    hire_result = await db.execute(
        select(func.count())
        .select_from(Scorecard)
        .join(InterviewSession, Scorecard.session_id == InterviewSession.id)
        .where(
            InterviewSession.user_id == current_user.id,
            Scorecard.recommendation.in_(["hire", "strong_hire"]),
        )
    )
    hire_count = hire_result.scalar() or 0

    return {
        "total_completed_sessions": total_completed,
        "average_overall_score": avg_score,
        "best_score": best_score,
        "hire_recommendations": hire_count,
    }


@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 10,
    offset: int = 0,
):
    """Paginated list of the user's interview sessions."""
    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.user_id == current_user.id)
        .order_by(InterviewSession.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    sessions = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "job_role": s.job_role,
            "status": s.status,
            "total_questions": s.total_questions,
            "started_at": s.started_at,
            "completed_at": s.completed_at,
            "created_at": s.created_at,
        }
        for s in sessions
    ]
