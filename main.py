"""
Entrypoint: serves all Prefect flows as deployments.

Usage:
    uv run main.py                    # serve all flows
    uv run main.py bronze             # serve only the bronze flow
"""

import sys

from pipelines.bronze_flow import bronze_ingestion_flow


def serve_all() -> None:
    """Serve all available flows for deployment."""
    bronze_ingestion_flow.serve(name="bronze-ingestion-deployment")


def serve_bronze() -> None:
    """Serve only the bronze ingestion flow."""
    bronze_ingestion_flow.serve(name="bronze-ingestion-deployment")


if __name__ == "__main__":
    arg: str = sys.argv[1] if len(sys.argv) > 1 else ""

    match arg:
        case "bronze":
            serve_bronze()
