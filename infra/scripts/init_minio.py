# infra/scripts/init_minio.py
from logging import Logger, LoggerAdapter

import s3fs

from core.config import settings
from core.helpers.logger import get_logger


def init_minio_buckets() -> None:
    """
    Set up MinIO buckets for bronze, silver, and gold layers.
    This function checks if the buckets already exist and creates them if they don't.
    """
    logger: Logger | LoggerAdapter[Logger] = get_logger(__name__)
    logger.info("🧺  Starting MinIO bucket setup...")

    # connect to MinIO using s3fs with the provided credentials and endpoint
    fs = s3fs.S3FileSystem(
        key=settings.minio.root_user,
        secret=settings.minio.root_password,
        endpoint_url=settings.minio.endpoint,
    )

    # get the bucket names from settings
    buckets: list[str] = [
        settings.minio.bucket_bronze,
        settings.minio.bucket_silver,
        settings.minio.bucket_gold,
    ]

    # create buckets if they don't exist
    for bucket in buckets:
        if not fs.exists(bucket):
            fs.mkdir(bucket)
            logger.info(f"✔  Bucket '{bucket}' created successfully")
        else:
            logger.warning(f"❌  Bucket '{bucket}' already exists")

    logger.info("🚀  Infrastructure initialized, ready to process data!")


if __name__ == "__main__":
    init_minio_buckets()
