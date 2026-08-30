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
    CHEAP_SECOND_FALLBACK,
    CHEAP_SECOND_MODEL,
    OPENAI_SECOND_CANDIDATES,
    PLANNED_ATTEMPTS,
    PREFERRED_LANGS,
    classify,
    collect_trials,
    load_jsonl,
    summarize_trials,
)
from select_lab_batch import select, select_batches_02_05  # noqa: E402


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

    def test_credit_too_low_is_infra(self):
        result = {
            "verifier_result": {"rewards": {"reward": 0.0}},
            "exception_info": {
                "exception_type": "",
                "exception_message": "credit-balance-too-low",
            },
        }
        self.assertEqual(classify(result), "infra_error")

    def test_quota_429_is_infra(self):
        result = {
            "verifier_result": {"rewards": {"reward": 0.0}},
            "exception_info": {
                "exception_type": "",
                "exception_message": "Error code: 429 - insufficient_quota",
            },
        }
        self.assertEqual(classify(result), "infra_error")

    def test_anthropic_credit_balance_message_blocks_measure(self):
        from run_lab_batch import credit_blocked

        blob = (
            'litellm.BadRequestError: AnthropicException - {"type":"error",'
            '"error":{"type":"invalid_request_error","message":'
            '"Your credit balance is too low to access the Anthropic API. '
            'Please go to Plans & Billing to upgrade or purchase credits."}}'
        )
        self.assertEqual(credit_blocked(blob), "credit balance is too low")

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


class LaterBatchSelectionTests(unittest.TestCase):
    def test_five_tens_are_unique_and_debugging_stays_in_batch_01(self):
        frozen = select_batches_02_05()
        self.assertEqual(sorted(frozen), [1, 2, 3, 4, 5])
        slugs = []
        for batch, rows in frozen.items():
            self.assertEqual(len(rows), 10)
            self.assertEqual(len({r["slug"] for r in rows}), 10)
            self.assertTrue(all(r["batch"] == batch for r in rows))
            slugs.extend(r["slug"] for r in rows)
        self.assertEqual(len(slugs), 50)
        self.assertEqual(len(set(slugs)), 50)
        b01 = load_jsonl(BATCH_01_JSONL)
        self.assertEqual([r["slug"] for r in frozen[1]], [r["slug"] for r in b01])
        later_cats = [r["category"] for n in range(2, 6) for r in frozen[n]]
        self.assertNotIn("debugging", later_cats)
        self.assertEqual(PLANNED_ATTEMPTS, 5)


class RemainingKTests(unittest.TestCase):
    def test_credit_infra_does_not_fill_planned_k(self):
        from run_lab_batch import attempted_n, remaining_k

        slug = "booking-slot-merge"
        model = "anthropic/claude-haiku-4-5"
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp)
            _write_result(
                jobs / "j" / f"{slug}__t1" / "result.json",
                {
                    "task_name": slug,
                    "trial_name": "t1",
                    "verifier_result": {"rewards": {"reward": 0.0}},
                    "agent_info": {"name": "terminus-2"},
                    "config": {"agent": {"model_name": model}},
                },
            )
            _write_result(
                jobs / "j" / f"{slug}__t2" / "result.json",
                {
                    "task_name": slug,
                    "trial_name": "t2",
                    "exception_info": {
                        "exception_type": "BadRequestError",
                        "exception_message": "credit balance is too low",
                    },
                    "agent_info": {"name": "terminus-2"},
                    "config": {"agent": {"model_name": model}},
                },
            )
            self.assertEqual(attempted_n(slug, model, jobs), 1)
            self.assertEqual(remaining_k(slug, model, 5, jobs), 4)

    def test_job_credit_blocked_reads_full_log_not_tail(self):
        from run_lab_batch import job_credit_blocked

        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "lab01-haiku-example-fill5"
            job.mkdir()
            (job / "job.log").write_text(
                "credit balance is too low to access the Anthropic API\n" + ("ok trial\n" * 4000),
                encoding="utf-8",
            )
            self.assertEqual(job_credit_blocked(job), "credit balance is too low")

    def test_timeout_counts_as_an_attempt(self):
        from run_lab_batch import attempted_n, remaining_k

        slug = "wildlife-counting-becomes-a-field-planning-game-when-uncerta"
        model = "anthropic/claude-haiku-4-5"
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp)
            _write_result(
                jobs / "j" / f"{slug}__t1" / "result.json",
                {
                    "task_name": slug,
                    "trial_name": "t1",
                    "verifier_result": {"rewards": {"reward": 0.0}},
                    "exception_info": {
                        "exception_type": "AgentTimeoutError",
                        "exception_message": "timed out",
                    },
                    "agent_info": {"name": "terminus-2"},
                    "config": {"agent": {"model_name": model}},
                },
            )
            self.assertEqual(attempted_n(slug, model, jobs), 1)
            self.assertEqual(remaining_k(slug, model, 5, jobs), 4)


