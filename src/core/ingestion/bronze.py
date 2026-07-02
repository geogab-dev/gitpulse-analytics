from datetime import UTC, datetime, timedelta
from enum import StrEnum

import polars as pl
from polars import LazyFrame
from s3fs import S3FileSystem

from core.config import settings
from core.contracts.bronze import BRONZE_EVENTS_SCHEMA
from core.helpers.s3 import S3_STORAGE_OPTIONS, get_s3_fs


class IngestResult(StrEnum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


def generate_hourly_datetimes(days: int) -> list[datetime]:
    """
    Generate hourly datetime objects for the past N complete days, starting from hour 0.

    Skips the current (incomplete) hour to avoid racing against GH Archive publication.
    For example, at 14:23 UTC, the last complete hour is 13:00 UTC.
    The range covers from ``00:00`` of ``days`` days ago up to that last complete hour.
    """
    now: datetime = datetime.now(UTC) - timedelta(hours=1)
    start: datetime = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    hours: int = int((now - start).total_seconds() // 3600) + 1
    return [start + timedelta(hours=i) for i in range(hours)]


def ingest_hour(dt: datetime, overwrite: bool = False) -> IngestResult:
    """
    Fetch one hour of GH Archive events and write as Parquet to the bronze layer.

    Steps:
        1. Skip if the parquet file already exists in MinIO (idempotency).
        2. Stream the .json.gz directly from GH Archive into a LazyFrame.
        3. Sink to partitioned Parquet in S3 (MinIO).

    Error handling:
        - 404 from GH Archive -> the hour hasn't been published yet -> SKIPPED (no retry).
        - Any other OSError -> re-raised, caught by the worker in runner.py.

    Returns:
        IngestResult.SUCCESS — data ingested and written.
        IngestResult.SKIPPED — already in MinIO or not yet on GH Archive.
    """

    # build URL from datetime components
    url: str = f"https://data.gharchive.org/{dt.year}-{dt.month:02d}-{dt.day:02d}-{dt.hour}.json.gz"

    # partition path mirrors the GH Archive folder structure for easy backfilling
    partition_path: str = f"year={dt.year}/month={dt.month:02d}/day={dt.day:02d}/hour={dt.hour:02d}"
    s3_path: str = (
        f"s3://{settings.minio.bucket_bronze}/github_events/{partition_path}/events.parquet"
    )

    # skip if data is already in the lake (idempotent runs)
    if not overwrite:
        fs: S3FileSystem = get_s3_fs()
        if fs.exists(s3_path):
            return IngestResult.SKIPPED

    try:
        lazy: LazyFrame = pl.scan_ndjson(
            source=url,
            schema=BRONZE_EVENTS_SCHEMA,
            include_file_paths="source_file",  # create source_file column
        ).with_columns(
            ingestion_timestamp=pl.lit(
                datetime.now(UTC), dtype=pl.Datetime(time_unit="us", time_zone="UTC")
            ),
        )

        # opt to not validate the data here since GH Archive is a well-known consistent source
        # we want to avoid the pandera validation overhead and improve ingestion speed
        # future validations will occur in the silver transformation layer
        lazy.sink_parquet(path=s3_path, compression="zstd", storage_options=S3_STORAGE_OPTIONS)
        return IngestResult.SUCCESS
    except OSError as ex:
        # GH Archive may return 404 if the file for that hour hasn't been published yet.
        # This is normal, hours near "now" are often delayed so we skip, not fail.
        if "404" in str(ex) or "Not Found" in str(ex):
            return IngestResult.SKIPPED
        raise
