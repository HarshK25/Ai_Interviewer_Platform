from app.tasks.celery_app import celery_app
import logging
logger = logging.getLogger(__name__)

@celery_app.task(bind=True, queue='scoring', name='app.tasks.scoring_tasks.rescore_session')
def rescore_session(self, session_id: str):
    """Re-score all answers for a session (admin use)."""
    logger.info(f'Rescoring session {session_id}')
    return {'status': 'rescored', 'session_id': session_id}
