import pandera.polars as pa
import polars as pl

# schema definition based on github event types, see:
# https://docs.github.com/en/rest/using-the-rest-api/github-event-types
BRONZE_EVENTS_SCHEMA: pl.Schema = pl.Schema(
    # all fields are defined as string for simplicity and performance
    # actor, repo, payload and org are structs and will be parsed in the silver layer
    schema={
        "id": pl.String,
        "type": pl.String,
        "actor": pl.String,
        "repo": pl.String,
        "payload": pl.String,
        "public": pl.Boolean,
        "created_at": pl.String,
        "org": pl.String,
    }
)


class BronzeEventsContract(pa.DataFrameModel):
    """
    Pandera contract for bronze layer events.

    Validates only essential fields: id, type, and created_at must be present
    and non-null. The type field is not constrained to known event types so
    new GitHub event types don't break ingestion.
    """

    id: str = pa.Field(nullable=False)
    type: str = pa.Field(nullable=False)
    created_at: str = pa.Field(nullable=False)
