"""
Transform raw GitHub events from Bronze into Silver Delta tables.

Reads partitioned Parquet from Bronze, parses JSON structs, extracts
event actions, builds fact and dimension DataFrames, validates with
Pandera contracts, then writes to Delta (append for events, SCD Type 1
upsert for dimensions).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import pandera.errors
import polars as pl
from deltalake.exceptions import DeltaError
from polars import DataFrame, LazyFrame
from s3fs import S3FileSystem

from core.config import settings
from core.contracts.silver import (
    KNOWN_EVENT_TYPES,
    ActorsContract,
    OrgsContract,
    ReposContract,
    SilverEventsContract,
)
from core.helpers.delta import append_delta, upsert_delta
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
        .drop("raw_action")
    )


def _build_events(df: DataFrame) -> DataFrame:
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
            pl.col("payload"),
            # partition columns from created_at
            pl.col("created_at").dt.year().cast(pl.String).alias("year"),
            pl.col("created_at").dt.month().cast(pl.String).str.pad_start(2, "0").alias("month"),
            pl.col("created_at").dt.day().cast(pl.String).str.pad_start(2, "0").alias("day"),
            pl.col("created_at").dt.hour().cast(pl.String).str.pad_start(2, "0").alias("hour"),
        )
        .drop_nulls(subset=["id", "actor_id", "repo_id"])
        .unique("id", keep="any")
    )


def _build_actors(df: DataFrame) -> DataFrame:
    """Build actors dimension, deduplicated by id."""
    return (
        df.select(
            pl.col("actor_struct").struct.field("*"),
            pl.col("created_at"),
        )
        .drop_nulls(subset=["id"])
        # sort so .last() and .shift() are deterministic
        .sort("id", "created_at")
        .with_columns(
            # true when login changes between consecutive events for the same actor
            _changed=(
                pl.col("login").shift(1).over("id").is_not_null()
                & (pl.col("login") != pl.col("login").shift(1).over("id"))
            ),
            # detect bots by login pattern: official [bot] suffix or common -bot ending
            # covers both github-actions[bot] and dependabot[bot] as well as renovate-bot style
            is_bot=pl.col("login").str.contains(r"\[bot\]|bot$"),
        )
        .group_by("id")
        .agg(
            # .last() gives the most recent value for each field
            pl.col("login").last(),
            pl.col("display_login").last(),
            pl.col("gravatar_id").last(),
            pl.col("url").last(),
            pl.col("avatar_url").last(),
            # is_bot is a stable property  any() is safe (all values are same)
            is_bot=pl.col("is_bot").any(),
            first_seen_at=pl.col("created_at").min(),
            # updated_at = timestamp of the change, or first_seen_at if unchanged
            updated_at=(
                pl.when(pl.col("_changed").any())
                .then(pl.col("created_at").filter(pl.col("_changed")).min())
                .otherwise(pl.col("created_at").min())
            ),
        )
    )


def _build_repos(df: DataFrame) -> DataFrame:
    """Build repos dimension, deduplicated by id."""
    return (
        df.select(
            pl.col("repo_struct").struct.field("*"),
            pl.col("created_at"),
        )
        .drop_nulls(subset=["id"])
        .sort("id", "created_at")
        .with_columns(
            # true when repo name changes between consecutive events
            _changed=(
                pl.col("name").shift(1).over("id").is_not_null()
                & (pl.col("name") != pl.col("name").shift(1).over("id"))
            )
        )
        .group_by("id")
        .agg(
            # .last() gives the most recent value for name and url
            pl.col("name").last(),
            pl.col("url").last(),
            first_seen_at=pl.col("created_at").min(),
            updated_at=(
                pl.when(pl.col("_changed").any())
                .then(pl.col("created_at").filter(pl.col("_changed")).min())
                .otherwise(pl.col("created_at").min())
            ),
        )
    )


def _build_orgs(df: DataFrame) -> DataFrame:
    """Build orgs dimension, deduplicated by id."""
    return (
        df.select(
            pl.col("org_struct").struct.field("*"),
            pl.col("created_at"),
        )
        .drop_nulls(subset=["id"])
        .sort("id", "created_at")
        .with_columns(
            # true when org login changes between consecutive events
            _changed=(
                pl.col("login").shift(1).over("id").is_not_null()
                & (pl.col("login") != pl.col("login").shift(1).over("id"))
            )
        )
        .group_by("id")
        .agg(
            # .last() gives the most recent value for each field
            pl.col("login").last(),
            pl.col("gravatar_id").last(),
            pl.col("url").last(),
            pl.col("avatar_url").last(),
            first_seen_at=pl.col("created_at").min(),
            updated_at=(
                pl.when(pl.col("_changed").any())
                .then(pl.col("created_at").filter(pl.col("_changed")).min())
                .otherwise(pl.col("created_at").min())
            ),
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
        6. Validate: Pandera contracts before any write
        7. Write: append events, upsert dims (SCD Type 1)
    """
    logger = get_logger(__name__)

    try:
        # lazy pipeline (reads + transforms, no collect yet)
        lf_events: LazyFrame = _read_bronze(batch_paths=batch_paths)
        lf_events: LazyFrame = _filter_events(lf=lf_events)
        lf_events: LazyFrame = _parse_structs(lf=lf_events)
        lf_events: LazyFrame = _extract_action(lf=lf_events)

        # materialize once, then build tables: fact + dimension dataFrames
        df_events_parsed: DataFrame = lf_events.collect().rechunk()

        df_events: DataFrame = _build_events(df=df_events_parsed)
        df_actors: DataFrame = _build_actors(df=df_events_parsed)
        df_repos: DataFrame = _build_repos(df=df_events_parsed)
        df_orgs: DataFrame = _build_orgs(df=df_events_parsed)

        # events: write append
        if not df_events.is_empty():
            SilverEventsContract.validate(check_obj=df_events)
            append_delta(
                df=df_events,
                target=f"s3://{settings.minio.bucket_silver}/github/events",
                partition_by=["year", "month", "day", "hour"],
            )

        # dimensions: SCD Type 1 upsert (insert new, update changed)
        if not df_actors.is_empty():
            ActorsContract.validate(check_obj=df_actors)
            upsert_delta(
                df=df_actors,
                target=f"s3://{settings.minio.bucket_silver}/github/actors",
                merge_predicate="target.id = source.id",
                update_predicate="target.login != source.login",
                insert_only_columns=["first_seen_at"],
            )

        if not df_repos.is_empty():
            ReposContract.validate(check_obj=df_repos)
            upsert_delta(
                df=df_repos,
                target=f"s3://{settings.minio.bucket_silver}/github/repos",
                merge_predicate="target.id = source.id",
                update_predicate="target.name != source.name",
                insert_only_columns=["first_seen_at"],
            )

        if not df_orgs.is_empty():
            OrgsContract.validate(check_obj=df_orgs)
            upsert_delta(
                df=df_orgs,
                target=f"s3://{settings.minio.bucket_silver}/github/orgs",
                merge_predicate="target.id = source.id",
                update_predicate="target.login != source.login",
                insert_only_columns=["first_seen_at"],
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
        return TransformResult.FAILED


__all__: list[str] = ["resolve_pending_partitions", "transform_batch"]
