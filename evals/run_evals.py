"""Automated eval pipeline (Evals gap #2). Run from the project root with:

    python -m evals.run_evals
    python -m evals.run_evals --agent account_agent

Syncs evals/dataset.py's golden cases into a LangSmith dataset, runs each
case through the *live* agent (using whatever prompt version is currently
promoted in app/prompts/manifest.json - this always evaluates what would
actually run in prod, not a hardcoded snapshot), scores every response with
the three evaluators in evals/evaluators.py (faithfulness, answer_relevance,
context_precision), and prints a pass/fail summary per agent. Exits non-zero
if any agent's overall score is below PASS_THRESHOLD, so it's usable as a CI
gate before promoting a prompt/model change (see evals/ab_test.py for the
before/after comparison version of this workflow).
"""
from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from langsmith import Client
from langsmith.evaluation import evaluate

from app.agent import run_account_agent, run_multi_agent, run_service_agent, run_transaction_agent
from evals.dataset import GOLDEN_DATASET
from evals.evaluators import ALL_EVALUATORS

DATASET_NAME = "multiagentbank-golden"
PASS_THRESHOLD = 0.7  # average score across evaluators & examples, per agent

_TARGET_FNS = {
    "account_agent": run_account_agent,
    "transaction_agent": run_transaction_agent,
    "service_agent": run_service_agent,
    "bank_supervisor": run_multi_agent,
}


def ensure_dataset(client: Client, dataset_name: str) -> None:
    """Make the LangSmith dataset match evals/dataset.py exactly.

    Wipe-and-recreate is fine at this dataset's size and keeps
    evals/dataset.py as the single source of truth instead of two things
    (the file and the LangSmith UI) drifting apart.
    """
    if client.has_dataset(dataset_name=dataset_name):
        for example in list(client.list_examples(dataset_name=dataset_name)):
            client.delete_example(example.id)
    else:
        client.create_dataset(
            dataset_name=dataset_name,
            description="Golden eval set for the multiagent bank assistant.",
        )

    for case in GOLDEN_DATASET:
        client.create_example(
            dataset_name=dataset_name,
            inputs={"question": case["question"]},
            outputs={"reference": case["reference"], "expected_keywords": case["expected_keywords"]},
            metadata={"id": case["id"], "agent": case["agent"]},
        )


def make_target(agent_key: str):
    run_fn = _TARGET_FNS[agent_key]

    def target(inputs: dict) -> dict:
        result = run_fn(inputs["question"], tenant_id="eval")
        return {"answer": result.reply, "context": result.context}

    target.__name__ = f"{agent_key}_target"
    return target


def summarize(agent_key: str, results) -> dict:
    scores_by_key: dict[str, list[float]] = {}
    for row in results:
        for eval_result in row["evaluation_results"]["results"]:
            if eval_result.score is None:
                continue
            scores_by_key.setdefault(eval_result.key, []).append(eval_result.score)

    averages = {key: sum(vals) / len(vals) for key, vals in scores_by_key.items() if vals}
    overall = sum(averages.values()) / len(averages) if averages else 0.0
    return {"agent": agent_key, "averages": averages, "overall": overall}


def run_for_agent(client: Client, dataset_name: str, agent_key: str, experiment_prefix: str | None = None) -> dict:
    examples = [
        ex for ex in client.list_examples(dataset_name=dataset_name)
        if (ex.metadata or {}).get("agent") == agent_key
    ]
    if not examples:
        return {"agent": agent_key, "averages": {}, "overall": 0.0, "note": "no examples for this agent"}

    results = evaluate(
        make_target(agent_key),
        data=examples,
        evaluators=ALL_EVALUATORS,
        experiment_prefix=experiment_prefix or f"{agent_key}-eval",
        client=client,
        metadata={"agent": agent_key},
    )
    return summarize(agent_key, results)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the automated eval pipeline against LangSmith.")
    parser.add_argument("--agent", choices=list(_TARGET_FNS), default=None, help="Evaluate a single agent only.")
    parser.add_argument("--dataset-name", default=DATASET_NAME)
    args = parser.parse_args()

    client = Client()
    ensure_dataset(client, args.dataset_name)

    agent_keys = [args.agent] if args.agent else list(_TARGET_FNS)
    summaries = [run_for_agent(client, args.dataset_name, agent_key) for agent_key in agent_keys]

    print("\n=== Eval summary ===")
    all_passed = True
    for summary in summaries:
        passed = summary["overall"] >= PASS_THRESHOLD
        all_passed = all_passed and passed
        status = "PASS" if passed else "FAIL"
        formatted_averages = {k: round(v, 2) for k, v in summary["averages"].items()}
        print(f"[{status}] {summary['agent']}: overall={summary['overall']:.2f} {formatted_averages}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())