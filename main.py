import time

from prefect import flow, task


@task(log_prints=True)
def prefect_task(fruit: str):
    print(f"Starting task with fruit: {fruit}")
    time.sleep(30)  # simulate task running
    return f"Task completed with fruit: {fruit}"


@flow(name="prefect-test-flow", log_prints=True)
def prefect_main_flow():
    print("Starting main flow")
    result = prefect_task(fruit="apple")
    print(f"Result: {result}")


if __name__ == "__main__":
    # serve the flow for deployment
    prefect_main_flow.serve(name="test-deployment-local")
