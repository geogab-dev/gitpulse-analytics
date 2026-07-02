"""
Transform raw GitHub events from Bronze into Silver Delta tables.

Reads partitioned Parquet from Bronze, parses JSON structs, extracts
event actions, builds fact and dimension DataFrames, validates with
Pandera contracts, then writes to Delta (append for events, SCD Type 1
anti-join + append for dimensions).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import pandera.errors
import polars as pl
from deltalake.exceptions import DeltaError
from polars import LazyFrame
from s3fs import S3FileSystem

from core.config import settings
from core.contracts.silver import (
    KNOWN_EVENT_TYPES,
    ActorsContract,
    OrgsContract,
    ReposContract,
    SilverEventsContract,
)
from core.helpers.delta import append_delta, filter_scd1
from core.helpers.logger import get_logger, magenta, yellow
from core.helpers.s3 import S3_STORAGE_OPTIONS


class TransformResult(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


# JSON schemas for decoding raw string columns into structs
ACTOR_STRUCT = pl.Struct(
    {
        "id": pl.Int64,
        "login": pl.String,
        "display_login": pl.String,
        "gravatar_id": pl.String,
        "url": pl.String,
        "avatar_url": pl.String,
    }
)

REPO_STRUCT = pl.Struct(
    {
        "id": pl.Int64,
        "name": pl.String,
        "url": pl.String,
    }
)

ORG_STRUCT = pl.Struct(
    {
        "id": pl.Int64,
        "login": pl.String,
        "gravatar_id": pl.String,
        "url": pl.String,
        "avatar_url": pl.String,
    }
)


# partition discovery
def _parse_partition_dt(partition_path: str) -> str:
    """Convert a hive partition path to a readable datetime label."""
    parts: dict[str, str] = dict(p.split("=") for p in partition_path.split("/"))
    return f"{parts['year']}-{parts['month']}-{parts['day']} {parts['hour']}:00"


def _list_partitions(fs: S3FileSystem, base_path: str) -> set[str]:
    """List year/month/day/hour partitions under *base_path*, returning relative paths."""
    if not fs.exists(base_path):
        return set()

    pattern: str = f"{base_path.rstrip('/')}/year=*/month=*/day=*/hour=*"
    base_stripped: str = base_path.rstrip("/").replace("s3://", "", 1)
    return {path.replace(f"{base_stripped}/", "", 1) for path in fs.glob(pattern) if fs.isdir(path)}


def resolve_pending_partitions(fs: S3FileSystem) -> list[str]:
    """Return Bronze partitions not yet processed in Silver, oldest-first."""
    logger = get_logger(__name__)

    bronze_parts: set[str] = _list_partitions(
        fs=fs, base_path=f"s3://{settings.minio.bucket_bronze}/github_events"
    )
    silver_parts: set[str] = _list_partitions(
        fs=fs, base_path=f"s3://{settings.minio.bucket_silver}/github/events"
    )

    pending: list[str] = sorted(bronze_parts - silver_parts)

    if pending:
        logger.info(
            "pending partitions: %s (bronze=%d, silver=%d)",
            yellow(len(pending)),
            len(bronze_parts),
            len(silver_parts),
        )
        logger.info(
            "range: %s → %s",
            magenta(_parse_partition_dt(pending[0])),
            magenta(_parse_partition_dt(pending[-1])),
        )
    else:
        logger.info(
            "pending partitions: %s (all caught up)",
            yellow("0"),
        )

    return pending


# Bronze -> Silver pipeline
def _read_bronze(batch_paths: list[str]) -> LazyFrame:
    """Scan multiple Bronze partitions into a single LazyFrame."""
    return pl.scan_parquet(
        source=[
            f"s3://{settings.minio.bucket_bronze}/github_events/{path}/" for path in batch_paths
        ],
        storage_options=S3_STORAGE_OPTIONS,
    )


def _filter_events(lf: LazyFrame) -> LazyFrame:
    """Keep only relevant event types and drop ingestion metadata."""
    return lf.filter(pl.col("type").is_in(KNOWN_EVENT_TYPES)).drop(
        "source_file", "ingestion_timestamp"
    )


def _parse_structs(lf: LazyFrame) -> LazyFrame:
    """Decode actor/repo/org JSON, parse timestamps, deduplicate by id."""
    return (
        lf.with_columns(
            actor_struct=pl.col("actor").str.json_decode(dtype=ACTOR_STRUCT),
            repo_struct=pl.col("repo").str.json_decode(dtype=REPO_STRUCT),
            org_struct=pl.col("org").str.json_decode(dtype=ORG_STRUCT),
        )
        .drop("actor", "repo", "org")
        .with_columns(
            created_at=pl.col("created_at").str.to_datetime("%Y-%m-%dT%H:%M:%SZ"),
        )
        .unique(subset=["id"], keep="any")
    )


def _extract_action(lf: LazyFrame) -> LazyFrame:
    """Parse or synthesize the ``action`` column from the raw payload."""
    return (
        lf.with_columns(
            raw_action=pl.coalesce(
                pl.col("payload").str.json_path_match("$.action"),
                pl.col("payload").str.extract(r'"action"\s*:\s*"([a-z_]+)"', 1),
            ),
        )
        .with_columns(
            action=(
                pl.when(pl.col("raw_action").is_not_null())
                .then(pl.col("raw_action"))
                .when(pl.col("type") == "PushEvent")
                .then(pl.lit("pushed"))
                .when(pl.col("type") == "CreateEvent")
                .then(pl.lit("created"))
                .when(pl.col("type") == "DeleteEvent")
                .then(pl.lit("deleted"))
            ),
        )
        .drop("raw_action", "payload")
    )


def _build_events(df: LazyFrame) -> LazyFrame:
    """Build the events fact table with hive partition columns."""
    return (
        df.select(
            pl.col("id").cast(pl.Int64),
            pl.col("type"),
            pl.col("action"),
            pl.col("actor_struct").struct.field("id").alias("actor_id"),
            pl.col("repo_struct").struct.field("id").alias("repo_id"),
            pl.col("org_struct").struct.field("id").alias("org_id"),
            pl.col("public"),
            pl.col("created_at"),
            # partition columns from created_at
            pl.col("created_at").dt.year().cast(pl.String).alias("year"),
            pl.col("created_at").dt.month().cast(pl.String).str.pad_start(2, "0").alias("month"),
            pl.col("created_at").dt.day().cast(pl.String).str.pad_start(2, "0").alias("day"),
            pl.col("created_at").dt.hour().cast(pl.String).str.pad_start(2, "0").alias("hour"),
        )
        .drop_nulls(subset=["id", "actor_id", "repo_id"])
        .unique("id", keep="any")
    )


def _build_actors(df: LazyFrame) -> LazyFrame:
    """Build actors dimension: one row per (id, login) version."""
    return (
        df.select(
            pl.col("actor_struct").struct.field("*"),
            pl.col("created_at"),
        )
        .drop_nulls(subset=["id"])
        .with_columns(
            is_bot=pl.col("login").str.contains(r"\[bot\]|bot$"),
        )
        .group_by("id", "login")
        .agg(
            pl.col("display_login").last(),
            pl.col("gravatar_id").last(),
            pl.col("url").last(),
            pl.col("avatar_url").last(),
            pl.col("is_bot").any(),
            first_seen_at=pl.col("created_at").min(),
            inserted_at=pl.lit(datetime.now(UTC).replace(tzinfo=None), dtype=pl.Datetime),
        )
    )


def _build_repos(df: LazyFrame) -> LazyFrame:
    """Build repos dimension: one row per (id, name) version."""
    return (
        df.select(
            pl.col("repo_struct").struct.field("*"),
            pl.col("created_at"),
        )
        .drop_nulls(subset=["id"])
        .group_by("id", "name")
        .agg(
            pl.col("url").last(),
            first_seen_at=pl.col("created_at").min(),
            inserted_at=pl.lit(datetime.now(UTC).replace(tzinfo=None), dtype=pl.Datetime),
        )
    )


def _build_orgs(df: LazyFrame) -> LazyFrame:
    """Build orgs dimension: one row per (id, login) version."""
    return (
        df.select(
            pl.col("org_struct").struct.field("*"),
            pl.col("created_at"),
        )
        .drop_nulls(subset=["id"])
        .group_by("id", "login")
        .agg(
            pl.col("gravatar_id").last(),
            pl.col("url").last(),
            pl.col("avatar_url").last(),
            first_seen_at=pl.col("created_at").min(),
            inserted_at=pl.lit(datetime.now(UTC).replace(tzinfo=None), dtype=pl.Datetime),
        )
    )


def transform_batch(batch_paths: list[str]) -> TransformResult:
    """
    Process one batch of Bronze partitions into Silver Delta tables.

    Steps:
        1. Read: scan Bronze Parquet partitions into a LazyFrame
        2. Filter: relevant types only, drop ingestion columns
        3. Parse: decode actor/repo/org JSON, parse timestamps
        4. Extract: parse or synthesize the ``action`` column
        5. Build: events fact + actors, repos, orgs dimensions
        6. Filter: SCD Type 1 anti-join on dims (lazy, no materialize)
        7. Collect: single ``pl.collect_all`` for all tables
        8. Validate: Pandera contracts before any write
        9. Write: append events + append filtered dimensions
    """
    logger = get_logger(__name__)

    try:
        # lazy pipeline (reads + transforms, no collect yet)
        lf_events: LazyFrame = _read_bronze(batch_paths=batch_paths)
        lf_events: LazyFrame = _filter_events(lf=lf_events)
        lf_events: LazyFrame = _parse_structs(lf=lf_events)
        lf_events_parsed: LazyFrame = _extract_action(lf=lf_events)

        # build tables: fact + dimension dataFrames
        lf_events: LazyFrame = _build_events(df=lf_events_parsed)
        lf_actors: LazyFrame = _build_actors(df=lf_events_parsed)
        lf_repos: LazyFrame = _build_repos(df=lf_events_parsed)
        lf_orgs: LazyFrame = _build_orgs(df=lf_events_parsed)

        # apply SCD Type 1 anti-join filter on dimensions (still lazy)
        lf_actors = filter_scd1(
            lf=lf_actors,
            target=f"s3://{settings.minio.bucket_silver}/github/actors",
            id_col="id",
            track_col="login",
        )

        lf_repos = filter_scd1(
            lf=lf_repos,
            target=f"s3://{settings.minio.bucket_silver}/github/repos",
            id_col="id",
            track_col="name",
        )

        lf_orgs = filter_scd1(
            lf=lf_orgs,
            target=f"s3://{settings.minio.bucket_silver}/github/orgs",
            id_col="id",
            track_col="login",
        )

        # single collect: materialize once for validation + write
        df_events, df_actors, df_repos, df_orgs = pl.collect_all(
            [
                lf_events,
                lf_actors,
                lf_repos,
                lf_orgs,
            ]
        )

        # fact events: write append
        if not df_events.is_empty():
            SilverEventsContract.validate(check_obj=df_events)
            append_delta(
                df=df_events,
                target=f"s3://{settings.minio.bucket_silver}/github/events",
                partition_by=["year", "month", "day", "hour"],
            )

        # dimensions: write append (already filtered by filter_scd1)
        if not df_actors.is_empty():
            ActorsContract.validate(check_obj=df_actors)
            append_delta(
                df=df_actors,
                target=f"s3://{settings.minio.bucket_silver}/github/actors",
            )

        if not df_repos.is_empty():
            ReposContract.validate(check_obj=df_repos)
            append_delta(
                df=df_repos,
                target=f"s3://{settings.minio.bucket_silver}/github/repos",
            )

        if not df_orgs.is_empty():
            OrgsContract.validate(check_obj=df_orgs)
            append_delta(
                df=df_orgs,
                target=f"s3://{settings.minio.bucket_silver}/github/orgs",
            )

        return TransformResult.SUCCESS

    except pandera.errors.SchemaError as ex:
        failures: Any | None = getattr(ex, "failure_cases", None)
        logger.error(
            "data contract violation: schema=%s batch=%s failures=%s",
            ex.schema.name if hasattr(ex, "schema") else "unknown",
            batch_paths,
            failures.head().to_dict() if failures is not None else "?",
        )
        return TransformResult.FAILED

    except DeltaError as ex:
        logger.error(
            "delta operation failed: batch=%s target_details=%s",
            batch_paths,
            str(ex)[:200],
        )
        return TransformResult.FAILED

    except Exception:
        logger.exception("unexpected error in batch: %s", batch_paths)
        raise


__all__: list[str] = ["resolve_pending_partitions", "transform_batch"]
