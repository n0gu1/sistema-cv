from unittest.mock import patch

from celery.exceptions import Retry
from django.test import SimpleTestCase, override_settings

from reclutamiento.ai_analysis import RetryableAnalysisError
from reclutamiento.tasks import process_application_analysis


class AnalysisTaskTests(SimpleTestCase):
    @override_settings(ANALYSIS_TASK_MAX_RETRIES=3)
    @patch("reclutamiento.tasks._mark_analysis_job_failed")
    @patch("reclutamiento.tasks.process_analysis_job")
    def test_transient_failure_is_retried_without_marking_job_failed(
        self, process_job, mark_failed
    ):
        process_job.side_effect = RetryableAnalysisError("Groq no responde")

        with patch.object(
            process_application_analysis,
            "retry",
            side_effect=Retry(),
        ) as retry:
            with self.assertRaises(Retry):
                process_application_analysis.run(10, 20)

        process_job.assert_called_once_with(10, 20, retrying=False)
        mark_failed.assert_not_called()
        retry.assert_called_once()
