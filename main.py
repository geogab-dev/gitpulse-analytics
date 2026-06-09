"""
Entrypoint: execute Prefect flows directly (no deployment).

Usage:
    uv run main.py           # execute bronze + silver + gold (default)
    uv run main.py bronze    # execute only bronze
    uv run main.py silver    # execute only silver
    uv run main.py gold      # execute only gold
"""

import sys

from pipelines.bronze_flow import bronze_ingestion_flow
from pipelines.gold_flow import gold_transform_flow
from pipelines.silver_flow import silver_transform_flow


def serve_all() -> None:
    """Execute bronze, silver, and gold flows sequentially."""
    bronze_ingestion_flow(days=7)
    silver_transform_flow(batch_size=12)
    gold_transform_flow(batch_size_days=2)


def serve_bronze() -> None:
    """Execute only the bronze ingestion flow."""
    bronze_ingestion_flow(days=7)


def serve_silver() -> None:
    """Execute only the silver transformation flow."""
    silver_transform_flow(batch_size=24)


def serve_gold() -> None:
    """Execute only the gold transformation flow."""
    gold_transform_flow(batch_size_days=2)


if __name__ == "__main__":
    arg: str = sys.argv[1] if len(sys.argv) > 1 else ""

    match arg:
        case "bronze":
            serve_bronze()
        case "silver":
            serve_silver()
        case "gold":
            serve_gold()
        case _:
            serve_all()
