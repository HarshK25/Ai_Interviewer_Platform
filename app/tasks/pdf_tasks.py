import asyncio
import logging
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async code inside a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, queue="pdf", name="app.tasks.pdf_tasks.generate_scorecard_task")
def generate_scorecard_task(self, session_id: str):
    """
    Background task triggered when interview completes:
    1. Fetch session data + scores
    2. Generate PDF scorecard
    3. Upload to MinIO
    4. Save Scorecard to DB
    5. Chain → send email
    """
    try:
        logger.info(f"Generating scorecard for session {session_id}")
        from app.services.scorecard_service import scorecard_service
        s3_key = run_async(scorecard_service.generate_scorecard(session_id))
        logger.info(f"Scorecard generated: {s3_key}")

        # Chain to email task
        send_scorecard_email_task.delay(session_id, s3_key)
        return {"status": "success", "s3_key": s3_key}
    except Exception as exc:
        logger.error(f"Scorecard generation failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@celery_app.task(bind=True, max_retries=3, queue="email", name="app.tasks.pdf_tasks.send_scorecard_email_task")
def send_scorecard_email_task(self, session_id: str, pdf_s3_key: str):
    """Send scorecard PDF email to the candidate."""
    try:
        from app.services.email_service import email_service
        run_async(email_service.send_scorecard_from_session(session_id, pdf_s3_key))
        logger.info(f"Scorecard email sent for session {session_id}")
        return {"status": "email_sent"}
    except Exception as exc:
        logger.error(f"Email failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=120 * (self.request.retries + 1))
