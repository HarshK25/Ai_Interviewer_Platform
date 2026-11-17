import io
import os
import logging
import asyncio
from pathlib import Path
from app.config import settings

logger = logging.getLogger(__name__)

# Local fallback directory when MinIO is not available
LOCAL_STORAGE_DIR = Path("data/local_storage")


class FileStorage:
    """
    S3/MinIO-compatible storage with automatic local filesystem fallback.
    If MinIO is not reachable, files are stored under data/local_storage/.
    """

    def __init__(self):
        self._client = None
        self._use_local = False
        self._initialized = False

    def _try_init_s3(self):
        """Try to init boto3 S3 client. Returns True if successful."""
        try:
            import boto3
            from botocore.config import Config
            client = boto3.client(
                "s3",
                endpoint_url=settings.MINIO_ENDPOINT,
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY,
                config=Config(
                    connect_timeout=2,      # 2 second timeout
                    retries={"max_attempts": 1},  # no retries
                ),
                region_name="us-east-1",
            )
            # Quick test
            client.list_buckets()
            self._client = client
            return True
        except Exception as e:
            logger.warning(f"MinIO not available ({str(e)[:80]}). Using local storage fallback.")
            return False

    @property
    def client(self):
        if self._client is None:
            self._try_init_s3()
        return self._client

    async def ensure_bucket(self):
        """Ensure storage bucket / local dir exists."""
        if self._initialized:
            return
        self._initialized = True

        # Run synchronous S3 check in thread to avoid blocking startup
        loop = asyncio.get_event_loop()
        s3_ok = await loop.run_in_executor(None, self._try_init_s3)

        if s3_ok:
            try:
                loop.run_until_complete if False else None
                await loop.run_in_executor(None, self._ensure_s3_bucket)
                logger.info(f"✅ MinIO bucket '{settings.MINIO_BUCKET}' ready")
            except Exception as e:
                logger.warning(f"MinIO bucket create failed: {e}. Using local fallback.")
                self._use_local = True
        else:
            self._use_local = True
            LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Local storage ready at: {LOCAL_STORAGE_DIR.absolute()}")

    def _ensure_s3_bucket(self):
        try:
            self._client.head_bucket(Bucket=settings.MINIO_BUCKET)
        except Exception:
            self._client.create_bucket(Bucket=settings.MINIO_BUCKET)

    async def upload(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        """Upload bytes to S3/MinIO or local fallback."""
        if self._use_local or self.client is None:
            return self._local_save(data, key)
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._client.upload_fileobj(
                    io.BytesIO(data),
                    settings.MINIO_BUCKET,
                    key,
                    ExtraArgs={"ContentType": content_type},
                ),
            )
            return key
        except Exception as e:
            logger.warning(f"S3 upload failed ({e}), falling back to local.")
            return self._local_save(data, key)

    def _local_save(self, data: bytes, key: str) -> str:
        path = LOCAL_STORAGE_DIR / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    async def download(self, key: str) -> bytes:
        """Download bytes from S3/MinIO or local fallback."""
        if self._use_local or self.client is None:
            return (LOCAL_STORAGE_DIR / key).read_bytes()
        try:
            loop = asyncio.get_event_loop()
            buf = io.BytesIO()
            await loop.run_in_executor(
                None,
                lambda: self._client.download_fileobj(settings.MINIO_BUCKET, key, buf),
            )
            return buf.getvalue()
        except Exception:
            return (LOCAL_STORAGE_DIR / key).read_bytes()

    async def get_presigned_url(self, key: str, expires: int = 3600) -> str:
        """Get a presigned URL or local static URL."""
        if not key:
            return ""
        if self._use_local or self.client is None:
            return f"/static/files/{key}"
        try:
            loop = asyncio.get_event_loop()
            url = await loop.run_in_executor(
                None,
                lambda: self._client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": settings.MINIO_BUCKET, "Key": key},
                    ExpiresIn=expires,
                ),
            )
            return url
        except Exception:
            return f"/static/files/{key}"

    async def delete(self, key: str):
        """Delete a file from S3 or local."""
        if self._use_local or self.client is None:
            p = LOCAL_STORAGE_DIR / key
            if p.exists():
                p.unlink()
            return
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._client.delete_object(Bucket=settings.MINIO_BUCKET, Key=key),
            )
        except Exception as e:
            logger.warning(f"S3 delete failed: {e}")


storage = FileStorage()
