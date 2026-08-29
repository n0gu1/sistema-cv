from celery import shared_task
from django.conf import settings
from django.db import OperationalError

from reclutamiento.ai_analysis import (
    RetryableAnalysisError,
    _mark_analysis_job_failed,
    process_analysis_job,
)


@shared_task(
    bind=True,
    name="reclutamiento.tasks.process_application_analysis",
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_application_analysis(self, analysis_id, evaluation_id):
    """Process one prepared analysis and retry only transient failures."""
    try:
        return process_analysis_job(
            analysis_id,
            evaluation_id,
            retrying=(
                self.request.retries > 0
                or (self.request.delivery_info or {}).get("redelivered", False)
            ),
        )
    except (RetryableAnalysisError, OperationalError) as error:
        max_retries = max(0, int(settings.ANALYSIS_TASK_MAX_RETRIES))
        if self.request.retries < max_retries:
            countdown = min(300, 10 * (2 ** self.request.retries))
            raise self.retry(
                exc=error,
                countdown=countdown,
                max_retries=max_retries,
            )
        _mark_analysis_job_failed(analysis_id, evaluation_id, error)
        raise
    except Exception as error:
        _mark_analysis_job_failed(analysis_id, evaluation_id, error)
        raise
