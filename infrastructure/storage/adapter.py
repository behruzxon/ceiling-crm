"""
File storage adapter.
Supports local filesystem and S3 backends.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import UTC
from pathlib import Path

import aiofiles

from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime"}
ALLOWED_DOC_TYPES = {"application/pdf"}
ALL_ALLOWED_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_VIDEO_TYPES | ALLOWED_DOC_TYPES

MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB


class StorageAdapter(ABC):
    """Abstract file storage interface."""

    @abstractmethod
    async def upload(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        """Upload file and return its URL/path."""
        ...

    @abstractmethod
    async def delete(self, file_path: str) -> bool:
        """Delete file by path. Returns True if deleted."""
        ...

    @abstractmethod
    async def exists(self, file_path: str) -> bool:
        """Check if file exists."""
        ...


class LocalStorageAdapter(StorageAdapter):
    """Store files on local filesystem."""

    def __init__(self, base_path: Path | None = None) -> None:
        settings = get_settings()
        self._base_path = base_path or settings.storage.local_path
        self._base_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Strip directory components and reject hidden/empty filenames."""
        safe = Path(filename).name
        if not safe or safe.startswith("."):
            safe = "upload"
        return safe

    def _generate_path(self, filename: str) -> Path:
        """Generate unique path: uploads/YYYY/MM/uuid_filename."""
        from datetime import datetime

        filename = self._sanitize_filename(filename)
        now = datetime.now(UTC)
        subdir = self._base_path / str(now.year) / f"{now.month:02d}"
        subdir.mkdir(parents=True, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        return subdir / unique_name

    async def upload(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        path = self._generate_path(filename)
        async with aiofiles.open(path, "wb") as f:
            await f.write(file_bytes)
        log.info("file_uploaded_local", path=str(path), size=len(file_bytes))
        return str(path)

    async def delete(self, file_path: str) -> bool:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            log.info("file_deleted_local", path=file_path)
            return True
        return False

    async def exists(self, file_path: str) -> bool:
        return Path(file_path).exists()


class S3StorageAdapter(StorageAdapter):
    """Store files on AWS S3."""

    def __init__(self) -> None:
        settings = get_settings()
        self._bucket = settings.storage.aws_bucket_name
        self._region = settings.storage.aws_region
        # Lazy import to avoid dependency if not using S3
        self._client = None

    def _get_client(self) -> object:
        if self._client is None:
            import boto3

            settings = get_settings()
            self._client = boto3.client(
                "s3",
                aws_access_key_id=settings.storage.aws_access_key_id,
                aws_secret_access_key=(
                    settings.storage.aws_secret_access_key.get_secret_value()
                    if settings.storage.aws_secret_access_key
                    else None
                ),
                region_name=self._region,
            )
        return self._client

    async def upload(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        import asyncio

        safe_name = LocalStorageAdapter._sanitize_filename(filename)
        key = f"uploads/{uuid.uuid4().hex[:8]}_{safe_name}"
        client = self._get_client()

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=file_bytes,
                ContentType=content_type,
            ),
        )

        url = f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{key}"
        log.info("file_uploaded_s3", key=key, size=len(file_bytes))
        return url

    async def delete(self, file_path: str) -> bool:
        import asyncio

        client = self._get_client()
        key = (
            file_path.split(".amazonaws.com/")[-1] if ".amazonaws.com/" in file_path else file_path
        )

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.delete_object(Bucket=self._bucket, Key=key),
        )
        return True

    async def exists(self, file_path: str) -> bool:
        import asyncio

        client = self._get_client()
        key = (
            file_path.split(".amazonaws.com/")[-1] if ".amazonaws.com/" in file_path else file_path
        )

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.head_object(Bucket=self._bucket, Key=key),
            )
            return True
        except Exception:
            return False


def get_storage_adapter() -> StorageAdapter:
    """Factory: return the configured storage adapter."""
    settings = get_settings()
    if settings.storage.backend == "s3":
        return S3StorageAdapter()
    return LocalStorageAdapter()
