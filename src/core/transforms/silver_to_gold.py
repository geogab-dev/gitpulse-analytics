"""
Build the single Gold aggregated table from Silver events.

A single group_by + agg pass computes all daily metrics:
event-type counts, GitPulse Score, PR action breakdown,
and issue action breakdown, no payload parsing.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum

import pandera.errors
import polars as pl
from deltalake import DeltaTable
from deltalake.exceptions import DeltaError, TableNotFoundError
from polars import DataFrame, LazyFrame

from core.config import settings
from core.contracts.gold import GoldDailyContract
from core.helpers.delta import append_delta
from core.helpers.logger import get_logger, magenta, yellow
from core.helpers.s3 import S3_STORAGE_OPTIONS


class TransformResult(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


# paths
SILVER_GH_EVENTS: str = f"s3://{settings.minio.bucket_silver}/github/events"
GOLD_DAILY_ACTIVITY: str = f"s3://{settings.minio.bucket_gold}/github/daily_activity"

# GitPulse Score weights
GITPULSE_WEIGHTS: dict[str, int] = {
    "PushEvent": 1,
    "PullRequestEvent": 5,
    "IssuesEvent": 3,
    "WatchEvent": 2,
}


# watermark
def _get_watermark() -> date:
    """Return the greatest ``day`` already in the gold table."""
    logger = get_logger(__name__)

    try:
        DeltaTable(GOLD_DAILY_ACTIVITY, storage_options=S3_STORAGE_OPTIONS)
    except TableNotFoundError:
        logger.info(
            "%s not found: watermark set to 2014-12-31 (full backfill)",
            yellow(GOLD_DAILY_ACTIVITY),
        )
        return date(2014, 12, 31)

    watermark: date = (
        pl.scan_delta(source=GOLD_DAILY_ACTIVITY, storage_options=S3_STORAGE_OPTIONS)
        .select(pl.col("day").max())
        .collect()
        .item()
    )

    logger.info("watermark: %s", magenta(str(watermark)))
    return watermark


def resolve_pending_days() -> list[date]:
    """
    Return Silver event days not yet in the gold table, oldest-first.

    Uses ``WHERE created_at > watermark`` — Delta Lake partition pruning
    handles performance.
    """
    logger = get_logger(__name__)

    watermark: date = _get_watermark()

    pending: list[date] = (
        pl.scan_delta(source=SILVER_GH_EVENTS, storage_options=S3_STORAGE_OPTIONS)
        .filter(pl.col("created_at") > watermark)
        .select(pl.col("created_at").dt.date().alias("day"))
        .unique()
        .sort("day")
        .collect()
        .to_series()
        .to_list()
    )

    n_pending: int = len(pending)

    if n_pending > 0:
        logger.info(
            "pending days: %s (watermark=%s, range=%s → %s)",
            yellow(n_pending),
            magenta(str(watermark)),
            magenta(str(pending[0])),
            magenta(str(pending[-1])),
        )
    else:
        logger.info(
            "pending days: %s (all caught up, watermark=%s)",
            yellow("0"),
            magenta(str(watermark)),
        )

    return pending


# helper: filter + project silver events for a day range
def _read_silver_events(days_batch: list[date]) -> LazyFrame:
    """
    Scan silver events for a specific range of days.

    Projects to the 8 columns needed by the gold aggregation — no payload
    parsing needed since we don't pair PRs/issues by number.
    """
    start_date: date = days_batch[0]
    end_date: date = days_batch[-1]

    return (
        pl.scan_delta(source=SILVER_GH_EVENTS, storage_options=S3_STORAGE_OPTIONS)
        .filter(
            pl.col("created_at").dt.date().is_between(start_date, end_date, closed="both"),
        )
        .select("type", "action", "actor_id", "repo_id", "org_id", "created_at")
    )


# single transform: 1 scan → 1 agg → 1 append
def _build_gold_daily(lf: LazyFrame) -> DataFrame:
    """
    Aggregate all daily metrics in a single pass: event counts, GitPulse
    Score, PR actions, and issue actions.

    ``prs_closed_unmerged`` is derived from the difference between closed
    and merged PRs — no payload parsing needed.
    """
    return (
        lf.with_columns(
            day=pl.col("created_at").dt.date(),
            is_pr=pl.col("type").eq("PullRequestEvent"),
            is_issue=pl.col("type").eq("IssuesEvent"),
        )
        .group_by("day", "repo_id", "org_id")
        .agg(
            # event counts
            total_events=pl.len().cast(pl.Int64),
            unique_actors=pl.col("actor_id").n_unique().cast(pl.Int64),
            push_events=pl.col("type").eq("PushEvent").sum().cast(pl.Int64),
            pr_events=pl.col("is_pr").sum().cast(pl.Int64),
            issue_events=pl.col("is_issue").sum().cast(pl.Int64),
            watch_events=pl.col("type").eq("WatchEvent").sum().cast(pl.Int64),
            fork_events=pl.col("type").eq("ForkEvent").sum().cast(pl.Int64),
            release_events=pl.col("type").eq("ReleaseEvent").sum().cast(pl.Int64),
            comment_events=pl.col("type").eq("IssueCommentEvent").sum().cast(pl.Int64),
            review_events=(
                pl.col("type").eq("PullRequestReviewEvent").sum()
                + pl.col("type").eq("PullRequestReviewCommentEvent").sum()
            ).cast(pl.Int64),
            # PR actions
            prs_opened=(pl.col("is_pr") & pl.col("action").eq("opened")).sum().cast(pl.Int64),
            prs_merged=(pl.col("is_pr") & pl.col("action").eq("merged")).sum().cast(pl.Int64),
            prs_closed=(pl.col("is_pr") & pl.col("action").eq("closed")).sum().cast(pl.Int64),
            # Issue actions
            issues_opened=(pl.col("is_issue") & pl.col("action").eq("opened")).sum().cast(pl.Int64),
            issues_closed=(pl.col("is_issue") & pl.col("action").eq("closed")).sum().cast(pl.Int64),
        )
        .with_columns(
            # prs_closed_unmerged = prs_closed - prs_merged (clamped to 0)
            # GitHub fires both action=merged and action=closed on merge.
            # The two events can end up in different (day, repo_id, org_id)
            # groups (e.g. merge at 23:59, closed at 00:01) — clipping
            # to 0 avoids negative values in those edge cases.
            prs_closed_unmerged=pl.max_horizontal(
                pl.col("prs_closed") - pl.col("prs_merged"),
                pl.lit(0),
            ).cast(pl.Int64),
            # GitPulse Score: weighted sum normalized to 0-100
            gitpulse_score=pl.min_horizontal(
                (
                    pl.col("push_events") * GITPULSE_WEIGHTS["PushEvent"]
                    + pl.col("pr_events") * GITPULSE_WEIGHTS["PullRequestEvent"]
                    + pl.col("issue_events") * GITPULSE_WEIGHTS["IssuesEvent"]
                    + pl.col("watch_events") * GITPULSE_WEIGHTS["WatchEvent"]
                ).cast(pl.Float64),
                pl.lit(100.0),
            ),
            updated_at=pl.lit(datetime.now(UTC).replace(tzinfo=None), dtype=pl.Datetime),
        )
        .with_columns(
            pr_merge_rate=pl.when((pl.col("prs_merged") + pl.col("prs_closed_unmerged")) > 0).then(
                pl.col("prs_merged") / (pl.col("prs_merged") + pl.col("prs_closed_unmerged"))
            ),
            issue_close_rate=pl.when((pl.col("issues_opened") + pl.col("issues_closed")) > 0).then(
                pl.col("issues_closed") / (pl.col("issues_opened") + pl.col("issues_closed"))
            ),
            year=pl.col("day").dt.year().cast(pl.String),
            month=pl.col("day").dt.month().cast(pl.String).str.pad_start(2, "0"),
        )
        .sort("day", "repo_id")
        .collect()
    )


def silver_to_gold(days_batch: list[date]) -> TransformResult:
    """
    Process one batch of days through the Silver -> Gold pipeline.

    Single scan → single aggregate → Pandera validate → single append.
    """
    logger = get_logger(__name__)
    batch_label: str = f"{days_batch[0]} → {days_batch[-1]}"

    try:
        lf: LazyFrame = _read_silver_events(days_batch=days_batch)

        df: DataFrame = _build_gold_daily(lf=lf)

        if df.is_empty():
            logger.info("no data for batch %s", batch_label)
            return TransformResult.SUCCESS

        GoldDailyContract.validate(check_obj=df)

        append_delta(
            df=df,
            target=GOLD_DAILY_ACTIVITY,
            partition_by=["year", "month"],
        )

        return TransformResult.SUCCESS

    except pandera.errors.SchemaError as ex:
        logger.error(
            "data contract violation: schema=%s batch=%s failure_cases=%s",
            getattr(ex, "schema", "unknown"),
            batch_label,
            str(getattr(ex, "failure_cases", "?")),
        )
        return TransformResult.FAILED

    except DeltaError as ex:
        logger.error(
            "delta operation failed: batch=%s target_details=%s",
            batch_label,
            str(ex)[:200],
        )
        return TransformResult.FAILED

    except Exception:
        logger.exception("unexpected error in batch: %s", batch_label)
        return TransformResult.FAILED


__all__: list[str] = [
    "TransformResult",
    "resolve_pending_days",
    "silver_to_gold",
]
