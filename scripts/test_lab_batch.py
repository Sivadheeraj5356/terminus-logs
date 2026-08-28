"""Tests for batch-01 selection, classification, and lab ingest isolation."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ingest_lab_jobs import apply_to_corpus, classify_batch  # noqa: E402
from lab_common import (  # noqa: E402
    BATCH_01_JSONL,
    CATEGORY_ORDER,
    PREFERRED_LANGS,
    classify,
    collect_trials,
    load_jsonl,
    summarize_trials,
)
from select_lab_batch import select  # noqa: E402


class BatchSelectionTests(unittest.TestCase):
    def test_freeze_matches_selector_and_coverage_rules(self):
        frozen = load_jsonl(BATCH_01_JSONL)
        computed = select()
        self.assertEqual([r["slug"] for r in frozen], [r["slug"] for r in computed])
        slugs = [r["slug"] for r in frozen]
        uuids = [r["uuid"] for r in frozen]
        self.assertEqual(len(frozen), 10)
        self.assertEqual(len(set(slugs)), 10)
        self.assertEqual(len(set(uuids)), 10)
        cats = [r["category"] for r in frozen]
        self.assertEqual(set(cats), set(CATEGORY_ORDER))
        self.assertEqual(cats.count("scientific-computing"), 2)
        self.assertEqual(cats.count("security"), 2)
        self.assertEqual(cats.count("debugging"), 1)
        langs = [r["primary_language"] for r in frozen]
        self.assertGreaterEqual(len(set(langs)), 8)
        for lang in PREFERRED_LANGS:
            self.assertIn(lang, langs)


class ClassifyTests(unittest.TestCase):
    def test_reward_one_is_solved(self):
        self.assertEqual(classify({"verifier_result": {"rewards": {"reward": 1.0}}}), "solved")

    def test_reward_zero_is_valid_fail(self):
        self.assertEqual(classify({"verifier_result": {"rewards": {"reward": 0.0}}}), "valid_fail")

    def test_timeout_is_not_stump(self):
        result = {
            "verifier_result": {"rewards": {"reward": 0.0}},
            "exception_info": {"exception_type": "AgentTimeoutError", "exception_message": "timed out"},
        }
        self.assertEqual(classify(result), "timeout")

    def test_auth_is_infra(self):
        result = {
            "exception_info": {
                "exception_type": "AuthenticationError",
                "exception_message": "401 invalid_api_key",
            }
        }
        self.assertEqual(classify(result), "infra_error")

    def test_stump_excludes_timeout_and_infra(self):
        rows = [
            {"classification": "valid_fail", "model": "a", "agent": "", "trial_dir": "1", "agent_summary": "x"},
            {"classification": "timeout", "model": "a", "agent": "", "trial_dir": "2", "agent_summary": "x"},
            {"classification": "infra_error", "model": "a", "agent": "", "trial_dir": "3", "agent_summary": "x"},
            {"classification": "solved", "model": "a", "agent": "", "trial_dir": "4", "agent_summary": "x"},
        ]
        summary = summarize_trials(rows)
        self.assertEqual(summary["completed_trials"], 2)
        self.assertEqual(summary["stump_pct"], 50.0)
        self.assertEqual(summary["timeout"], 1)
        self.assertEqual(summary["infra_error"], 1)


def _write_result(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class IngestIsolationTests(unittest.TestCase):
    def test_only_batch_slugs_light_up_and_stray_jobs_are_ignored(self):
        batch = load_jsonl(BATCH_01_JSONL)
        target = batch[0]["slug"]
        outsider = "this-slug-is-not-in-batch-01-and-must-stay-dark"
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp)
            _write_result(
                jobs / "j1" / f"{target}__terminus-2__1" / "result.json",
                {
                    "task_name": target,
                    "trial_name": "t1",
                    "verifier_result": {"rewards": {"reward": 0.0}},
                    "agent_info": {"name": "terminus-2"},
                    "config": {"agent": {"model_name": "anthropic/claude-opus-5"}},
                },
            )
            _write_result(
                jobs / "j1" / f"{target}__terminus-2__2" / "result.json",
                {
                    "task_name": target,
                    "trial_name": "t2",
                    "exception_info": {
                        "exception_type": "AgentTimeoutError",
                        "exception_message": "timed out",
                    },
                    "agent_info": {"name": "terminus-2"},
                    "config": {"agent": {"model_name": "anthropic/claude-opus-5"}},
                },
            )
            _write_result(
                jobs / "j2" / f"{outsider}__terminus-2__1" / "result.json",
                {
                    "task_name": outsider,
                    "trial_name": "t1",
                    "verifier_result": {"rewards": {"reward": 1.0}},
                    "agent_info": {"name": "terminus-2"},
                    "config": {"agent": {"model_name": "openai/gpt-5.6-sol"}},
                },
            )
            trials = collect_trials(jobs)
            reports = classify_batch(batch, trials, jobs)
            by_slug = {r["slug"]: r for r in reports}
            self.assertTrue(by_slug[target]["has_jobs"])
            self.assertEqual(by_slug[target]["local"]["valid_fail"], 1)
            self.assertEqual(by_slug[target]["local"]["timeout"], 1)
            self.assertEqual(by_slug[target]["local"]["stump_pct"], 100.0)
            for row in reports:
                if row["slug"] != target:
                    self.assertFalse(row["has_jobs"])

            corpus = {
                "lab": {"honesty": {}, "name": "x"},
                "tasks": [
                    {
                        "slug": target,
                        "name": "in batch",
                        "category": "debugging",
                        "languages": ["Rust"],
                    },
                    {
                        "slug": outsider,
                        "name": "stray",
                        "category": "games",
                        "languages": ["Go"],
                    },
                    {
                        "slug": batch[1]["slug"],
                        "name": "batch no jobs",
                        "category": "security",
                        "languages": ["C"],
                    },
                ],
            }
            apply_to_corpus(corpus, batch, reports)
            by_task = {t["slug"]: t for t in corpus["tasks"]}
            self.assertTrue(by_task[target]["measured"])
            self.assertEqual(by_task[target]["rollouts"]["status"], "measured")
            self.assertFalse(by_task[outsider]["measured"])
            self.assertEqual(by_task[outsider]["rollouts"]["status"], "not_run")
            self.assertIsNone(by_task[outsider]["stump_pct"])
            self.assertFalse(by_task[batch[1]["slug"]]["measured"])
            self.assertEqual(corpus["lab"]["measured_size"], 1)
            self.assertNotIn(outsider, corpus["lab"]["measured_slugs"])


class LabUiIdentityTests(unittest.TestCase):
    def test_static_lab_keeps_applied_work_identity(self):
        html = (ROOT / "lab" / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "lab" / "lab.css").read_text(encoding="utf-8")
        js = (ROOT / "lab" / "lab.js").read_text(encoding="utf-8")
        self.assertIn("Applied Work Worlds Lab", html)
        self.assertIn("data-nav=\"overview\"", html)
        self.assertIn("data-nav=\"tasks\"", html)
        self.assertIn("data-nav=\"agents\"", html)
        self.assertNotIn("Senior SWE-Bench", html)
        self.assertNotIn("snorkel.ai", html.lower())
        self.assertIn("#fdfbf7", css.lower())
        self.assertIn("#7b6cf0", css.lower())
        self.assertNotIn("#b5471a", css)
        self.assertIn("not run", js.lower())
        self.assertNotIn("8/8 solved", js)
        self.assertIn("https://github.com/Sivadheeraj5356/terminus-logs", html)

    def test_enrich_overview_stats_uses_our_instruction_files(self):
        from build_lab_corpus import enrich_overview_stats

        corpus = {
            "lab": {"harness": {}, "batch_01_slugs": []},
            "tasks": [
                {
                    "slug": "repair-the-pendulum-motion-solver",
                    "name": "Pendulum",
                    "batch": 1,
                    "languages": ["Python"],
                }
            ],
        }
        enrich_overview_stats(corpus)
        chars = corpus["tasks"][0]["instruction_chars"]
        self.assertGreater(chars, 500)
        self.assertEqual(corpus["lab"]["charts"]["copied_other_labs"], False)
        self.assertGreaterEqual(corpus["lab"]["charts"]["instruction_length"]["n"], 1)
        self.assertTrue(corpus["lab"]["instruction_previews"])


if __name__ == "__main__":
    unittest.main()
