from app.tasks.celery_app import celery_app

@celery_app.task(queue='email', name='app.tasks.email_tasks.test_email')
def test_email(to_email: str):
    import logging
    logging.getLogger(__name__).info(f'Test email to {to_email}')
    return {'status': 'sent'}
