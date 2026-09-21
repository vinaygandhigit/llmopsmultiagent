"""Evaluators for the automated eval pipeline (Evals gap #2): faithfulness,
answer relevance, and context precision.

- faithfulness: reuses the same LLM-as-judge as production quality
  monitoring (app.quality.judge_faithfulness) - is every claim in the answer
  grounded in the tool-output context?
- answer_relevance: a second, differently-prompted LLM-as-judge - does the
  answer actually address the question asked, independent of whether the
  facts are correct (that's faithfulness's job)?
- context_precision: a deterministic, no-LLM-call proxy - did the answer
  surface the specific facts we know are correct for this case, from the
  golden dataset's `expected_keywords`? Cheap and exact; catches "grounded
  in *a* real record but the wrong customer's" failures a fuzzy LLM judge
  can miss.

Each function follows LangSmith's evaluator signature: `(run, example) -> dict`,
called by evals/run_evals.py via `langsmith.evaluate()`.
"""
from __future__ import annotations

import json
import re

from langchain_anthropic import ChatAnthropic
from langsmith.schemas import Example, Run

from app.config import JUDGE_MODEL
from app.quality import judge_faithfulness

_relevance_llm: ChatAnthropic | None = None


def _get_relevance_llm() -> ChatAnthropic:
    global _relevance_llm
    if _relevance_llm is None:
        _relevance_llm = ChatAnthropic(model=JUDGE_MODEL, temperature=0)
    return _relevance_llm


_RELEVANCE_PROMPT = """You are judging whether an assistant's ANSWER actually
addresses the customer's QUESTION - regardless of whether the facts in it are
correct (that is scored separately). An answer that is factually grounded but
doesn't address what was asked, or that refuses/deflects without reason,
should score low.

QUESTION:
{question}

ANSWER:
{answer}

Respond with ONLY a JSON object, no other text:
{{"score": <float 0.0-1.0, 1.0 = fully addresses the question>, "rationale": "<one sentence>"}}
"""


def _parse_score(raw: str) -> tuple[float, str]:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    payload = json.loads(match.group(0) if match else raw)
    score = max(0.0, min(1.0, float(payload.get("score", 0.0))))
    return score, str(payload.get("rationale", ""))


def faithfulness_evaluator(run: Run, example: Example | None) -> dict:
    outputs = run.outputs or {}
    inputs = (example.inputs if example else None) or {}
    answer = outputs.get("answer", "")
    context = outputs.get("context", "")
    question = inputs.get("question", "")

    result = judge_faithfulness(question, context, answer)
    if result is None:
        return {"key": "faithfulness", "score": None, "comment": "judge call failed"}
    score, rationale = result
    return {"key": "faithfulness", "score": score, "comment": rationale}


def answer_relevance_evaluator(run: Run, example: Example | None) -> dict:
    outputs = run.outputs or {}
    inputs = (example.inputs if example else None) or {}
    answer = outputs.get("answer", "")
    question = inputs.get("question", "")

    try:
        response = _get_relevance_llm().invoke(_RELEVANCE_PROMPT.format(question=question, answer=answer))
        score, rationale = _parse_score(str(response.content))
        return {"key": "answer_relevance", "score": score, "comment": rationale}
    except Exception as exc:
        return {"key": "answer_relevance", "score": None, "comment": f"judge call failed: {exc}"}


def context_precision_evaluator(run: Run, example: Example | None) -> dict:
    outputs = run.outputs or {}
    reference_outputs = (example.outputs if example else None) or {}
    answer = str(outputs.get("answer", "")).lower()
    expected_keywords = reference_outputs.get("expected_keywords", [])

    if not expected_keywords:
        return {"key": "context_precision", "score": None, "comment": "no expected_keywords on example"}

    hits = [kw for kw in expected_keywords if kw.lower() in answer]
    score = len(hits) / len(expected_keywords)
    missing = sorted(set(expected_keywords) - set(hits))
    comment = "all expected facts present" if not missing else f"missing: {missing}"
    return {"key": "context_precision", "score": score, "comment": comment}


ALL_EVALUATORS = [faithfulness_evaluator, answer_relevance_evaluator, context_precision_evaluator]