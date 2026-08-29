import logging

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import get_valid_filename


logger = logging.getLogger(__name__)

B2_PROVIDER_CODE = "BACKBLAZE_B2"


def _backblaze_client():
    required = {
        "BACKBLAZE_APPLICATION_KEY_ID": settings.BACKBLAZE_APPLICATION_KEY_ID,
        "BACKBLAZE_APPLICATION_KEY": settings.BACKBLAZE_APPLICATION_KEY,
        "BACKBLAZE_BUCKET_NAME": settings.BACKBLAZE_BUCKET_NAME,
        "BACKBLAZE_ENDPOINT_URL": settings.BACKBLAZE_ENDPOINT_URL,
        "BACKBLAZE_REGION": settings.BACKBLAZE_REGION,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValidationError(
            "Falta configurar Backblaze: " + ", ".join(missing) + "."
        )

    return boto3.client(
        "s3",
        endpoint_url=settings.BACKBLAZE_ENDPOINT_URL.rstrip("/"),
        region_name=settings.BACKBLAZE_REGION,
        aws_access_key_id=settings.BACKBLAZE_APPLICATION_KEY_ID,
        aws_secret_access_key=settings.BACKBLAZE_APPLICATION_KEY,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )


def upload_backblaze_object(uploaded_file, object_key, checksum):
    try:
        uploaded_file.seek(0)
        _backblaze_client().upload_fileobj(
            uploaded_file,
            settings.BACKBLAZE_BUCKET_NAME,
            object_key,
            ExtraArgs={
                "ContentType": "application/pdf",
                "Metadata": {"sha256": checksum},
            },
        )
    except (BotoCoreError, ClientError, OSError) as error:
        logger.exception("No se pudo cargar el curriculo en Backblaze.")
        raise ValidationError(
            "No fue posible guardar el curriculo en el almacenamiento privado."
        ) from error


def delete_backblaze_object(object_key):
    try:
        _backblaze_client().delete_object(
            Bucket=settings.BACKBLAZE_BUCKET_NAME,
            Key=object_key,
        )
    except (BotoCoreError, ClientError, OSError, ValidationError):
        logger.warning(
            "No se pudo eliminar el objeto de Backblaze durante la limpieza: %s",
            object_key,
            exc_info=True,
        )


def backblaze_download_url(object_key, original_filename):
    safe_filename = get_valid_filename(original_filename or "curriculo.pdf")
    safe_filename = safe_filename.replace('"', "")[:200] or "curriculo.pdf"
    params = {
        "Bucket": settings.BACKBLAZE_BUCKET_NAME,
        "Key": object_key,
        "ResponseContentType": "application/pdf",
        "ResponseContentDisposition": f'attachment; filename="{safe_filename}"',
    }
    try:
        return _backblaze_client().generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=settings.BACKBLAZE_PRESIGNED_URL_EXPIRY,
        )
    except (BotoCoreError, ClientError, OSError) as error:
        logger.exception("No se pudo generar la URL temporal del curriculo.")
        raise ValidationError(
            "No fue posible preparar la descarga del curriculo."
        ) from error
