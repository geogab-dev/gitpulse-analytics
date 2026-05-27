# infra/scripts/init_minio.py
from logging import Logger, LoggerAdapter

from s3fs import S3FileSystem

from core.config import settings
from core.helpers.logger import get_logger
from core.helpers.s3 import get_s3_fs


def init_minio_buckets() -> None:
    """
    Set up MinIO buckets for bronze, silver, and gold layers.
    """
    logger: Logger | LoggerAdapter[Logger] = get_logger(__name__)

    try:
        fs: S3FileSystem = get_s3_fs()
        # probe connectivity by listing the root
        fs.ls("/")
    except Exception:
        logger.error(
            "cannot connect to MinIO at %s — is Docker Compose running?",
            settings.minio.endpoint,
        )
        return

    buckets: list[str] = [
        settings.minio.bucket_bronze,
        settings.minio.bucket_silver,
        settings.minio.bucket_gold,
    ]

    logger.info("Starting MinIO bucket setup...")

    for bucket in buckets:
        if not fs.exists(bucket):
            fs.mkdir(bucket)
            logger.info("Bucket '%s' created successfully", bucket)
        else:
            logger.warning("Bucket '%s' already exists", bucket)

    logger.info("Infrastructure initialized, ready to process data!")


if __name__ == "__main__":
    init_minio_buckets()
