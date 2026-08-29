from io import BytesIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from reclutamiento.storage import (
    backblaze_download_url,
    upload_backblaze_object,
)


class BackblazeStorageTests(SimpleTestCase):
    backblaze_settings = {
        "BACKBLAZE_APPLICATION_KEY_ID": "key-id",
        "BACKBLAZE_APPLICATION_KEY": "application-key",
        "BACKBLAZE_BUCKET_NAME": "sistema-cv-curriculos-privados",
        "BACKBLAZE_ENDPOINT_URL": "https://s3.eu-central-003.backblazeb2.com",
        "BACKBLAZE_REGION": "eu-central-003",
        "BACKBLAZE_PRESIGNED_URL_EXPIRY": 300,
    }

    @override_settings(**backblaze_settings)
    @patch("reclutamiento.storage.boto3.client")
    def test_uploads_pdf_to_backblaze_with_checksum_metadata(self, client_factory):
        uploaded_file = BytesIO(b"%PDF-1.4\n%%EOF")
        checksum = "a" * 64

        upload_backblaze_object(uploaded_file, "curriculos/1/archivo.pdf", checksum)

        client = client_factory.return_value
        client.upload_fileobj.assert_called_once_with(
            uploaded_file,
            "sistema-cv-curriculos-privados",
            "curriculos/1/archivo.pdf",
            ExtraArgs={
                "ContentType": "application/pdf",
                "Metadata": {"sha256": checksum},
            },
        )
        self.assertEqual(uploaded_file.tell(), 0)

    @override_settings(**backblaze_settings)
    @patch("reclutamiento.storage.boto3.client")
    def test_generates_short_lived_download_url(self, client_factory):
        client_factory.return_value.generate_presigned_url.return_value = (
            "https://signed.example/curriculo"
        )

        url = backblaze_download_url(
            "curriculos/1/archivo.pdf",
            "mi curriculo.pdf",
        )

        self.assertEqual(url, "https://signed.example/curriculo")
        client_factory.return_value.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={
                "Bucket": "sistema-cv-curriculos-privados",
                "Key": "curriculos/1/archivo.pdf",
                "ResponseContentType": "application/pdf",
                "ResponseContentDisposition": 'attachment; filename="mi_curriculo.pdf"',
            },
            ExpiresIn=300,
        )

    @override_settings(
        BACKBLAZE_APPLICATION_KEY_ID="",
        BACKBLAZE_APPLICATION_KEY="",
        BACKBLAZE_BUCKET_NAME="",
        BACKBLAZE_ENDPOINT_URL="",
        BACKBLAZE_REGION="",
    )
    def test_rejects_missing_backblaze_configuration(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Falta configurar Backblaze:",
        ):
            backblaze_download_url("curriculos/1/archivo.pdf", "curriculo.pdf")
