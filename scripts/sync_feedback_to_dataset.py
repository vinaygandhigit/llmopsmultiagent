"""Close the feedback loop (gap #4): pull production runs that got negative
end-user feedback (submitted via POST /feedback) into a regression eval
dataset, so the next prompt iteration is informed by real production
failures instead of only the original golden set in evals/dataset.py. This
is the "observe -> evaluate" link in deploy -> observe -> evaluate ->
improve -> redeploy.

Usage (from the project root):

    python -m scripts.sync_feedback_to_dataset
    python -m scripts.sync_feedback_to_dataset --threshold -0.5

For each negative-feedback run_id, fetches the run's actual inputs/outputs
from LangSmith (so the case reflects what the customer really asked, not a
guess) and appends it to a LangSmith dataset flagged `needs_human_review` -
a human should confirm or correct the expected answer before this dataset
is trusted as a CI gate the way evals/run_evals.py's golden set is.
"""
from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from langsmith import Client

from app.feedback_store import negative_feedback_runs

DEFAULT_DATASET_NAME = "multiagentbank-regression"


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync negative-feedback runs into a regression eval dataset.")
    parser.add_argument("--threshold", type=float, default=0, help="Feedback score below this counts as negative.")
    parser.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME)
    args = parser.parse_args()

    runs = negative_feedback_runs(threshold=args.threshold)
    if not runs:
        print("No negative-feedback runs found locally. Nothing to sync.")
        return 0

    client = Client()
    if not client.has_dataset(dataset_name=args.dataset_name):
        client.create_dataset(
            dataset_name=args.dataset_name,
            description=(
                "Production runs that received negative user feedback - candidates "
                "for prompt/eval iteration. Review before trusting as ground truth."
            ),
        )

    existing_source_run_ids = {
        (example.metadata or {}).get("source_run_id")
        for example in client.list_examples(dataset_name=args.dataset_name)
    }

    synced = 0
    for row in runs:
        run_id = row["run_id"]
        if run_id in existing_source_run_ids:
            continue
        try:
            run = client.read_run(run_id)
        except Exception as exc:
            print(f"Skipping run {run_id}: could not fetch from LangSmith ({exc})")
            continue

        client.create_example(
            dataset_name=args.dataset_name,
            inputs=run.inputs,
            outputs=run.outputs,
            metadata={
                "source_run_id": run_id,
                "agent": row["agent"],
                "feedback_score": row["score"],
                "feedback_comment": row["comment"],
                "needs_human_review": True,
            },
        )
        synced += 1

    print(
        f"Synced {synced} new example(s) into dataset '{args.dataset_name}' "
        f"(out of {len(runs)} negative-feedback runs on file)."
    )
    print("Review each example's outputs in the LangSmith UI and correct them before using this as a CI gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())