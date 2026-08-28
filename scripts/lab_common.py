"""Shared lab constants, Harbor trial matching, and valid-fail classification.

Stump arithmetic: valid_fail / completed_trials. Timeouts and infra do not count.
Do not invent scores. Match Harbor trials by slug or uuid (do not truncate slugs).
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = ROOT / "jobs"
CATALOG_JSONL = ROOT / "catalog" / "tasks.jsonl"
MVP_JSONL = ROOT / "docs" / "lab_mvp_100.jsonl"
BATCH_01_JSONL = ROOT / "docs" / "lab_batch_01.jsonl"
BATCH_01_EXCLUSIONS_JSON = ROOT / "docs" / "lab_batch_01_exclusions.json"
TASKS_LATEST = ROOT / "tasks" / "latest"

CATEGORY_ORDER = [
    "scientific-computing",
    "security",
    "system-administration",
    "build-and-dependency-management",
    "data-processing",
    "machine-learning",
    "games",
    "debugging",
]

# Plan: 8 TB categories (debugging gets 1) plus 2 extra from sci/security.
BATCH_01_SEATS = {
    "scientific-computing": 2,
    "security": 2,
    "system-administration": 1,
    "build-and-dependency-management": 1,
    "data-processing": 1,
    "machine-learning": 1,
    "games": 1,
    "debugging": 1,
}

# Plan examples for ≥8 distinct primaries.
PREFERRED_LANGS = [
    "Go",
    "Rust",
    "Python",
    "TypeScript",
    "C",
    "C++",
    "Java",
    "Bash",
]

LANG_ALIASES = {
    "c": "C",
    "c++": "C++",
    "cpp": "C++",
    "csharp": "C#",
    "c#": "C#",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "py": "Python",
    "python": "Python",
    "golang": "Go",
    "go": "Go",
    "rs": "Rust",
    "rust": "Rust",
    "rb": "Ruby",
    "ruby": "Ruby",
    "sh": "Bash",
    "shell": "Bash",
    "bash": "Bash",
    "jl": "Julia",
    "julia": "Julia",
    "kt": "Kotlin",
    "kotlin": "Kotlin",
    "java": "Java",
    "r": "R",
    "sql": "SQL",
    "php": "PHP",
    "lua": "Lua",
    "haskell": "Haskell",
    "awk": "Awk",
    "yaml": "YAML",
    "toml": "TOML",
    "json": "JSON",
    "minizinc": "MiniZinc",
}

TIMEOUT_RE = re.compile(r"timeout|timed out|AgentTimeout|VerifierTimeout", re.I)
INFRA_RE = re.compile(
    r"RuntimeError|DaytonaError|EnvironmentStart|AgentSetup|BadRequest|"
    r"RewardFileNotFound|AddTestsDir|DownloadVerifier|InfraBootstrap|InternalServer|"
    r"AuthenticationError|Unauthorized|401|403|API key|invalid_api_key|PermissionDenied",
    re.I,
)
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def normalize_language(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return raw
    return LANG_ALIASES.get(raw.lower(), raw)


def primary_language(languages) -> str:
    if not languages:
        return ""
    if isinstance(languages, str):
        languages = [languages]
    return normalize_language(languages[0]) if languages else ""


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def classify(result: dict) -> str:
    exception = result.get("exception_info") or {}
    exc_type = str(exception.get("exception_type") or "")
    blob = f"{exc_type} {exception.get('exception_message') or ''}"
    reward = None
    rewards = ((result.get("verifier_result") or {}).get("rewards") or {})
    if "reward" in rewards:
        try:
            reward = float(rewards["reward"])
        except (TypeError, ValueError):
            reward = None
    if reward is None:
        raw = result.get("reward")
        if raw is not None:
            try:
                reward = float(raw)
            except (TypeError, ValueError):
                reward = None
    if reward == 1.0:
        return "solved"
    if TIMEOUT_RE.search(blob) or exc_type.endswith("TimeoutError"):
        return "timeout"
    if INFRA_RE.search(blob) or exc_type:
        return "infra_error"
    if reward == 0.0:
        return "valid_fail"
    return "unknown"


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def trajectory_summary(trial_dir: Path) -> str:
    candidates = [
        trial_dir / "agent" / "trajectory.json",
        trial_dir / "trajectory.json",
        trial_dir / "summary.md",
    ]
    for path in candidates:
        if path.exists() and path.suffix == ".md":
            return path.read_text(encoding="utf-8", errors="replace")[:2000]
    traj_path = next((p for p in candidates if p.name == "trajectory.json" and p.exists()), None)
    if not traj_path:
        log = trial_dir / "trial.log"
        if log.exists():
            text = log.read_text(encoding="utf-8", errors="replace")
            return collapse(text[-1500:])
        return "No trajectory.json was written for this trial."
    try:
        data = json.loads(traj_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "trajectory.json was present but not valid JSON."
    steps = []
    messages = data if isinstance(data, list) else data.get("messages") or data.get("steps") or []
    if isinstance(messages, dict):
        messages = messages.get("items") or []
    for item in messages[:12]:
        if not isinstance(item, dict):
            continue
        role = item.get("role") or item.get("type") or "step"
        content = item.get("content") or item.get("text") or item.get("message") or ""
        if isinstance(content, list):
            bits = []
            for part in content:
                if isinstance(part, dict):
                    bits.append(str(part.get("text") or part.get("content") or "")[:200])
                else:
                    bits.append(str(part)[:200])
            content = " ".join(x for x in bits if x)
        content = collapse(str(content))
        if content:
            steps.append(f"{role}: {content[:240]}")
    if not steps:
        return f"Trajectory recorded ({traj_path.name}) but no readable steps were found."
    return " | ".join(steps[:8])


def test_fraction(result: dict) -> float | None:
    rewards = ((result.get("verifier_result") or {}).get("rewards") or {})
    for key in ("test_fraction", "tests", "fraction_passed"):
        if key in rewards:
            try:
                return float(rewards[key])
            except (TypeError, ValueError):
                continue
    details = (result.get("verifier_result") or {}).get("details") or {}
    passed = details.get("n_passed") or details.get("passed")
    total = details.get("n_total") or details.get("total")
    try:
        if passed is not None and total:
            return float(passed) / float(total)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return None


def trial_identity(data: dict, result_path: Path) -> dict:
    task_name = str(data.get("task_name") or "")
    folder = task_name.split("/")[-1] if task_name else result_path.parent.name.split("__")[0]
    uuid_hit = UUID_RE.search(task_name) or UUID_RE.search(result_path.parent.name)
    uuid = uuid_hit.group(0).lower() if uuid_hit else ""
    keys = set()
    if folder:
        keys.add(folder)
    if uuid:
        keys.add(uuid)
    return {
        "task_name": task_name,
        "folder": folder,
        "uuid": uuid,
        "keys": keys,
        "trial_dir": result_path.parent,
    }


def is_job_rollup(data: dict, result_path: Path, jobs_dir: Path) -> bool:
    if "n_total_trials" in data and result_path.parent.parent == jobs_dir:
        return True
    if result_path.parent == jobs_dir:
        return True
    return False


def collect_trials(jobs_dir: Path | None = None) -> dict[str, list[dict]]:
    """Index Harbor trial result.json files by slug folder and by uuid."""
    jobs_dir = Path(jobs_dir) if jobs_dir else JOBS_DIR
    by_key: dict[str, list[dict]] = defaultdict(list)
    if not jobs_dir.exists():
        return by_key
    seen: set[str] = set()
    for result_path in jobs_dir.rglob("result.json"):
        if result_path.name != "result.json":
            continue
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if "task_name" not in data and "trial_name" not in data:
            continue
        if is_job_rollup(data, result_path, jobs_dir):
            continue
        marker = str(result_path)
        if marker in seen:
            continue
        seen.add(marker)
        ident = trial_identity(data, result_path)
        agent = ((data.get("agent_info") or {}) or {}).get("name") or ""
        model = ((data.get("config") or {}).get("agent") or {}).get("model_name") or ""
        if not model:
            model = ((data.get("agent_info") or {}) or {}).get("model_name") or ""
        row = {
            "task_name": ident["task_name"],
            "folder": ident["folder"],
            "uuid": ident["uuid"],
            "agent": agent,
            "model": model,
            "classification": classify(data),
            "exception_type": ((data.get("exception_info") or {}) or {}).get("exception_type"),
            "trial_dir": str(ident["trial_dir"]),
            "agent_summary": trajectory_summary(ident["trial_dir"]),
            "test_fraction": test_fraction(data),
            "reward": ((data.get("verifier_result") or {}).get("rewards") or {}).get("reward"),
        }
        for key in ident["keys"]:
            by_key[key].append(row)
    return by_key


def summarize_trials(rows: list[dict]) -> dict:
    counts: dict[str, int] = defaultdict(int)
    by_model: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    traces = []
    seen_dirs = set()
    unique_rows = []
    for row in rows:
        marker = row.get("trial_dir")
        if marker in seen_dirs:
            continue
        seen_dirs.add(marker)
        unique_rows.append(row)
        counts[row["classification"]] += 1
        key = row["model"] or row["agent"] or "unknown"
        by_model[key][row["classification"]] += 1
        traces.append(
            {
                "model": row["model"] or row["agent"] or "unknown",
                "classification": row["classification"],
                "summary": row.get("agent_summary") or "",
                "trial_dir": row.get("trial_dir"),
                "test_fraction": row.get("test_fraction"),
            }
        )
    completed = counts["solved"] + counts["valid_fail"]
    stump = round(100.0 * counts["valid_fail"] / completed, 1) if completed else None
    models = []
    for model, c in sorted(by_model.items()):
        m_completed = c["solved"] + c["valid_fail"]
        models.append(
            {
                "model": model,
                "n": sum(c.values()),
                "solved": c["solved"],
                "valid_fail": c["valid_fail"],
                "timeout": c["timeout"],
                "infra_error": c["infra_error"],
                "unknown": c["unknown"],
                "stump_pct": (
                    round(100.0 * c["valid_fail"] / m_completed, 1) if m_completed else None
                ),
            }
        )
    return {
        "n_trials": len(unique_rows),
        "solved": counts["solved"],
        "valid_fail": counts["valid_fail"],
        "timeout": counts["timeout"],
        "infra_error": counts["infra_error"],
        "unknown": counts["unknown"],
        "completed_trials": completed,
        "stump_pct": stump,
        "by_model": models,
        "traces": traces,
    }


def band_for(stump_pct: float | None) -> str:
    if stump_pct is None:
        return "no_logs"
    if stump_pct >= 60:
        return "stumps"
    if stump_pct >= 40:
        return "borderline"
    return "too_easy"


def coverage_matrix(gallery: list[dict], batch_slugs: set[str], measured_slugs: set[str]) -> dict:
    langs = sorted(
        {
            primary_language(t.get("languages") or [])
            for t in gallery
            if primary_language(t.get("languages") or [])
        }
    )
    cells: dict[str, dict] = {}
    for task in gallery:
        slug = task.get("slug") or task.get("id")
        cat = task.get("category") or "unknown"
        lang = primary_language(task.get("languages") or []) or "—"
        key = f"{cat}|{lang}"
        cell = cells.setdefault(
            key,
            {
                "domain": cat,
                "language": lang,
                "gallery": 0,
                "selected": 0,
                "measured": 0,
                "slugs": [],
            },
        )
        cell["gallery"] += 1
        if slug in batch_slugs:
            cell["selected"] += 1
            cell["slugs"].append(slug)
        if slug in measured_slugs:
            cell["measured"] += 1
    return {
        "domains": list(CATEGORY_ORDER),
        "languages": langs,
        "cells": cells,
        "gallery_n": len(gallery),
        "selected_n": len(batch_slugs),
        "measured_n": len(measured_slugs),
    }
