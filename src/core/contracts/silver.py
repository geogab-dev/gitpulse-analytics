import pandera.polars as pa
from pandera.engines.polars_engine import DateTime

# event types we track, low-value types excluded:
# (GollumEvent, MemberEvent, DiscussionEvent, PublicEvent)
# no analytical value for our use case
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
]


# actions we extract from event payloads
# some are synthetic: (pushed, created, deleted)
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
    "pushed",
    "created",
    "deleted",
]


class SilverEventsContract(pa.DataFrameModel):
    """Fact table: clean events with validated types, actions, and partition columns."""

    id: int = pa.Field(nullable=False, unique=True, ge=0)
    type: str = pa.Field(nullable=False, isin=KNOWN_EVENT_TYPES)
    action: str = pa.Field(nullable=False, isin=KNOWN_ACTIONS)
    actor_id: int = pa.Field(nullable=False, ge=0)
    repo_id: int = pa.Field(nullable=False, ge=0)
    org_id: int = pa.Field(nullable=True, ge=0)
    public: bool = pa.Field(nullable=False)
    created_at: DateTime = pa.Field(nullable=False, dtype_kwargs={"time_zone_agnostic": True})
    payload: str = pa.Field(nullable=False)

    # hive-style partition columns mirroring the bronze layout
    year: str = pa.Field(nullable=False, str_matches=r"^\d{4}$")
    month: str = pa.Field(nullable=False, str_matches=r"^(0[1-9]|1[0-2])$")
    day: str = pa.Field(nullable=False, str_matches=r"^(0[1-9]|[12]\d|3[01])$")
    hour: str = pa.Field(nullable=False, str_matches=r"^(0\d|1\d|2[0-3])$")


class ActorsContract(pa.DataFrameModel):
    """SCD Type 1 dimension: GitHub users/actors, deduplicated by id."""

    id: int = pa.Field(nullable=False, unique=True, ge=0)
    login: str = pa.Field(nullable=False)
    display_login: str = pa.Field(nullable=True)
    gravatar_id: str = pa.Field(nullable=True)
    url: str = pa.Field(nullable=False)
    avatar_url: str = pa.Field(nullable=True)
    is_bot: bool = pa.Field(nullable=False)
    first_seen_at: DateTime = pa.Field(nullable=False, dtype_kwargs={"time_zone_agnostic": True})
    updated_at: DateTime = pa.Field(nullable=False, dtype_kwargs={"time_zone_agnostic": True})


class ReposContract(pa.DataFrameModel):
    """SCD Type 1 dimension: repositories, deduplicated by id."""

    id: int = pa.Field(nullable=False, unique=True, ge=0)
    name: str = pa.Field(nullable=False)
    url: str = pa.Field(nullable=False)
    first_seen_at: DateTime = pa.Field(nullable=False, dtype_kwargs={"time_zone_agnostic": True})
    updated_at: DateTime = pa.Field(nullable=False, dtype_kwargs={"time_zone_agnostic": True})


class OrgsContract(pa.DataFrameModel):
    """SCD Type 1 dimension: organizations, deduplicated by id."""

    id: int = pa.Field(nullable=False, unique=True, ge=0)
    login: str = pa.Field(nullable=False)
    gravatar_id: str = pa.Field(nullable=True)
    url: str = pa.Field(nullable=False)
    avatar_url: str = pa.Field(nullable=True)
    first_seen_at: DateTime = pa.Field(nullable=False, dtype_kwargs={"time_zone_agnostic": True})
    updated_at: DateTime = pa.Field(nullable=False, dtype_kwargs={"time_zone_agnostic": True})
