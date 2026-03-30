from io import BytesIO
from pathlib import Path

import boto3

from app.core.config import get_settings


class StorageService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.bucket = self.settings.s3_bucket
        self.backend = self.settings.storage_backend.lower()
        self.local_root = Path(self.settings.local_storage_root)
        self.client = None

        if self.backend == "local":
            self.local_root.mkdir(parents=True, exist_ok=True)
            return

        self.client = boto3.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint,
            aws_access_key_id=self.settings.s3_access_key,
            aws_secret_access_key=self.settings.s3_secret_key,
            region_name=self.settings.s3_region,
        )

    def upload_bytes(self, content: bytes, object_key: str, content_type: str) -> str:
        if self.backend == "local":
            target = self.local_root / object_key
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            return object_key

        self.client.upload_fileobj(
            Fileobj=BytesIO(content),
            Bucket=self.bucket,
            Key=object_key,
            ExtraArgs={"ContentType": content_type},
        )
        return object_key

    def download_bytes(self, object_key: str) -> bytes:
        if self.backend == "local":
            target = self.local_root / object_key
            if not target.exists():
                raise FileNotFoundError(f"{object_key} not found in local storage")
            return target.read_bytes()

        if self.client is None:
            raise RuntimeError("S3 client is not configured")

        response = self.client.get_object(Bucket=self.bucket, Key=object_key)
        body = response.get("Body")
        if body is None:
            raise RuntimeError("S3 response missing body")
        return body.read()

    def delete_bytes(self, object_key: str) -> None:
        if self.backend == "local":
            target = self.local_root / object_key
            if target.exists():
                target.unlink()
            return

        if self.client is None:
            raise RuntimeError("S3 client is not configured")

        self.client.delete_object(Bucket=self.bucket, Key=object_key)
