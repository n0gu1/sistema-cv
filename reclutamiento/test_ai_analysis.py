import json
from datetime import date
from types import SimpleNamespace
from urllib.error import HTTPError
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from reclutamiento.ai_analysis import (
    GroqError,
    InvalidAnalysisResponse,
    RetryableAnalysisError,
    call_groq,
    _experience_result,
    _months_from_experiences,
    validate_analysis_response,
)


class GroqClientTests(SimpleTestCase):
    @override_settings(GROQ_API_KEY="")
    @patch("reclutamiento.ai_analysis.urlopen")
    def test_call_requires_api_key_before_network_request(self, urlopen):
        with self.assertRaisesMessage(
            GroqError,
            "Configura GROQ_API_KEY",
        ):
            call_groq("Texto del CV")

        urlopen.assert_not_called()

    @override_settings(GROQ_API_KEY="test-key")
    @patch("reclutamiento.ai_analysis.urlopen")
    def test_call_explains_authentication_failure(self, urlopen):
        urlopen.side_effect = HTTPError(
            "https://api.groq.example/openai/v1/chat/completions",
            401,
            "Unauthorized",
            {},
            None,
        )

        with self.assertRaisesMessage(
            GroqError,
            "La clave GROQ_API_KEY fue rechazada",
        ):
            call_groq("Texto del CV")

    @override_settings(GROQ_API_KEY="test-key")
    @patch("reclutamiento.ai_analysis.urlopen")
    def test_call_marks_rate_limit_as_retryable(self, urlopen):
        urlopen.side_effect = HTTPError(
            "https://api.groq.example/openai/v1/chat/completions",
            429,
            "Too Many Requests",
            {},
            None,
        )

        with self.assertRaisesMessage(
            RetryableAnalysisError,
            "limite de uso",
        ):
            call_groq("Texto del CV")

    @override_settings(
        GROQ_API_KEY="test-key",
        GROQ_API_BASE_URL="https://api.groq.example/openai/v1",
        GROQ_MODEL="qwen/qwen3.8-27b",
    )
    @patch("reclutamiento.ai_analysis.urlopen")
    def test_call_uses_json_mode_and_parses_response(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "personal_data": {},
                                    "professional_summary": "Resumen",
                                    "calculated_experience_months": 12,
                                    "experiences": [],
                                    "educations": [],
                                    "skills": [],
                                    "languages": [],
                                    "certifications": [],
                                }
                            )
                        },
                    }
                ]
            }
        ).encode("utf-8")
        urlopen.return_value = response

        result = call_groq("Texto del CV")

        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(
            request.full_url,
            "https://api.groq.example/openai/v1/chat/completions",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(request.get_header("User-agent"), "NexoTalento/1.0")
        self.assertEqual(body["model"], "qwen/qwen3.8-27b")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(result["calculated_experience_months"], 12)

    def test_validation_rejects_non_object_list_items(self):
        with self.assertRaises(InvalidAnalysisResponse):
            validate_analysis_response(
                {
                    "personal_data": {},
                    "skills": ["Python"],
                }
            )

    def test_call_accepts_json_wrapped_in_markdown_fence(self):
        payload = {
            "personal_data": {},
            "professional_summary": "Resumen",
            "experiences": [],
            "educations": [],
            "skills": [],
            "languages": [],
            "certifications": [],
        }
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": f"```json\n{json.dumps(payload)}\n```"},
                    }
                ]
            }
        ).encode("utf-8")
        with override_settings(GROQ_API_KEY="test-key"), patch(
            "reclutamiento.ai_analysis.urlopen", return_value=response
        ):
            result = call_groq("Texto del CV")

        self.assertEqual(result["professional_summary"], "Resumen")

    def test_validation_discards_invalid_email_and_preserves_raw_confidence_for_normalization(self):
        result = validate_analysis_response(
            {
                "personal_data": {"email": "no-es-un-correo"},
                "skills": [
                    {"name": "Python", "confidence": 2, "evidence": "mencionado"}
                ],
            }
        )

        self.assertIsNone(result["personal_data"]["email"])
        self.assertEqual(result["skills"][0]["confidence"], 2)


class ExperienceCalculationTests(SimpleTestCase):
    def test_months_merge_overlapping_experience_periods(self):
        experiences = [
            {"start_date": "2020-01-01", "end_date": "2021-01-01"},
            {"start_date": "2020-06-01", "end_date": "2020-12-01"},
            {"start_date": "2021-01-01", "end_date": "2021-06-01"},
        ]

        self.assertEqual(_months_from_experiences(experiences), 17)

    def test_experience_uses_required_profession_and_deduplicates_sources(self):
        profession = SimpleNamespace(nombre="Ingeniería de software")
        detail = SimpleNamespace(
            profesion_id=7,
            profesion=profession,
            meses_minimos=12,
        )
        requirement = SimpleNamespace(descripcion="Experiencia en ingeniería de software")
        analysis = SimpleNamespace(meses_experiencia_calculados=99)
        required_cv_record = SimpleNamespace(
            profesion_id=7,
            puesto="Desarrolladora backend",
            fecha_inicio=date(2020, 1, 1),
            fecha_fin=date(2021, 1, 1),
        )
        unrelated_cv_record = SimpleNamespace(
            profesion_id=11,
            puesto="Diseñadora gráfica",
            fecha_inicio=date(2015, 1, 1),
            fecha_fin=date(2025, 1, 1),
        )
        duplicate_profile_record = SimpleNamespace(
            profesion_id=7,
            puesto="Desarrolladora backend",
            fecha_inicio=date(2020, 1, 1),
            fecha_fin=date(2021, 1, 1),
        )

        result = _experience_result(
            requirement,
            detail,
            analysis,
            {
                "experiences": [required_cv_record, unrelated_cv_record],
            },
            {
                "experiences": [duplicate_profile_record],
            },
        )

        self.assertTrue(result[0])
        self.assertEqual(result[1], 100)
        self.assertEqual(
            result[2],
            "Se calcularon 12 meses de experiencia para Ingeniería de software.",
        )
