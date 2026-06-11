"""
S3/MinIO клиент — загрузка, скачивание, presigned URLs.

Использует boto3 для совместимости с любым S3-совместимым хранилищем
(MinIO, AWS S3, Yandex Object Storage и т.д.).
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Конфигурация из переменных окружения
S3_ENDPOINT   = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", os.getenv("MINIO_ROOT_USER", "minioadmin"))
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"))
S3_BUCKET     = os.getenv("S3_BUCKET", "chemrep-files")
S3_REGION     = os.getenv("S3_REGION", "us-east-1")

_presigned_url_ttl = 3600  # 1 час


def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket() -> None:
    """Создать bucket, если не существует."""
    client = _get_client()
    try:
        client.head_bucket(Bucket=S3_BUCKET)
    except ClientError:
        try:
            client.create_bucket(Bucket=S3_BUCKET)
            logger.info("[S3] Bucket '%s' создан", S3_BUCKET)
        except Exception as e:
            logger.warning("[S3] Не удалось создать bucket: %s", e)


def upload_bytes(data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
    """
    Загрузить байты в S3.
    Возвращает key (путь в хранилище).
    """
    client = _get_client()
    client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    logger.debug("[S3] Загружен %s (%d байт)", key, len(data))
    return key


def upload_fileobj(fileobj, key: str, content_type: str = "application/octet-stream") -> str:
    """Загрузить file-like объект в S3."""
    client = _get_client()
    client.upload_fileobj(fileobj, S3_BUCKET, key, ExtraArgs={"ContentType": content_type})
    logger.debug("[S3] Загружен %s", key)
    return key


def download_bytes(key: str) -> bytes:
    """Скачать объект из S3 как bytes."""
    client = _get_client()
    resp = client.get_object(Bucket=S3_BUCKET, Key=key)
    return resp["Body"].read()


def delete_object(key: str) -> None:
    """Удалить объект из S3."""
    client = _get_client()
    client.delete_object(Bucket=S3_BUCKET, Key=key)
    logger.debug("[S3] Удалён %s", key)


def presign_url(key: str, ttl: int = _presigned_url_ttl) -> str:
    """Сгенерировать presigned URL для скачивания."""
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=ttl,
    )


def object_exists(key: str) -> bool:
    """Проверить, существует ли объект."""
    client = _get_client()
    try:
        client.head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except ClientError:
        return False
