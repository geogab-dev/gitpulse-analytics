import pandera.polars as pa
import polars as pl
from pandera.engines.polars_engine import DateTime

# known github event types (validated against the API payload)
KNOWN_EVENT_TYPES: list[str] = [
    "PushEvent",
    "PullRequestEvent",
    "IssuesEvent",
    "WatchEvent",
    "IssueCommentEvent",
    "PullRequestReviewEvent",
    "PullRequestReviewCommentEvent",
    "CreateEvent",
    "DeleteEvent",
    "ForkEvent",
    "ReleaseEvent",
    "CommitCommentEvent",
    # event types excluded (low-value for our use case):
    # "GollumEvent", "MemberEvent", "DiscussionEvent", "PublicEvent",
]


# known github event actions (validated against the API payload)
KNOWN_ACTIONS: list[str] = [
    "assigned",
    "closed",
    "dismissed",
    "labeled",
    "opened",
    "published",
    "reopened",
    "started",
    "unassigned",
    "unlabeled",
    "updated",
    "forked",
    "merged",
    # sintetic actions derived from payload not explicitly labeled in the API:
    "pushed",
    "created",
    "deleted",
]


class SilverEventsContract(pa.DataFrameModel):
    """Fact table: one row per GitHub event (validated types and actions)."""

    id: str = pa.Field(nullable=False)
    type: str = pa.Field(nullable=False, isin=KNOWN_EVENT_TYPES)
    action: str = pa.Field(nullable=False, isin=KNOWN_ACTIONS)
    actor_id: int = pa.Field(nullable=False, ge=0)
    repo_id: int = pa.Field(nullable=False, ge=0)
    org_id: int = pa.Field(nullable=True, ge=0)
    public: bool = pa.Field(nullable=False)
    created_at: pl.Datetime = pa.Field(nullable=False)
    payload: str = pa.Field(nullable=False)

    # partition columns (hive-style)
    year: str = pa.Field(nullable=False, str_matches=r"^\d{4}$")  # YYYY
    month: str = pa.Field(nullable=False, str_matches=r"^(0[1-9]|1[0-2])$")  # MM
    day: str = pa.Field(nullable=False, str_matches=r"^(0[1-9]|[12]\d|3[01])$")  # DD
    hour: str = pa.Field(nullable=False, str_matches=r"^(0\d|1\d|2[0-3])$")  # HH


class ActorsContract(pa.DataFrameModel):
    """SCD Type 1 dimension: one unique row per GitHub actor."""

    id: int = pa.Field(nullable=False, unique=True, ge=0)
    login: str = pa.Field(nullable=False)
    display_login: str = pa.Field(nullable=True)
    gravatar_id: str = pa.Field(nullable=True)
    url: str = pa.Field(nullable=False)
    avatar_url: str = pa.Field(nullable=True)
    first_seen_at: DateTime = pa.Field(nullable=False, dtype_kwargs={"time_zone_agnostic": True})
    updated_at: DateTime = pa.Field(nullable=False, dtype_kwargs={"time_zone_agnostic": True})


class ReposContract(pa.DataFrameModel):
    """SCD Type 1 dimension: one unique row per GitHub repository."""

    id: int = pa.Field(nullable=False, unique=True, ge=0)
    name: str = pa.Field(nullable=False)
    url: str = pa.Field(nullable=False)
    first_seen_at: DateTime = pa.Field(nullable=False, dtype_kwargs={"time_zone_agnostic": True})
    updated_at: DateTime = pa.Field(nullable=False, dtype_kwargs={"time_zone_agnostic": True})


class OrgsContract(pa.DataFrameModel):
    """SCD Type 1 dimension: one unique row per GitHub organization."""

    id: int = pa.Field(nullable=False, unique=True, ge=0)
    login: str = pa.Field(nullable=False)
    gravatar_id: str = pa.Field(nullable=True)
    url: str = pa.Field(nullable=False)
    avatar_url: str = pa.Field(nullable=True)
    first_seen_at: DateTime = pa.Field(nullable=False, dtype_kwargs={"time_zone_agnostic": True})
    updated_at: DateTime = pa.Field(nullable=False, dtype_kwargs={"time_zone_agnostic": True})
