from cProfile import run
import os
import time
from dotenv import load_dotenv

import adaption
from adaption import Adaption

# Load ENV variables from .env file
load_dotenv()

# Adaptation API Client
client = Adaption(api_key=os.getenv("ADAPTION_API_KEY"))

def main():
    print(f"Adaption version: {adaption.__version__}")

    dataset = client.datasets.create(
    source={
        "url": "https://huggingface.co/datasets/tatsu-lab/alpaca",
        "files": [
            "data/train-00000-of-00001-a09b74b3ef9c3b56.parquet"
        ],
    },
    )
    dataset_id = dataset.dataset_id
    print(f"Dataset ID: {dataset_id}")

    count = 1
    while True:
        print(f"[{count}] Loading dataset...")
        count += 1
        status = client.datasets.get_status(dataset_id)
        if status.status == "failed":
            err = status.error_data
            msg = (err and err.message) or "unknown error"
            raise RuntimeError(f"Ingestion failed: {msg}")
        if status.row_count is not None:
            print(f"Imported {status.row_count} rows")
            break
        time.sleep(5)

    column_mapping = {
    "prompt": "instruction",
    "completion": "output",
    "context": ["input"],
    }

    job_specification = {"max_rows": 500}

    estimate = client.datasets.adapt(
        dataset_id,
        column_mapping=column_mapping,
        job_specification=job_specification,
        estimate=True,
    )

    print(f"Estimated credits: {estimate.estimated_credits_consumed}")

    run = client.datasets.adapt(
    dataset_id,
    column_mapping=column_mapping,
    job_specification=job_specification,
    )

    print(f"Run started: {run.run_id}")

    status = client.datasets.wait_for_completion(dataset_id, timeout=3600)
    if status.status == "failed":
        raise RuntimeError(f"Adaptive Data failed: {status.error_data}")

    print(status.status)

    client.datasets.download(dataset_id, file_format="parquet").write_to_file(
        "adapted-alpaca.tar.gz"
    )

if __name__ == "__main__":
    main()