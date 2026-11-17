import io
import logging
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import AsyncSessionLocal
from app.models.interview_session import InterviewSession
from app.models.score import Score, Scorecard
from app.llm.llm_client import llm
from app.llm.prompt_templates import SESSION_SUMMARY_PROMPT
from app.utils.file_storage import storage

logger = logging.getLogger(__name__)

RECOMMENDATION_COLORS = {
    "strong_hire": colors.HexColor("#16a34a"),
    "hire": colors.HexColor("#2563eb"),
    "borderline": colors.HexColor("#d97706"),
    "no_hire": colors.HexColor("#dc2626"),
}


class ScorecardService:

    async def generate_scorecard(self, session_id: str) -> str:
        """
        Main entry point: fetch data → generate PDF → upload → save to DB.
        Returns S3 key of the generated PDF.
        """
        async with AsyncSessionLocal() as db:
            # Fetch session with user and scores
            session_result = await db.execute(
                select(InterviewSession)
                .where(InterviewSession.id == session_id)
                .options(selectinload(InterviewSession.user))
                .options(selectinload(InterviewSession.scores))
            )
            session = session_result.scalar_one_or_none()
            if not session:
                raise ValueError(f"Session {session_id} not found")

            scores = session.scores
            if not scores:
                raise ValueError(f"No scores found for session {session_id}")

            # Compute aggregates
            metrics = self._compute_metrics(scores)

            # LLM session summary
            qa_summary = self._build_qa_summary(session)
            summary_prompt = SESSION_SUMMARY_PROMPT.format(
                candidate_name=session.user.full_name,
                job_role=session.job_role,
                qa_summary=qa_summary,
                **metrics,
            )
            summary_response = await llm.ainvoke(summary_prompt)
            session_summary = summary_response.content.strip()

            # Recommendation
            recommendation = self._compute_recommendation(metrics["avg_overall"])

            # Build PDF
            pdf_bytes = self._build_pdf(session, scores, metrics, session_summary, recommendation)

            # Upload PDF
            s3_key = f"scorecards/{session_id}/scorecard.pdf"
            await storage.upload(pdf_bytes, s3_key, content_type="application/pdf")

            # Collect strengths/improvements across all scores
            all_strengths = []
            all_improvements = []
            for s in scores:
                all_strengths.extend(s.strengths or [])
                all_improvements.extend(s.improvements or [])

            # Save Scorecard to DB
            scorecard = Scorecard(
                session_id=session_id,
                avg_accuracy=metrics["avg_accuracy"],
                avg_clarity=metrics["avg_clarity"],
                avg_depth=metrics["avg_depth"],
                avg_relevance=metrics["avg_relevance"],
                overall_score=metrics["avg_overall"],
                strengths=list(set(all_strengths))[:5],
                improvements=list(set(all_improvements))[:5],
                session_summary=session_summary,
                recommendation=recommendation,
                pdf_s3_key=s3_key,
            )
            db.add(scorecard)
            await db.commit()

        logger.info(f"Scorecard generated for session {session_id}")
        return s3_key

    def _compute_metrics(self, scores: list) -> dict:
        n = len(scores)
        return {
            "avg_accuracy": round(sum(s.accuracy_score or 0 for s in scores) / n, 2),
            "avg_clarity": round(sum(s.clarity_score or 0 for s in scores) / n, 2),
            "avg_depth": round(sum(s.depth_score or 0 for s in scores) / n, 2),
            "avg_relevance": round(sum(s.relevance_score or 0 for s in scores) / n, 2),
            "avg_overall": round(sum(s.overall_score or 0 for s in scores) / n, 2),
        }

    def _compute_recommendation(self, overall: float) -> str:
        if overall >= 8.5: return "strong_hire"
        if overall >= 7.0: return "hire"
        if overall >= 5.5: return "borderline"
        return "no_hire"

    def _build_qa_summary(self, session) -> str:
        lines = []
        for q in sorted(session.questions, key=lambda x: x.sequence_num)[:5]:
            if q.answer and q.answer.transcript:
                lines.append(f"Q{q.sequence_num}: {q.question_text}\nA: {q.answer.transcript[:300]}")
        return "\n\n".join(lines) or "No Q&A data available"

    def _build_pdf(self, session, scores, metrics, summary, recommendation) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            topMargin=0.75 * inch, bottomMargin=0.75 * inch,
            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        )
        styles = getSampleStyleSheet()
        story = []

        # ── Header ────────────────────────────────────────────────────────────
        title_style = ParagraphStyle("title", fontSize=22, alignment=TA_CENTER,
                                      textColor=colors.HexColor("#1e1b4b"), spaceAfter=6)
        subtitle_style = ParagraphStyle("subtitle", fontSize=12, alignment=TA_CENTER,
                                         textColor=colors.HexColor("#6b7280"), spaceAfter=20)

        story.append(Paragraph("🤖 AI Interview Scorecard", title_style))
        story.append(Paragraph(f"{session.job_role} — {session.user.full_name}", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#4f46e5")))
        story.append(Spacer(1, 16))

        # ── Recommendation Badge ───────────────────────────────────────────────
        rec_color = RECOMMENDATION_COLORS.get(recommendation, colors.grey)
        rec_style = ParagraphStyle("rec", fontSize=16, alignment=TA_CENTER,
                                    textColor=colors.white, backColor=rec_color,
                                    borderPadding=8, spaceAfter=20)
        story.append(Paragraph(f"Recommendation: {recommendation.upper().replace('_', ' ')}", rec_style))

        # ── Score Table ────────────────────────────────────────────────────────
        score_data = [
            ["Dimension", "Score (/10)", "Rating"],
            ["Accuracy",  f"{metrics['avg_accuracy']:.1f}", self._rating(metrics['avg_accuracy'])],
            ["Clarity",   f"{metrics['avg_clarity']:.1f}",  self._rating(metrics['avg_clarity'])],
            ["Depth",     f"{metrics['avg_depth']:.1f}",    self._rating(metrics['avg_depth'])],
            ["Relevance", f"{metrics['avg_relevance']:.1f}", self._rating(metrics['avg_relevance'])],
            ["OVERALL",   f"{metrics['avg_overall']:.1f}",  self._rating(metrics['avg_overall'])],
        ]
        table = Table(score_data, colWidths=[2.5 * inch, 1.5 * inch, 1.5 * inch])
        table.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, 0), 11),
            ("BACKGROUND",  (0, -1), (-1, -1), colors.HexColor("#e0e7ff")),
            ("FONTNAME",    (0, -1), (-1, -1), "Helvetica-Bold"),
            ("ALIGN",       (1, 0), (-1, -1), "CENTER"),
            ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#c7d2fe")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f5f3ff")]),
            ("TOPPADDING",  (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(table)
        story.append(Spacer(1, 20))

        # ── Assessment Summary ─────────────────────────────────────────────────
        story.append(Paragraph("Assessment Summary", ParagraphStyle("h2", fontSize=14,
                                textColor=colors.HexColor("#1e1b4b"), spaceAfter=8,
                                fontName="Helvetica-Bold")))
        story.append(Paragraph(summary, styles["Normal"]))
        story.append(Spacer(1, 20))

        # ── Footer ────────────────────────────────────────────────────────────
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))
        footer_style = ParagraphStyle("footer", fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
        story.append(Paragraph("Generated by AI Interviewer Platform • Confidential", footer_style))

        doc.build(story)
        return buf.getvalue()

    def _rating(self, score: float) -> str:
        if score >= 8.5: return "⭐ Excellent"
        if score >= 7.0: return "👍 Good"
        if score >= 5.5: return "📈 Average"
        return "⚠️ Needs Work"


scorecard_service = ScorecardService()
