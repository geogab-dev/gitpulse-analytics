"""
Bronze ingestion flow: fetches GH Archive data and writes raw Parquet to MinIO.
"""

from multiprocessing import cpu_count

from prefect import flow, task

from core.ingestion import run_ingestion


@task(retries=3, retry_delay_seconds=30, log_prints=True)
def ingest_task(days: int, max_workers: int) -> None:
    """Task that wraps the core ingestion logic with Prefect retry policy."""
    run_ingestion(days=days, max_workers=max_workers)


@flow(name="bronze-ingestion", log_prints=True)
def bronze_ingestion_flow(days: int = 1, max_workers: int | None = None) -> None:
    """
    Ingest GH Archive data for the past N days into the Bronze layer.

    Args:
        days: Number of past days to ingest (default 1).
        max_workers: Thread pool size (defaults to CPU count).
    """
    workers: int = max_workers or cpu_count()
    ingest_task(days=days, max_workers=workers)


if __name__ == "__main__":
    bronze_ingestion_flow(days=1)
