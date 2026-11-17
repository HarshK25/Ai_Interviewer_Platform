import logging
from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:

    async def send_scorecard_from_session(self, session_id: str, pdf_s3_key: str):
        """Fetch session data and send scorecard email to candidate."""
        from app.database import AsyncSessionLocal
        from app.models.interview_session import InterviewSession
        from app.models.score import Scorecard
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(InterviewSession)
                .where(InterviewSession.id == session_id)
                .options(selectinload(InterviewSession.user))
            )
            session = result.scalar_one_or_none()

            sc_result = await db.execute(
                select(Scorecard).where(Scorecard.session_id == session_id)
            )
            scorecard = sc_result.scalar_one_or_none()

            if not session or not scorecard:
                logger.error(f"Cannot send email: session or scorecard not found for {session_id}")
                return

            # Download PDF
            from app.utils.file_storage import storage
            pdf_bytes = await storage.download(pdf_s3_key)

            # Send email
            await self._send(
                to_email=session.user.email,
                candidate_name=session.user.full_name,
                job_role=session.job_role,
                scorecard=scorecard,
                pdf_bytes=pdf_bytes,
            )

            # Mark email sent
            scorecard.email_sent = "true"
            from datetime import datetime, timezone
            scorecard.email_sent_at = datetime.now(timezone.utc)
            await db.commit()

    async def _send(self, to_email: str, candidate_name: str, job_role: str, scorecard, pdf_bytes: bytes):
        """Send email via SendGrid or log if not configured."""
        if not settings.SENDGRID_API_KEY:
            logger.info(
                f"[EMAIL STUB] Would send scorecard to {to_email} for {candidate_name} ({job_role}) "
                f"| Score: {scorecard.overall_score} | Rec: {scorecard.recommendation}"
            )
            return

        import sendgrid
        from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType
        import base64

        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)

        html_body = f"""
        <html><body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Your AI Interview Scorecard</h2>
        <p>Hi {candidate_name},</p>
        <p>Your interview for <strong>{job_role}</strong> has been completed.</p>
        <table style="border-collapse: collapse; width: 400px;">
          <tr style="background: #4f46e5; color: white;">
            <th style="padding: 8px;">Dimension</th><th style="padding: 8px;">Score</th>
          </tr>
          <tr><td style="padding: 8px;">Accuracy</td><td style="padding: 8px;">{scorecard.avg_accuracy}/10</td></tr>
          <tr><td style="padding: 8px;">Clarity</td><td style="padding: 8px;">{scorecard.avg_clarity}/10</td></tr>
          <tr><td style="padding: 8px;">Depth</td><td style="padding: 8px;">{scorecard.avg_depth}/10</td></tr>
          <tr style="font-weight: bold; background: #e0e7ff;">
            <td style="padding: 8px;">Overall</td><td style="padding: 8px;">{scorecard.overall_score}/10</td>
          </tr>
        </table>
        <p><strong>Recommendation:</strong> {scorecard.recommendation.upper().replace('_', ' ')}</p>
        <p>Your full scorecard PDF is attached.</p>
        <br><p>Best regards,<br>AI Interviewer Platform</p>
        </body></html>
        """

        message = Mail(
            from_email=settings.FROM_EMAIL,
            to_emails=to_email,
            subject=f"Your Interview Scorecard — {job_role}",
            html_content=html_body,
        )
        encoded_pdf = base64.b64encode(pdf_bytes).decode()
        message.attachment = Attachment(
            FileContent(encoded_pdf),
            FileName("scorecard.pdf"),
            FileType("application/pdf"),
        )
        sg.send(message)
        logger.info(f"Scorecard email sent to {to_email}")


email_service = EmailService()
