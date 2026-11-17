import json
import re
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.llm.llm_client import llm
from app.llm.prompt_templates import SCORING_PROMPT
from app.models.score import Score

logger = logging.getLogger(__name__)


class ScoringEngine:

    async def score_answer(
        self,
        question: str,
        answer: str,
        job_role: str,
        context: str = "",
    ) -> dict:
        """
        Score an interview answer using LLM with a structured rubric.
        Returns validated dict with all score dimensions + feedback.
        """
        if not answer or len(answer.strip()) < 10:
            return self._empty_score("Answer was too short or empty")

        prompt = SCORING_PROMPT.format(
            job_role=job_role,
            question=question,
            answer=answer[:3000],
            context=context[:500],
        )

        try:
            response = await llm.ainvoke(prompt)
            raw_text = response.content

            # Extract JSON from response (LLM may wrap in markdown)
            json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in LLM response")

            score_data = json.loads(json_match.group())
            return self._validate_score(score_data)

        except Exception as e:
            logger.error(f"Scoring failed: {e}")
            return self._empty_score(f"Scoring error: {str(e)}")

    def _validate_score(self, data: dict) -> dict:
        """Clamp all scores to 0-10 and ensure required fields exist."""
        score_fields = ["accuracy_score", "clarity_score", "depth_score", "relevance_score", "overall_score"]
        for field in score_fields:
            if field not in data:
                data[field] = 5.0
            else:
                data[field] = round(max(0.0, min(10.0, float(data[field]))), 1)

        # Recalculate weighted overall
        data["overall_score"] = round(
            data["accuracy_score"] * 0.30 +
            data["clarity_score"] * 0.25 +
            data["depth_score"] * 0.25 +
            data["relevance_score"] * 0.20,
            1,
        )

        data.setdefault("feedback", "No feedback provided.")
        data.setdefault("strengths", [])
        data.setdefault("improvements", [])
        data.setdefault("suggested_followup", None)
        return data

    def _empty_score(self, reason: str) -> dict:
        return {
            "accuracy_score": 0.0,
            "clarity_score": 0.0,
            "depth_score": 0.0,
            "relevance_score": 0.0,
            "overall_score": 0.0,
            "feedback": reason,
            "strengths": [],
            "improvements": ["Could not evaluate answer"],
            "suggested_followup": None,
        }

    async def save_score(
        self,
        db: AsyncSession,
        answer_id: str,
        session_id: str,
        score_data: dict,
    ) -> Score:
        """Persist score to PostgreSQL."""
        score = Score(
            answer_id=answer_id,
            session_id=session_id,
            accuracy_score=score_data["accuracy_score"],
            clarity_score=score_data["clarity_score"],
            depth_score=score_data["depth_score"],
            relevance_score=score_data["relevance_score"],
            overall_score=score_data["overall_score"],
            llm_feedback=score_data["feedback"],
            strengths=score_data.get("strengths", []),
            improvements=score_data.get("improvements", []),
            raw_llm_json=score_data,
        )
        db.add(score)
        await db.flush()
        return score


scoring_engine = ScoringEngine()
