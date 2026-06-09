from datetime import date

import pandera.polars as pa
from pandera.engines.polars_engine import DateTime


class GoldDailyContract(pa.DataFrameModel):
    """
    Single aggregated daily table: events, PR health, and issue health.

    Grain: (day, repo_id, org_id)
    Partitioned by: year, month
    """

    day: date = pa.Field(nullable=False)
    repo_id: int = pa.Field(nullable=False, ge=0)
    org_id: int = pa.Field(nullable=True, ge=0)

    # event counts
    total_events: int = pa.Field(nullable=False, ge=0)
    unique_actors: int = pa.Field(nullable=False, ge=0)
    push_events: int = pa.Field(nullable=False, ge=0)
    pr_events: int = pa.Field(nullable=False, ge=0)
    issue_events: int = pa.Field(nullable=False, ge=0)
    watch_events: int = pa.Field(nullable=False, ge=0)
    fork_events: int = pa.Field(nullable=False, ge=0)
    release_events: int = pa.Field(nullable=False, ge=0)
    comment_events: int = pa.Field(nullable=False, ge=0)
    review_events: int = pa.Field(nullable=False, ge=0)

    # PR actions
    prs_opened: int = pa.Field(nullable=False, ge=0)
    prs_merged: int = pa.Field(nullable=False, ge=0)
    prs_closed_unmerged: int = pa.Field(nullable=False, ge=0)
    pr_merge_rate: float = pa.Field(nullable=True, ge=0.0, le=1.0)

    # Issue actions
    issues_opened: int = pa.Field(nullable=False, ge=0)
    issues_closed: int = pa.Field(nullable=False, ge=0)
    issue_close_rate: float = pa.Field(nullable=True, ge=0.0, le=1.0)

    # Score & metadata
    gitpulse_score: float = pa.Field(nullable=False, ge=0.0, le=100.0)
    updated_at: DateTime = pa.Field(nullable=False)

    # hive-style partition columns
    year: str = pa.Field(nullable=False, str_matches=r"^\d{4}$")
    month: str = pa.Field(nullable=False, str_matches=r"^(0[1-9]|1[0-2])$")


__all__: list[str] = [
    "GoldDailyContract",
]
