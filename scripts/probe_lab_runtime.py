"""Probe the Harbor evaluation host: keys, binary, Docker, optional 1-trial smoke.

Writes docs/lab_batch_01_status.json. Does not invent scores. Does not start
the 160-run batch. Refuse to smoke if Anthropic is a sk-proj- value or Harbor
/ Docker are missing.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lab_common import BATCH_01_JSONL, load_jsonl  # noqa: E402

STATUS_PATH = ROOT / "docs" / "lab_batch_01_status.json"
SMOKE_SLUG_DEFAULT = "repair-the-pendulum-motion-solver"


def key_report() -> dict:
    anthropic = os.environ.get("ANTHROPIC_API_KEY") or ""
    openai = os.environ.get("OPENAI_API_KEY") or ""
    anth_ok = anthropic.startswith("sk-ant-")
    openai_ok = bool(openai) and openai.startswith("sk-") and not openai.startswith("sk-ant-")
    anth_is_proj = anthropic.startswith("sk-proj-")
    return {
        "anthropic_present": bool(anthropic),
        "anthropic_len": len(anthropic),
        "anthropic_prefix": anthropic[:7] if anthropic else "",
        "anthropic_ok": anth_ok,
        "anthropic_is_openai_project_key": anth_is_proj,
        "openai_present": bool(openai),
        "openai_len": len(openai),
        "openai_prefix": openai[:4] if openai else "",
        "openai_ok": openai_ok,
        "ok": anth_ok and openai_ok,
        "note": (
            "ANTHROPIC_API_KEY must start with sk-ant-. OPENAI_API_KEY must be a "
            "real OpenAI key in this shell. Do not paste keys into chat."
        ),
    }


def which(name: str) -> str | None:
    return shutil.which(name)


def run_cmd(argv: list[str], timeout: int = 20) -> dict:
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        return {
            "argv": argv,
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr[-2000:],
        }
    except FileNotFoundError:
        return {"argv": argv, "returncode": 127, "stdout": "", "stderr": "not found"}
    except subprocess.TimeoutExpired:
        return {"argv": argv, "returncode": 124, "stdout": "", "stderr": "timeout"}


def parse_harbor_help(text: str) -> dict:
    lines = []
    for raw in text.splitlines():
        low = raw.lower()
        if any(tok in low for tok in ("-k", "n-attempts", "n_attempts", "n-trials", "n_trials", "attempts")):
            lines.append(raw.strip())
    return {
        "n_trials_flag_mentioned": any("n-trials" in x.lower() or "n_trials" in x.lower() for x in lines),
        "n_attempts_or_k_mentioned": any(
            "-k" in x.lower() or "n-attempts" in x.lower() or "n_attempts" in x.lower() for x in lines
        ),
        "help_lines": lines[:40],
        "interpretation": (
            "Harbor n_trials = n_attempts × n_tasks × n_agents. CLI -k / --n-attempts "
            "creates independent trials (cartesian product), not intra-trial retries. "
            "Use -k 8 -n 1 for eight independent rollouts. Infra retries are --retry."
        ),
    }


def probe(*, smoke: bool, smoke_slug: str, opus_model: str, gpt_model: str) -> dict:
    keys = key_report()
    harbor_bin = which("harbor")
    docker_bin = which("docker")
    docker_info = run_cmd(["docker", "info"], timeout=15) if docker_bin else None
    harbor_help = run_cmd(["harbor", "run", "--help"], timeout=15) if harbor_bin else None
    harbor_help_text = ""
    if harbor_help:
        harbor_help_text = (harbor_help.get("stdout") or "") + "\n" + (harbor_help.get("stderr") or "")
        # Status JSON should not store the entire `harbor run --help` dump.
        harbor_help = {
            "argv": harbor_help.get("argv"),
            "returncode": harbor_help.get("returncode"),
            "stderr": harbor_help.get("stderr") or "",
        }
    harbor_k = parse_harbor_help(harbor_help_text)
    batch = load_jsonl(BATCH_01_JSONL)
    blockers = []
    if not harbor_bin:
        blockers.append("harbor binary not on PATH")
    if not docker_bin:
        blockers.append("docker binary not on PATH")
    elif docker_info and docker_info.get("returncode") not in (0, None):
        blockers.append("docker info failed (daemon down?)")
    if not keys["anthropic_ok"]:
        blockers.append("ANTHROPIC_API_KEY missing or not sk-ant-")
    if keys["anthropic_is_openai_project_key"]:
        blockers.append("ANTHROPIC_API_KEY is an OpenAI sk-proj- value")
    if not keys["openai_ok"]:
        blockers.append("OPENAI_API_KEY missing or not a real OpenAI key")

    status = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": os.uname().nodename if hasattr(os, "uname") else "unknown",
        "keys": keys,
        "harbor": {
            "path": harbor_bin,
            "help": harbor_help,
            "k_vs_n_trials": harbor_k,
        },
        "docker": {"path": docker_bin, "info": docker_info},
        "batch_01_n": len(batch),
        "smoke_slug": smoke_slug,
        "opus_model": opus_model,
        "gpt_model": gpt_model,
        "blockers": blockers,
        "smoke": {"skipped": True, "reason": blockers or "probe without --smoke"},
        "oracle": {"skipped": True, "reason": blockers or "not requested in probe"},
        "measure": {
            "skipped": True,
            "reason": (
                blockers
                if blockers
                else "160 frontier runs require a green smoke then -Phase measure -YesMeasure"
            ),
            "frontier_jobs_started": 0,
            "target_frontier_jobs": 160,
        },
        "ok_to_smoke": not blockers,
        "ok_to_measure_160": False,
        "note": (
            "Probe only. 160 frontier runs stay on the Harbor host after a green "
            "1-task smoke of both models. This file is not a scoreboard."
        ),
    }

    if smoke:
        if blockers:
            status["smoke"] = {"skipped": True, "reason": blockers}
        else:
            pkg = ROOT / "tasks" / "latest" / smoke_slug
            jobs = ROOT / "jobs"
            jobs.mkdir(exist_ok=True)
            smokes = []
            for model in (opus_model, gpt_model):
                argv = [
                    "harbor",
                    "run",
                    "-p",
                    str(pkg),
                    "-a",
                    "terminus-2",
                    "-m",
                    model,
                    "-k",
                    "1",
                    "-n",
                    "1",
                    "-o",
                    str(jobs),
                    "--job-name",
                    f"lab-smoke-{model.replace('/', '-')}",
                    "-y",
                ]
                smokes.append(run_cmd(argv, timeout=1800))
            status["smoke"] = {"runs": smokes}
            status["ok_to_measure_160"] = all(r.get("returncode") == 0 for r in smokes)

    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="1 trial × both models if the host is ready")
    parser.add_argument("--slug", default=SMOKE_SLUG_DEFAULT)
    parser.add_argument("--opus-model", default="anthropic/claude-opus-5")
    parser.add_argument("--gpt-model", default="openai/gpt-5.6-sol")
    args = parser.parse_args()
    status = probe(
        smoke=args.smoke,
        smoke_slug=args.slug,
        opus_model=args.opus_model,
        gpt_model=args.gpt_model,
    )
    print(json.dumps({k: status[k] for k in ("generated_utc", "blockers", "ok_to_smoke", "ok_to_measure_160", "keys")}, indent=2))
    print(f"wrote {STATUS_PATH.relative_to(ROOT)}")
    if status["blockers"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
