"""
Entrypoint: execute Prefect flows directly (no deployment).

Usage:
    uv run main.py           # execute bronze + silver (default)
    uv run main.py bronze    # execute only bronze
    uv run main.py silver    # execute only silver
"""

import sys

from pipelines.bronze_flow import bronze_ingestion_flow
from pipelines.silver_flow import silver_transform_flow


def serve_all() -> None:
    """Execute both bronze and silver flows sequentially."""
    bronze_ingestion_flow(days=1)
    silver_transform_flow(batch_size=12)


def serve_bronze() -> None:
    """Execute only the bronze ingestion flow."""
    bronze_ingestion_flow(days=1)


def serve_silver() -> None:
    """Execute only the silver transformation flow."""
    silver_transform_flow(batch_size=12)


if __name__ == "__main__":
    arg: str = sys.argv[1] if len(sys.argv) > 1 else ""

    match arg:
        case "bronze":
            serve_bronze()
        case "silver":
            serve_silver()
        case _:
            serve_all()
