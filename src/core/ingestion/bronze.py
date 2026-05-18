from datetime import UTC, datetime, timedelta
from enum import StrEnum

import pandera.errors
import polars as pl
from polars import LazyFrame

from core.config import settings
from core.contracts.bronze import BRONZE_EVENTS_SCHEMA, BronzeEventsContract
from core.helpers.logger import get_logger
from core.helpers.s3 import S3_STORAGE_OPTIONS, get_s3_fs

logger = get_logger(__name__)


class IngestResult(StrEnum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


def generate_hourly_datetimes(days: int) -> list[datetime]:
    """
    Generate hourly datetime objects for the past N days, going back from the last complete hour.

    Skips the current (incomplete) hour to avoid racing against GH Archive publication.
    For example, at 14:23 UTC, the last complete hour is 13:00 UTC.
    """
    now: datetime = datetime.now(UTC) - timedelta(hours=1)
    start: datetime = now.replace(minute=0, second=0, microsecond=0) - timedelta(days=days)
    hours: int = int((now - start).total_seconds() // 3600) + 1
    return [start + timedelta(hours=i) for i in range(hours)]


def ingest_hour(dt: datetime, overwrite: bool = False) -> IngestResult:
    """
    Fetch one hour of GH Archive events, validate a sample, and write as Parquet to the bronze layer.

    Steps:
        1. Skip if the parquet file already exists in MinIO (idempotency).
        2. Stream the .json.gz directly from GH Archive into a LazyFrame.
        3. Validate a sample (first 10k rows) against the bronze data contract.
        4. Sink to partitioned Parquet in S3 (MinIO).

    Error handling:
        - 404 from GH Archive -> the hour hasn't been published yet -> SKIPPED (no retry).
        - Contract validation failure -> FAILED (data quality gate).
        - Any other OSError/Exception -> FAILED (logged for investigation).

    Returns:
        IngestResult.SUCCESS — data ingested and written.
        IngestResult.SKIPPED — already in MinIO, or file not yet on GH Archive.
        IngestResult.FAILED  — validation or I/O error.
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
        fs = get_s3_fs()
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

        # validate a sample (first 10k rows) instead of the full file
        # GH Archive data is consistent, if the sample passes, the rest is safe
        # this avoids the overhead of Pandera expressions on every row during sink
        validated = BronzeEventsContract.validate(check_obj=lazy, lazy=True, head=10_000)
        validated.sink_parquet(path=s3_path, compression="zstd", storage_options=S3_STORAGE_OPTIONS)
        return IngestResult.SUCCESS
    except pandera.errors.SchemaError as ex:
        # data contract violation: data doesn't meet quality gates
        logger.error(f"data contract validation failed for {url}: {ex}")
        return IngestResult.FAILED
    except OSError as ex:
        # GH Archive may return 404 if the file for that hour hasn't been published yet.
        # This is normal, hours near "now" are often delayed so we skip, not fail.
        if "404" in str(ex) or "Not Found" in str(ex):
            return IngestResult.SKIPPED
        logger.error(f"failed to ingest {url}: {ex}")
        return IngestResult.FAILED
    except Exception as ex:
        logger.error(f"failed to ingest {url}: {ex}")
        return IngestResult.FAILED
