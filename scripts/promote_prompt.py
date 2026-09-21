"""Promote or roll back a prompt version for one agent (Prompt versioning
gap #3: "rollback capability when a prompt change degrades quality").

Usage (from the project root):

    python -m scripts.promote_prompt account_agent v2
    python -m scripts.promote_prompt account_agent --rollback

Updates app/prompts/manifest.json - the single source of truth that
app.agent.get_agent()/get_supervisor() re-read on every request, so this
takes effect immediately with no app restart or redeploy - and appends an
audit entry to app/prompts/history.jsonl (see GET /prompts to inspect it).

Run evals/run_evals.py or evals/ab_test.py first to justify the promotion
with numbers; this script doesn't gate on eval scores itself, since a
rollback specifically needs to work even when evals are the thing failing.
"""
from __future__ import annotations

import argparse
import getpass
import sys

from app.prompts import available_versions, current_version, promote, rollback


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote or roll back an agent's production prompt version.")
    parser.add_argument("agent", help="e.g. account_agent, transaction_agent, service_agent, bank_supervisor")
    parser.add_argument("version", nargs="?", help="Version to promote to, e.g. v2. Omit with --rollback.")
    parser.add_argument(
        "--rollback", action="store_true",
        help="Revert to the version this agent had before its last promotion.",
    )
    parser.add_argument("--actor", default=None, help="Who is making this change (defaults to the OS username).")
    args = parser.parse_args()

    actor = args.actor or getpass.getuser()

    if args.rollback:
        if args.version:
            parser.error("--rollback doesn't take a version argument.")
        try:
            entry = rollback(args.agent, actor=actor)
        except RuntimeError as exc:
            print(f"Rollback failed: {exc}", file=sys.stderr)
            return 1
        print(f"Rolled back {args.agent}: {entry['from_version']} -> {entry['to_version']} (actor={actor})")
        return 0

    if not args.version:
        parser.error("Provide a version to promote, or use --rollback.")

    before = current_version(args.agent)
    if args.version not in available_versions(args.agent):
        print(
            f"No prompt text file for '{args.agent}' version '{args.version}'. "
            f"Available: {available_versions(args.agent)}",
            file=sys.stderr,
        )
        return 1

    promote(args.agent, args.version, actor=actor)
    print(f"Promoted {args.agent}: {before} -> {args.version} (actor={actor})")
    return 0


if __name__ == "__main__":
    sys.exit(main())