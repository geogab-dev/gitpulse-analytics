"""Export static Parquet files for the public Streamlit dashboard."""

from __future__ import annotations

import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import polars as pl
from polars.dataframe.frame import DataFrame
from polars.lazyframe.frame import LazyFrame

from core.config import settings
from core.helpers.logger import cyan, get_logger, green, magenta, yellow
from core.helpers.s3 import S3_STORAGE_OPTIONS

_SIZE_WARN_MB = 90

OUTPUT_DIR = Path(settings.dashboard.static_data_path)

_MINIO_SILVER = {
    "orgs": f"s3://{settings.minio.bucket_silver}/github/orgs",
    "repos": f"s3://{settings.minio.bucket_silver}/github/repos",
    "actors": f"s3://{settings.minio.bucket_silver}/github/actors",
    "events": f"s3://{settings.minio.bucket_silver}/github/events",
}

_MINIO_GOLD = f"s3://{settings.minio.bucket_gold}/github/daily_activity"

# only columns the dashboard actually needs
_DIM_COLS = {
    "orgs": ["id", "login"],
    "repos": ["id", "name"],
    "actors": ["id", "login", "is_bot"],
}


def export_dashboard_data(days: int = 7) -> None:
    """
    Export static Parquet files for the Streamlit dashboard.

    Args:
        days: Number of complete days to export
    """
    logger = get_logger(__name__)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # latest day in gold
    max_day: date = (
        pl.scan_delta(source=_MINIO_GOLD, storage_options=S3_STORAGE_OPTIONS)
        .select(pl.col(name="day").max())
        .collect()
        .item()
    )

    min_day: date = max_day - timedelta(days=days)

    logger.info(
        "range: %s → %s  (%d days)",
        cyan(text=str(object=min_day)),
        cyan(text=str(object=max_day)),
        days,
    )

    # delete exported files if they already exist
    gold_daily_activity_path: Path = OUTPUT_DIR / "gold" / "daily_activity.parquet"
    if gold_daily_activity_path.exists():
        shutil.rmtree(path=gold_daily_activity_path, ignore_errors=True)

    # export gold metrics
    (
        pl.scan_delta(source=_MINIO_GOLD, storage_options=S3_STORAGE_OPTIONS)
        .filter(
            pl.col(name="day").is_between(
                lower_bound=min_day,
                upper_bound=max_day,
                closed="both",
            )
        )
        .sink_parquet(
            path=str(object=gold_daily_activity_path),
            compression="zstd",
            mkdir=True,
        )
    )
    _log_size(path=gold_daily_activity_path, label="gold/daily_activity", logger=logger)

    # get start and end datetime for filtering silver events
    start_dt: datetime = datetime.combine(date=min_day, time=datetime.min.time())
    end_dt: datetime = datetime.combine(date=max_day + timedelta(days=1), time=datetime.min.time())

    # delete exported files if they already exist
    silver_events_path: Path = OUTPUT_DIR / "silver" / "events"
    if silver_events_path.exists():
        shutil.rmtree(path=silver_events_path, ignore_errors=True)

    # export silver events (partitioned by day)
    lf: LazyFrame = (
        pl.scan_delta(source=_MINIO_SILVER["events"], storage_options=S3_STORAGE_OPTIONS)
        .filter(
            pl.col(name="created_at").is_between(
                lower_bound=start_dt, upper_bound=end_dt, closed="both"
            )
        )
        .with_columns(date=pl.col(name="created_at").dt.date())
    )

    df: DataFrame = lf.collect().drop("year", "month", "day", "hour")

    df.write_parquet(
        file=str(object=silver_events_path),
        partition_by=["date"],
        compression="zstd",
    )

    for p in sorted(silver_events_path.iterdir()):
        if p.is_dir():
            _log_size(path=p, label=f"silver/events/{p.name}", logger=logger)

    # export silver actors, repos and orgs dimensions (deduplicated)
    for dim_name in ("actors", "repos", "orgs"):
        # delete exported files if they already exist
        output_path: Path = OUTPUT_DIR / "silver" / f"{dim_name}.parquet"
        if output_path.exists():
            shutil.rmtree(path=output_path, ignore_errors=True)

        pl.scan_delta(
            source=_MINIO_SILVER[dim_name],
            storage_options=S3_STORAGE_OPTIONS,
        ).sort(
            "id",
            "first_seen_at",
            descending=[False, True],
        ).unique(subset=["id"], keep="first").select(
            _DIM_COLS[dim_name],
        ).sink_parquet(
            path=str(object=output_path),
            compression="zstd",
        )
        _log_size(path=output_path, label=f"silver/{dim_name}", logger=logger)

    logger.info(
        "✓ export complete — %s",
        green(text=str(object=OUTPUT_DIR)),
    )


def _log_size(path: Path, label: str, logger) -> None:
    """Log the size of a file or directory."""
    size_mb: int | float = (
        path.stat().st_size
        if path.is_file()
        else sum(f.stat().st_size for f in path.rglob(pattern="*.parquet"))
    ) / (1024 * 1024)

    if size_mb > _SIZE_WARN_MB:
        logger.warning(
            "%s — %.1f MB (near GitHub limit)",
            yellow(text=label),
            size_mb,
        )
    else:
        logger.info(
            "%s — %s",
            green(text=label),
            magenta(text=f"{size_mb:.1f} MB"),
        )


if __name__ == "__main__":
    export_dashboard_data(days=7)
