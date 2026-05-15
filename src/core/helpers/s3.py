import s3fs

from core.config import settings


def _minio_creds() -> dict[str, str]:
    """Shared MinIO credentials — single source of truth."""
    return {
        "access_key": settings.minio.root_user,
        "secret_key": settings.minio.root_password,
        "endpoint": settings.minio.endpoint,
    }


_creds: dict[str, str] = _minio_creds()

S3_STORAGE_OPTIONS: dict[str, str] = {
    "aws_access_key_id": _creds["access_key"],
    "aws_secret_access_key": _creds["secret_key"],
    "aws_region": "us-east-1",
    "aws_endpoint_url": _creds["endpoint"],
    "aws_allow_http": "true",
}


def get_s3_fs() -> s3fs.S3FileSystem:
    """Create and return an S3FileSystem instance configured for MinIO."""
    return s3fs.S3FileSystem(
        key=_creds["access_key"],
        secret=_creds["secret_key"],
        endpoint_url=_creds["endpoint"],
    )
