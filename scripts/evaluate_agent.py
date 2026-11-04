"""Evaluates the agent against a fixed set of cases and writes a Markdown report.

Each case checks which tools the agent used and what the answer must (or must not)
contain. Results are cached per case, so a run can be split in parts (useful with free
tier quotas) and the report always covers every case run so far.

Usage (from the project root, with the .env configured):
    python scripts/evaluate_agent.py                         # every case
    python scripts/evaluate_agent.py --only price_lookup,budget_search
    python scripts/evaluate_agent.py --report-only           # rebuild the report from cache
"""

import argparse
import json
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver

from emporio_agent.config import Settings
from emporio_agent.container import start_chat_session
from emporio_agent.domain.text import normalize_text

CASES_FILE = Path("evals/cases.json")
CACHE_DIR = Path(".memory/eval_results")
REPORT_FILE = Path("evals/report.md")


@dataclass
class CaseResult:
    case_id: str
    goal: str
    model: str
    passed: bool
    tools_used: list[str]
    failures: list[str] = field(default_factory=list)
    transcript: list[tuple[str, str]] = field(default_factory=list)


def check_answer(case: dict[str, Any], tools_used: list[str], replies: list[str]) -> list[str]:
    """Compares what the agent did with what the case expects.

    Text checks ignore accents and case. "must_contain" is checked on the last answer,
    "must_not_contain" on every answer of the case.

    Args:
        case: Case from evals/cases.json.
        tools_used: Tools called during the whole case.
        replies: Agent answers, one per customer message.

    Returns:
        A list of failure reasons, empty when the case passed.
    """
    failures = []
    expected_tools = case.get("expect_tools", [])
    if expected_tools and not set(expected_tools) & set(tools_used):
        failures.append(f"expected one of the tools {expected_tools}, used {tools_used or 'none'}")
    if case.get("expect_no_tools") and tools_used:
        failures.append(f"expected no tools, used {tools_used}")

    last_answer = normalize_text(replies[-1]) if replies else ""
    all_answers = normalize_text(" ".join(replies))
    for text in case.get("must_contain", []):
        if normalize_text(text) not in last_answer:
            failures.append(f"answer is missing '{text}'")
    for text in case.get("must_not_contain", []):
        if normalize_text(text) in all_answers:
            failures.append(f"answer should not contain '{text}'")
    return failures


def run_case(settings: Settings, case: dict[str, Any]) -> CaseResult:
    """Plays one case in a fresh conversation and checks the result.

    Args:
        settings: Project settings with a working model.
        case: Case from evals/cases.json.

    Returns:
        The result with the transcript.
    """
    session = start_chat_session(settings, f"eval-{case['id']}", checkpointer=InMemorySaver())
    tools_used: list[str] = []
    replies: list[str] = []
    transcript: list[tuple[str, str]] = []
    for message in case["messages"]:
        reply = session.send_message(message)
        tools_used += reply.tools_used
        replies.append(reply.text)
        transcript.append((message, reply.text))
    failures = check_answer(case, tools_used, replies)
    return CaseResult(
        case["id"], case["goal"], settings.model, not failures, tools_used, failures, transcript
    )


def write_report(cases: list[dict[str, Any]]) -> tuple[int, int]:
    """Builds the Markdown report from the cached results of the current cases.

    Args:
        cases: Every case of evals/cases.json.

    Returns:
        Number of cases passed and number of cases with a result.
    """
    results = []
    for case in cases:
        cached = CACHE_DIR / f"{case['id']}.json"
        if cached.is_file():
            results.append(CaseResult(**json.loads(cached.read_text(encoding="utf-8"))))
    passed = sum(result.passed for result in results)
    tool_cases = [
        r
        for r in results
        if any(
            c["id"] == r.case_id and (c.get("expect_tools") or c.get("expect_no_tools"))
            for c in cases
        )
    ]
    tool_ok = sum(not any("tool" in f for f in r.failures) for r in tool_cases)
    models = sorted({result.model for result in results})

    lines = [
        "# Agent evaluation report",
        "",
        f"**Model:** {', '.join(f'`{m}`' for m in models) or 'n/a'} · "
        f"**Generated:** {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"- **Cases passed:** {passed}/{len(results)}",
        f"- **Correct tool choice:** {tool_ok}/{len(tool_cases)}",
        "",
        "| Case | Goal | Tools used | Result |",
        "|---|---|---|---|",
    ]
    for result in results:
        status = "✅ pass" if result.passed else "❌ " + "; ".join(result.failures)
        tools = ", ".join(f"`{name}`" for name in result.tools_used) or "none"
        lines.append(f"| `{result.case_id}` | {result.goal} | {tools} | {status} |")
    lines += ["", "## Transcripts", ""]
    for result in results:
        lines += [f"### `{result.case_id}`", ""]
        for message, answer in result.transcript:
            lines += [f"**Cliente:** {message}", "", f"**Melody:** {answer}", ""]
    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    return passed, len(results)


def main() -> None:
    """Runs the selected cases, caches each result and rewrites the report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="Comma separated case ids to run")
    parser.add_argument("--report-only", action="store_true", help="Only rebuild the report")
    args = parser.parse_args()

    load_dotenv()
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    errors = 0

    if not args.report_only:
        selected = set(args.only.split(",")) if args.only else {case["id"] for case in cases}
        unknown = selected - {case["id"] for case in cases}
        if unknown:
            sys.exit(f"Unknown case ids: {sorted(unknown)}")
        # This is for keeping the tickets of the evaluation out of the real ticket file
        tickets = Path(tempfile.mkdtemp()) / "eval_tickets.jsonl"
        settings = Settings(tickets_file=tickets)
        for case in cases:
            if case["id"] not in selected:
                continue
            print(f"Running {case['id']}...", flush=True)
            try:
                result = run_case(settings, case)
            except Exception as error:
                errors += 1
                print(f"  error: {type(error).__name__}: {str(error)[:200]}")
                continue
            cached = CACHE_DIR / f"{case['id']}.json"
            cached.write_text(json.dumps(asdict(result), ensure_ascii=False), encoding="utf-8")
            print("  pass" if result.passed else f"  FAIL: {result.failures}")

    passed, total = write_report(cases)
    print(f"\n{passed}/{total} cases passed · report saved in {REPORT_FILE}")
    if errors:
        print(f"{errors} case(s) could not run, run them again with --only")
    if errors or passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