class SecondArmResolveTests(unittest.TestCase):
    def test_openai_candidates_prefer_mini_then_gpt4o(self):
        self.assertEqual(OPENAI_SECOND_CANDIDATES[0], CHEAP_SECOND_MODEL)
        self.assertEqual(OPENAI_SECOND_CANDIDATES[1], "openai/gpt-4o")
        self.assertEqual(CHEAP_SECOND_FALLBACK, "anthropic/claude-sonnet-4-5")

    def test_picks_gpt4o_when_mini_429(self):
        import argparse

        import run_lab_batch as rlb

        def fake_probe(kind, model=None):
            name = (model or "").replace("openai/", "")
            if kind == "openai" and name == "gpt-4o":
                return {"ok": True, "status": 200, "blocked": None, "model": "gpt-4o"}
            if kind == "openai":
                return {
                    "ok": False,
                    "status": 429,
                    "blocked": "insufficient_quota",
                    "model": name,
                }
            return {
                "ok": False,
                "status": 400,
                "blocked": "credit balance is too low",
                "model": name,
            }

        orig = rlb.probe_http_arm
        rlb.probe_http_arm = fake_probe
        try:
            args = argparse.Namespace(
                second_model="openai/gpt-4o-mini",
                second_fallback="anthropic/claude-sonnet-4-5",
            )
            self.assertEqual(rlb.resolve_second_model(args), "openai/gpt-4o")
        finally:
            rlb.probe_http_arm = orig

    def test_falls_back_to_sonnet_when_all_openai_blocked(self):
        import argparse

        import run_lab_batch as rlb

        def fake_probe(kind, model=None):
            if kind == "openai":
                return {
                    "ok": False,
                    "status": 429,
                    "blocked": "insufficient_quota",
                    "model": model,
                }
            return {"ok": True, "status": 200, "blocked": None, "model": model}

        orig = rlb.probe_http_arm
        rlb.probe_http_arm = fake_probe
        try:
            args = argparse.Namespace(
                second_model="openai/gpt-4o-mini",
                second_fallback="anthropic/claude-sonnet-4-5",
            )
            self.assertEqual(rlb.resolve_second_model(args), "anthropic/claude-sonnet-4-5")
        finally:
            rlb.probe_http_arm = orig

    def test_raises_when_both_providers_blocked(self):
        import argparse

        import run_lab_batch as rlb

        def fake_probe(kind, model=None):
            if kind == "openai":
                return {
                    "ok": False,
                    "status": 429,
                    "blocked": "insufficient_quota",
                    "model": model,
                }
            return {
                "ok": False,
                "status": 400,
                "blocked": "credit balance is too low",
                "model": model,
            }

        orig = rlb.probe_http_arm
        rlb.probe_http_arm = fake_probe
        try:
            args = argparse.Namespace(
                second_model="openai/gpt-4o-mini",
                second_fallback="anthropic/claude-sonnet-4-5",
            )
            with self.assertRaises(rlb.StopMeasure):
                rlb.resolve_second_model(args)
        finally:
            rlb.probe_http_arm = orig


class IterateStopTests(unittest.TestCase):
    def test_halt_iterate_false_does_not_stop(self):
        import iterate_lab_batches as it

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "lab_batch_01_stop.json").write_text(
                json.dumps({"halt_iterate": False, "reason": "haiku skipped"}),
                encoding="utf-8",
            )
            orig = it.ROOT
            it.ROOT = root
            try:
                self.assertFalse(it.stopped(1))
            finally:
                it.ROOT = orig

    def test_legacy_stop_file_still_halts(self):
        import iterate_lab_batches as it

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "lab_batch_01_stop.json").write_text(
                json.dumps({"reason": "credit balance is too low"}),
                encoding="utf-8",
            )
            orig = it.ROOT
            it.ROOT = root
            try:
                self.assertTrue(it.stopped(1))
            finally:
                it.ROOT = orig


class LabUiIdentityTests(unittest.TestCase):
    def test_static_lab_keeps_applied_work_identity(self):
        html = (ROOT / "lab" / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "lab" / "lab.css").read_text(encoding="utf-8")
        js = (ROOT / "lab" / "lab.js").read_text(encoding="utf-8")
        self.assertIn("Applied Work Worlds Lab", html)
        for surface in (
            "worlds",
            "coverage",
            "catalog",
            "runs",
            "traces",
            "stump",
            "failures",
            "verifier",
            "harness",
            "spend",
            "batches",
            "agents",
        ):
            self.assertIn(f'data-nav="{surface}"', html)
            self.assertIn(f"id=\"surface-{surface}\"", html)
        self.assertNotIn("Senior SWE-Bench", html)
        self.assertNotIn("snorkel.ai", html.lower())
        self.assertNotIn("Post-Training Signal Lab", html)
        self.assertNotIn("00 Introduction", html)
        self.assertIn("pre-wrap", css)
        self.assertIn("#preview-code", css)
        self.assertIn("not run", js.lower())
        self.assertNotIn("8/8 solved", js)
        self.assertIn("${row.solved || 0}/${recorded}", js)
        self.assertNotIn("${row.solved || 0}/${PLANNED}", js)
        self.assertIn('category === "batch" && batchNum(task) !== 1', js)
        self.assertIn("https://github.com/Sivadheeraj5356/terminus-logs", html)
        self.assertEqual(PLANNED_ATTEMPTS, 5)

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
