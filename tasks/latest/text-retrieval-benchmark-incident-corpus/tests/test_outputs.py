"""Verifier pytest suite.

Wraps the vitest (unit) and Playwright (E2E) suites via subprocess so the top-level
verifier is Python + pytest, per the Harbor task framework. The underlying suites
still live in tests/unit/*.spec.ts and tests/e2e/*.spec.ts — pytest here just
invokes them and surfaces exit codes.
"""

from __future__ import annotations

import os
import subprocess


WORK_DIR = "/tmp/ui-task-tests"
NODE_MODULES = "/opt/ui-task-tests/node_modules"


def _npm_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{NODE_MODULES}/.bin:{env.get('PATH', '')}"
    env["CI"] = "1"  # non-interactive playwright output
    return env


def _run_npm_script(script: str, timeout_sec: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["npm", "run", script],
        cwd=WORK_DIR,
        env=_npm_env(),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )


def test_vitest_unit_suite_passes():
    """All unit tests in tests/unit/*.spec.ts must pass under vitest."""
    result = _run_npm_script("test")
    if result.returncode != 0:
        raise AssertionError(
            f"vitest unit suite failed (exit {result.returncode})\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )


def test_playwright_e2e_suite_passes():
    """All E2E tests in tests/e2e/*.spec.ts must pass under Playwright."""
    result = _run_npm_script("test:e2e")
    if result.returncode != 0:
        raise AssertionError(
            f"playwright E2E suite failed (exit {result.returncode})\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )


def test_random_transcript_excerpts_surface_matching_content():
    """Anti-hardcoding check: sample random 6-word excerpts from the incident
    transcript at TEST TIME and verify the /query endpoint surfaces matching
    content in its top-3 passages. A real TF-IDF/BM25 index over the transcript
    will always pass this; a shortcut backend that hardcodes responses for the
    visible verifier questions cannot anticipate random inputs.
    """
    import json
    import random
    import urllib.request

    transcript_path = "/app/data/incident_transcript.txt"
    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript = f.read()
    words = [w for w in transcript.split() if len(w) > 0]
    assert len(words) > 1000, f"transcript looks too short ({len(words)} words)"

    trials = 6
    required_successes = 5  # allow one occasional near-miss without flaking
    successes = 0
    misses = []

    for i in range(trials):
        # Random 6-word window; avoid edges.
        start = random.randint(100, len(words) - 100)
        excerpt = words[start:start + 6]
        query = " ".join(excerpt)
        req = urllib.request.Request(
            "http://localhost:8000/query",
            data=json.dumps({"question": query, "top_k": 3}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
        combined = " ".join(p["text"].lower() for p in body["passages"])
        # A real retriever should surface most of the excerpt's substantive
        # words in the top-3 passages (window itself is a snippet of the doc).
        content_words = [w.lower() for w in excerpt if len(w) > 4]
        if not content_words:
            successes += 1
            continue
        hits = sum(1 for w in content_words if w in combined)
        threshold = max(1, len(content_words) // 2)
        if hits >= threshold:
            successes += 1
        else:
            misses.append((query, hits, len(content_words)))

    if successes < required_successes:
        detail = "\n".join(
            f"  '{q}' → {h}/{total} content words in top-3"
            for q, h, total in misses
        )
        raise AssertionError(
            f"only {successes}/{trials} random-excerpt queries surfaced content; "
            f"this suggests retrieval isn't running against the actual transcript.\n"
            f"Misses:\n{detail}"
        )
