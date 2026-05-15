from multiprocessing import cpu_count

from prefect import flow, task

from core.ingestion import run_ingestion


@task(log_prints=True)
def prefect_task(days: int, max_workers: int) -> None:
    run_ingestion(days=days, max_workers=max_workers)


@flow(name="prefect-test-flow", log_prints=True)
def prefect_main_flow(days: int, max_workers: int) -> None:
    prefect_task(days=days, max_workers=max_workers)


if __name__ == "__main__":
    # serve the flow for deployment
    prefect_main_flow(days=1, max_workers=cpu_count())
