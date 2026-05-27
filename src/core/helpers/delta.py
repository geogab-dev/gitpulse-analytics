"""
Delta Lake helpers: upsert (SCD Type 1) and append-only writes.
"""

from __future__ import annotations

from deltalake import DeltaTable, write_deltalake
from deltalake.exceptions import TableNotFoundError
from polars import DataFrame

from core.helpers.logger import cyan, get_logger, magenta
from core.helpers.s3 import S3_STORAGE_OPTIONS


def upsert_delta(
    df: DataFrame,
    target: str,
    merge_predicate: str,
    update_predicate: str,
    partition_by: list[str] | None = None,
    insert_only_columns: list[str] | None = None,
) -> None:
    """
    Upsert *df* into a Delta table (SCD Type 1), creating it if missing.

    On first run the table is created via `write_deltalake(mode="overwrite")`.
    Subsequent runs merge matched rows (when *update_predicate* is true) and
    insert unmatched rows.

    Columns listed in *insert_only_columns* (e.g. `first_seen_at`) are set
    only on INSERT. On UPDATE the target (original) value is preserved.
    """
    logger = get_logger(__name__)

    insert_only: set[str] = set(insert_only_columns or [])

    try:
        dt = DeltaTable(target, storage_options=S3_STORAGE_OPTIONS)
    except TableNotFoundError:
        write_deltalake(
            target,
            df.to_arrow(),
            storage_options=S3_STORAGE_OPTIONS,
            mode="overwrite",
            partition_by=partition_by or [],
        )

        logger.info("created %s rows into %s (new table)", magenta(len(df)), cyan(target))
        return

    # build update mapping: source columns overwrite target, insert-only preserved
    update_updates: dict[str, str] = {
        col: f"source.{col}"
        for col in df.columns
        if col not in insert_only and col not in (partition_by or [])
    }
    for col in insert_only:
        update_updates[col] = f"target.{col}"

    (
        dt.merge(
            source=df.to_arrow(),
            predicate=merge_predicate,
            source_alias="source",
            target_alias="target",
        )
        .when_matched_update(predicate=update_predicate, updates=update_updates)
        .when_not_matched_insert_all()
        .execute()
    )

    logger.info("merged %s rows into %s", magenta(len(df)), cyan(target))


def append_delta(
    df: DataFrame,
    target: str,
    partition_by: list[str] | None = None,
) -> None:
    """
    Append *df* to a Delta table, creating it if it doesn't exist.

    Designed for immutable fact tables (e.g. GitHub events). Uses
    `write_deltalake(mode="append")` no merge, no predicate.
    """
    logger = get_logger(__name__)

    write_deltalake(
        target,
        df.to_arrow(),
        storage_options=S3_STORAGE_OPTIONS,
        mode="append",
        partition_by=partition_by or [],
    )

    logger.info("appended %s rows into %s", magenta(len(df)), cyan(target))


__all__: list[str] = ["upsert_delta", "append_delta"]
