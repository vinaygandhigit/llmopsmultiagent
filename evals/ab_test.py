"""A/B test two prompt versions for one agent before promoting either to
prod (Evals gap #2: "A/B testing prompt versions before promoting to prod").

Usage (from the project root):

    python -m evals.ab_test --agent account_agent --version-a v1 --version-b v2

Runs the golden eval cases for that agent under each prompt version (via
app.prompts.use_version(), which forces the version for this process only -
it never touches the shared manifest.json that governs prod traffic), scores
both with the same evaluators as evals/run_evals.py, and prints a
side-by-side comparison with a promote/keep recommendation. Promotion itself
is a separate, deliberate step - see scripts/promote_prompt.py - so a human
always signs off even when the numbers are clear-cut.
"""
from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from langsmith import Client

from app.prompts import use_version
from evals.run_evals import DATASET_NAME, ensure_dataset, run_for_agent

AB_IMPROVEMENT_THRESHOLD = 0.02  # require >=2% overall score improvement to recommend promoting


def run_version(client: Client, dataset_name: str, agent_key: str, version: str) -> dict:
    use_version(agent_key, version)
    try:
        return run_for_agent(client, dataset_name, agent_key, experiment_prefix=f"{agent_key}-{version}-ab")
    finally:
        use_version(agent_key, None)


def main() -> int:
    parser = argparse.ArgumentParser(description="A/B test two prompt versions for one agent.")
    parser.add_argument("--agent", required=True, help="e.g. account_agent, bank_supervisor")
    parser.add_argument("--version-a", required=True, help="Baseline version, e.g. v1")
    parser.add_argument("--version-b", required=True, help="Candidate version, e.g. v2")
    parser.add_argument("--dataset-name", default=DATASET_NAME)
    args = parser.parse_args()

    client = Client()
    ensure_dataset(client, args.dataset_name)

    result_a = run_version(client, args.dataset_name, args.agent, args.version_a)
    result_b = run_version(client, args.dataset_name, args.agent, args.version_b)

    print(f"\n=== A/B comparison: {args.agent} ===")
    print(f"{args.version_a}: overall={result_a['overall']:.3f} {result_a['averages']}")
    print(f"{args.version_b}: overall={result_b['overall']:.3f} {result_b['averages']}")

    delta = result_b["overall"] - result_a["overall"]
    print(f"\ndelta ({args.version_b} - {args.version_a}): {delta:+.3f}")

    if delta >= AB_IMPROVEMENT_THRESHOLD:
        print(
            f"Recommendation: PROMOTE {args.version_b}. Run:\n"
            f"  python -m scripts.promote_prompt {args.agent} {args.version_b}"
        )
        return 0
    if delta <= -AB_IMPROVEMENT_THRESHOLD:
        print(f"Recommendation: KEEP {args.version_a}. {args.version_b} performs worse.")
        return 1
    print("Recommendation: INCONCLUSIVE - difference is within noise threshold; consider more eval cases.")
    return 1


if __name__ == "__main__":
    sys.exit(main())