"""Build the Terminal-Bench catalog from local task folders and optional Harbor jobs."""

from __future__ import annotations

import json
import re
import tomllib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "tasks" / "latest"
INDEX_PATH = ROOT / "catalog" / "_latest_index.json"
CATALOG_DIR = ROOT / "catalog"
TASK_CARDS_DIR = CATALOG_DIR / "tasks"
JOB_SEARCH_ROOTS = [
    ROOT / "tasks" / "latest",
    ROOT / "jobs",
    ROOT / "_jobs",
    Path.home() / ".cache" / "harbor" / "jobs",
]
UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)

PATH_RE = re.compile(r"(?:/app/[^\s)\]`'\"<>]+|[A-Za-z0-9_./-]+\.(?:txt|json|bin|py|sh|csv|pem|crt|key|md|html|R))")
TIMEOUT_RE = re.compile(r"timeout|timed out|AgentTimeout|VerifierTimeout", re.I)
INFRA_RE = re.compile(
    r"RuntimeError|DaytonaError|EnvironmentStart|AgentSetup|BadRequest|"
    r"RewardFileNotFound|AddTestsDir|DownloadVerifier|InfraBootstrap|InternalServer",
    re.I,
)


def load_toml(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def extract_paths(text: str) -> list[str]:
    found = []
    for match in PATH_RE.findall(text):
        cleaned = match.rstrip(".,;:")
        if cleaned not in found:
            found.append(cleaned)
    return found[:12]


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def instruction_paragraphs(text: str) -> list[str]:
    chunks = [collapse_ws(p) for p in re.split(r"\n\s*\n", text) if collapse_ws(p)]
    return chunks


def summarize_instruction(instruction: str, description: str) -> str:
    paras = instruction_paragraphs(instruction)
    sentences: list[str] = []
    for para in paras:
        if para.startswith("#"):
            continue
        if re.match(r"^(\d+\.|[-*])\s", para):
            continue
        sentences.append(para)
        if len(sentences) == 2:
            break
    if not sentences:
        sentences.append(description or "See instruction.md for the full prompt.")
    numbered = re.findall(r"^\s*\d+\.\s+(.+)$", instruction, re.M)
    if numbered:
        clipped = [collapse_ws(item) for item in numbered[:4]]
        sentences.append("Key requirements: " + "; ".join(clipped) + ".")
    if description and description.lower() not in " ".join(sentences).lower():
        sentences.append(description)
    return " ".join(sentences)


def quality_flags(instruction: str, has_tests: bool, category: str, tags: list[str]) -> dict:
    has_paths = bool(re.search(r"/app/", instruction))
    has_numbered = bool(re.search(r"^\s*\d+\.", instruction, re.M))
    format_heavy = bool(
        re.search(r"exactly|bit-for-bit|whitespace|formatting|precision|decimal", instruction, re.I)
    )
    reasoning_cats = {
        "scientific-computing",
        "security",
        "model-training",
        "software-engineering",
        "data-science",
        "debugging",
        "system-administration",
    }
    tedium_tags = {"file-operations", "data-processing"}
    if category in reasoning_cats and not (format_heavy and "file-operations" in tags):
        difficulty_source = "reasoning"
    elif format_heavy or set(tags) <= tedium_tags:
        difficulty_source = "tedium_or_format"
    else:
        difficulty_source = "mixed"
    return {
        "well_specified": has_paths or has_numbered,
        "outcome_verified": has_tests,
        "difficulty_source": difficulty_source,
        "format_sensitive": format_heavy,
    }


def inferred_failure_modes(task_id: str, category: str, instruction: str) -> list[str]:
    modes = []
    text = instruction.lower()
    if re.search(r"\b(password|crack|hash|7z|john)\b", text):
        modes.append("Wrong cracking tool, wordlist, or archive handling; secret extracted but written to the wrong path.")
    if re.search(r"\b(javascript|xss)\b", text):
        modes.append("Incomplete JS/XSS filter: event handlers, javascript: URLs, or encoded payloads survive.")
    if re.search(r"\b(train|accuracy|fasttext)\b", text) and re.search(r"\bmodel\b", text):
        modes.append("Trains a model that misses the accuracy or size gate, or saves it to the wrong filename.")
    if re.search(r"\b(openssl|certificate|tls)\b", text):
        modes.append("Certificate fields, permissions, or verification text do not match the required layout.")
    if re.search(r"\bgit\b", text):
        modes.append("Repo history, hooks, or remotes are only partially repaired; tests see leftover secrets or missing refs.")
    if re.search(r"\bqemu\b", text) or "windows-3.11" in task_id:
        modes.append("Guest never becomes reachable: wrong disk, boot flags, or SSH/networking setup.")
    if re.search(r"\bmips\b", text) or "doom" in task_id:
        modes.append("Cross-compile or emulator bring-up fails; binary exists but does not run under the required target.")
    if category == "scientific-computing":
        modes.append("Recovers a plausible scientific model that fails held-out numeric or statistical checks.")
    if "parallel" in task_id or "tensor" in task_id:
        modes.append("Distributed/parallel setup looks right but correctness or sharding tests fail.")
    if not modes:
        modes.append("Agent finishes a locally plausible solution that misses a hidden verifier constraint.")
        modes.append("Agent spends the budget exploring the environment and never writes the required artifacts.")
    return modes[:4]


def classify_trial(result: dict, reward_text: str | None) -> str:
    exception = ((result.get("exception_info") or {}) or {})
    exc_type = str(exception.get("exception_type") or "")
    exc_msg = str(exception.get("exception_message") or "")
    blob = f"{exc_type} {exc_msg}"
    reward = None
    verifier = result.get("verifier_result") or {}
    rewards = verifier.get("rewards") or {}
    if "reward" in rewards:
        try:
            reward = float(rewards["reward"])
        except (TypeError, ValueError):
            reward = None
    if reward is None and reward_text is not None:
        try:
            reward = float(reward_text.strip().split()[0])
        except (TypeError, ValueError, IndexError):
            reward = None
    if reward == 1.0:
        return "solved"
    if TIMEOUT_RE.search(blob) or exc_type.endswith("TimeoutError"):
        return "timeout"
    if INFRA_RE.search(blob) or exc_type:
        return "infra_error"
    if reward == 0.0 or reward == 0:
        return "valid_fail"
    return "unknown"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:72] or "task"


def read_instruction(task_dir: Path) -> str:
    direct = task_dir / "instruction.md"
    if direct.exists():
        return direct.read_text(encoding="utf-8", errors="replace")
    steps_dir = task_dir / "steps"
    if steps_dir.exists():
        parts = []
        for path in sorted(steps_dir.glob("*/instruction.md")):
            parts.append(f"## {path.parent.name}\n\n{path.read_text(encoding='utf-8', errors='replace')}")
        return "\n\n".join(parts)
    return ""


def derive_slug(task_dir: Path, task: dict, meta: dict, instruction: str) -> str:
    raw = meta.get("name") or task.get("name") or ""
    if raw and not str(raw).startswith("milestone"):
        return slugify(str(raw).split("/")[-1])
    tags = meta.get("tags") or task.get("keywords") or []
    if tags:
        return slugify("-".join(str(t) for t in tags[:4]))
    first = instruction_paragraphs(instruction)
    if first:
        return slugify(" ".join(first[0].split()[:8]))
    return slugify(task_dir.name)


def read_package_uuid(task_dir: Path) -> str:
    for marker in (".extracted_from", ".extracted"):
        path = task_dir / marker
        if path.exists():
            match = UUID_RE.search(path.read_text(encoding="utf-8", errors="replace"))
            if match:
                return match.group(0).lower()
    if UUID_RE.fullmatch(task_dir.name):
        return task_dir.name.lower()
    summary = task_dir / "summary.md"
    if summary.exists():
        match = UUID_RE.search(summary.read_text(encoding="utf-8", errors="replace"))
        if match:
            return match.group(0).lower()
    return task_dir.name


def parse_task(task_dir: Path) -> dict:
    toml_path = task_dir / "task.toml"
    data = load_toml(toml_path)
    task = data.get("task") or {}
    meta = data.get("metadata") or {}
    instruction = read_instruction(task_dir)
    authors = task.get("authors") or []
    if isinstance(authors, list) and authors:
        author = authors[0].get("name") if isinstance(authors[0], dict) else str(authors[0])
    else:
        author = meta.get("author_name") or ""
    description = task.get("description") or meta.get("difficulty_explanation") or ""
    if isinstance(description, str) and len(description) > 400:
        description = description[:397].rsplit(" ", 1)[0] + "..."
    category = meta.get("category") or ""
    tags = list(meta.get("tags") or task.get("keywords") or [])
    uuid = read_package_uuid(task_dir)
    if UUID_RE.fullmatch(task_dir.name):
        slug = derive_slug(task_dir, task, meta, instruction)
    else:
        slug = task_dir.name
    has_oracle = first_existing(task_dir / "solution" / "solve.sh", task_dir / "solution" / "solve.bash") is not None
    test_sh = first_existing(task_dir / "tests" / "test.sh", task_dir / "tests" / "test.bat")
    test_py = list((task_dir / "tests").glob("test_*.py")) if (task_dir / "tests").exists() else []
    return {
        "id": slug,
        "uuid": uuid,
        "sid": uuid,
        "package_dir": f"tasks/latest/{slug}",
        "harbor_name": meta.get("name") or task.get("name") or slug,
        "description": description,
        "author": author,
        "category": category,
        "difficulty": meta.get("difficulty") or "",
        "tags": tags,
        "expert_time_estimate_min": meta.get("expert_time_estimate_min"),
        "junior_time_estimate_min": meta.get("junior_time_estimate_min"),
        "agent_timeout_sec": (data.get("agent") or {}).get("timeout_sec"),
        "verifier_timeout_sec": (data.get("verifier") or {}).get("timeout_sec"),
        "build_timeout_sec": (data.get("environment") or {}).get("build_timeout_sec"),
        "cpus": (data.get("environment") or {}).get("cpus"),
        "memory_mb": (data.get("environment") or {}).get("memory_mb"),
        "allow_internet": (data.get("environment") or {}).get("allow_internet"),
        "docker_image": (data.get("environment") or {}).get("docker_image"),
        "has_oracle": has_oracle,
        "has_tests": test_sh is not None,
        "test_files": [p.name for p in test_py],
        "required_outputs": extract_paths(instruction),
        "instruction": instruction,
        "instruction_summary": summarize_instruction(instruction, description),
        "quality": quality_flags(instruction, test_sh is not None, category, tags),
        "source_path": str(task_dir),
    }


def discover_tasks(source: Path) -> list[Path]:
    if not source.exists():
        return []
    dirs = []
    for child in sorted(source.iterdir()):
        if child.is_dir() and (child / "task.toml").exists():
            dirs.append(child)
    return dirs


def discover_job_roots() -> list[Path]:
    roots = []
    for root in JOB_SEARCH_ROOTS:
        if root.exists():
            roots.append(root)
    return roots


def iter_trial_results(job_roots: list[Path]) -> list[dict]:
    trials = []
    for root in job_roots:
        for result_path in root.rglob("result.json"):
            try:
                data = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if "task_name" not in data and "trial_name" not in data:
                continue
            reward_path = first_existing(
                result_path.parent / "verifier" / "reward.txt",
                result_path.parent / "logs" / "verifier" / "reward.txt",
            )
            reward_text = reward_path.read_text(encoding="utf-8") if reward_path else None
            task_name = data.get("task_name") or ""
            task_id = task_name.split("/")[-1] if task_name else ""
            if not task_id:
                trial_name = data.get("trial_name") or result_path.parent.name
                task_id = trial_name.split("__")[0]
            agent = ((data.get("agent_info") or {}) or {}).get("name") or ""
            model = ((data.get("config") or {}).get("agent") or {}).get("model_name") or ""
            classification = classify_trial(data, reward_text)
            stdout = ""
            for candidate in (
                result_path.parent / "verifier" / "test-stdout.txt",
                result_path.parent / "verifier" / "test-console-output.txt",
                result_path.parent / "logs" / "verifier" / "stdout.txt",
            ):
                if candidate.exists():
                    stdout = candidate.read_text(encoding="utf-8", errors="replace")[:4000]
                    break
            trials.append(
                {
                    "task_id": task_id,
                    "task_name": task_name,
                    "agent": agent,
                    "model": model,
                    "classification": classification,
                    "job_path": str(result_path.parent),
                    "exception_type": ((data.get("exception_info") or {}) or {}).get("exception_type"),
                    "verifier_stdout": stdout,
                }
            )
    return trials


def band_for(stump_pct: float | None, unsolved_pct: float | None, has_any: bool) -> str:
    score = stump_pct if stump_pct is not None else unsolved_pct
    if not has_any or score is None:
        return "no_logs"
    if score >= 60:
        return "stumps"
    if score >= 40:
        return "borderline"
    return "too_easy"


def aggregate_local(trials: list[dict]) -> dict[str, dict]:
    by_task: dict[str, list[dict]] = defaultdict(list)
    for trial in trials:
        by_task[trial["task_id"]].append(trial)
    out = {}
    for task_id, items in by_task.items():
        by_model: dict[str, list[dict]] = defaultdict(list)
        for item in items:
            key = item["model"] or item["agent"] or "unknown"
            by_model[key].append(item)
        model_rows = []
        for model, rows in sorted(by_model.items()):
            counts = defaultdict(int)
            for row in rows:
                counts[row["classification"]] += 1
            completed = counts["solved"] + counts["valid_fail"]
            stump = round(100.0 * counts["valid_fail"] / completed, 1) if completed else None
            model_rows.append(
                {
                    "model": model,
                    "n": len(rows),
                    "solved": counts["solved"],
                    "valid_fail": counts["valid_fail"],
                    "timeout": counts["timeout"],
                    "infra_error": counts["infra_error"],
                    "unknown": counts["unknown"],
                    "stump_pct": stump,
                }
            )
        totals = defaultdict(int)
        for row in items:
            totals[row["classification"]] += 1
        completed = totals["solved"] + totals["valid_fail"]
        out[task_id] = {
            "n_trials": len(items),
            "solved": totals["solved"],
            "valid_fail": totals["valid_fail"],
            "timeout": totals["timeout"],
            "infra_error": totals["infra_error"],
            "unknown": totals["unknown"],
            "stump_pct": round(100.0 * totals["valid_fail"] / completed, 1) if completed else None,
            "by_model": model_rows,
            "sample_exceptions": sorted({r["exception_type"] for r in items if r.get("exception_type")}),
            "sample_verifier": next((r["verifier_stdout"] for r in items if r.get("verifier_stdout")), ""),
        }
    return out


def log_summary(task: dict, local: dict | None, public: dict) -> str:
    lines = []
    if local:
        lines.append(
            f"Local Harbor jobs: {local['n_trials']} trial(s) — "
            f"{local['solved']} solved, {local['valid_fail']} valid fail, "
            f"{local['timeout']} timeout, {local['infra_error']} infra, "
            f"{local['unknown']} unknown."
        )
        if local.get("sample_exceptions"):
            lines.append("Exceptions seen: " + ", ".join(local["sample_exceptions"]) + ".")
        if local.get("sample_verifier"):
            snippet = collapse_ws(local["sample_verifier"])[:400]
            lines.append(f"Verifier excerpt: {snippet}")
    else:
        lines.append(
            "This Dropbox submission zip is task source only — no Harbor "
            "`result.json` / `verifier/reward.txt` agent-run logs were included."
        )
    if public.get("n_trials"):
        lines.append(
            f"Public TB2 leaderboard ({public['n_trials']} trials): "
            f"{public['n_passed']} passed, {public['n_failed']} valid fail, "
            f"{public['n_errored']} timeout/infra. "
            f"Valid-fail stump rate {public['valid_stump_pct']}% "
            f"(timeouts excluded). Published unsolved rate including errors: "
            f"{public['leaderboard_unsolved_pct']}%."
        )
    elif public.get("leaderboard_unsolved_pct") is not None:
        lines.append(
            f"Public TB2 leaderboard unsolved rate is {public['leaderboard_unsolved_pct']}% "
            f"(1 − mean reward; timeouts and infra errors count as unsolved). "
            "Per-trial valid-fail vs timeout split was not published for this task."
        )
    return " ".join(lines)


def agent_summary(task: dict, local: dict | None) -> str:
    modes = inferred_failure_modes(task["id"], task["category"], task["instruction"])
    if local:
        by_model = ", ".join(
            f"{row['model']}: {row['valid_fail']}/{row['solved'] + row['valid_fail'] or 0} valid fail"
            if (row["solved"] + row["valid_fail"])
            else f"{row['model']}: no completed trials"
            for row in local["by_model"]
        )
        return (
            f"Local agent runs exist ({by_model}). "
            "Typical ways this task fails, consistent with the instruction: "
            + " ".join(modes)
        )
    return (
        "No agent trajectories were in this Dropbox submission zip. "
        "Failure modes below are inferred from the instruction only: "
        + " ".join(modes)
    )


def task_summary_md(task: dict) -> str:
    bits = [task["instruction_summary"]]
    if task["required_outputs"]:
        bits.append(
            "Required artifacts include: "
            + ", ".join(f"`{p}`" for p in task["required_outputs"][:8])
            + "."
        )
    bits.append(
        f"Author {task['author'] or 'unknown'} tagged this **{task['difficulty'] or 'unspecified'}** "
        f"{task['category'] or 'uncategorized'} task"
        + (f" ({', '.join(task['tags'])})" if task["tags"] else "")
        + "."
    )
    time_bits = []
    if task["expert_time_estimate_min"] is not None:
        time_bits.append(f"expert ~{task['expert_time_estimate_min']} min")
    if task["junior_time_estimate_min"] is not None:
        time_bits.append(f"junior ~{task['junior_time_estimate_min']} min")
    if time_bits:
        bits.append("Time estimates: " + ", ".join(time_bits) + ".")
    bits.append(
        f"Harbor timeouts: agent {task['agent_timeout_sec']}s, verifier {task['verifier_timeout_sec']}s"
        + (f", build {task['build_timeout_sec']}s." if task["build_timeout_sec"] else ".")
    )
    oracle = "Oracle `solution/solve.sh` is present" if task["has_oracle"] else "No oracle solution was found"
    tests = "tests write a Harbor reward via `tests/test.sh`" if task["has_tests"] else "no `tests/test.sh`"
    bits.append(f"{oracle}; {tests}.")
    q = task["quality"]
    bits.append(
        "Terminus-style flags (inspiration only, not a submission): "
        f"well-specified={'yes' if q['well_specified'] else 'weak'}, "
        f"outcome-verified={'yes' if q['outcome_verified'] else 'no'}, "
        f"difficulty source={q['difficulty_source']}."
    )
    return "\n\n".join(bits)


def stump_section(local: dict | None, public: dict, band: str) -> str:
    lines = []
    if local and local.get("by_model"):
        for row in local["by_model"]:
            completed = row["solved"] + row["valid_fail"]
            if row["stump_pct"] is None:
                lines.append(f"- {row['model']}: no completed trials — not a stump signal")
            else:
                verb = "stumps" if row["stump_pct"] >= 60 else "does not stump"
                lines.append(
                    f"- {row['model']}: {row['valid_fail']}/{completed} valid fail "
                    f"({row['stump_pct']}%) — {verb}"
                )
        lines.append(f"- Timeouts excluded: {local['timeout']}; infra excluded: {local['infra_error']}")
    if public.get("valid_stump_pct") is not None:
        verb = "stumps" if public["valid_stump_pct"] >= 60 else "does not stump"
        completed = public["n_passed"] + public["n_failed"]
        lines.append(
            f"- Public TB2 (all published agents): {public['n_failed']}/{completed} valid fail "
            f"({public['valid_stump_pct']}%) — {verb}"
        )
        lines.append(f"- Public timeouts/infra excluded: {public['n_errored']}")
    elif public.get("leaderboard_unsolved_pct") is not None:
        verb = "stumps" if public["leaderboard_unsolved_pct"] >= 60 else "mixed / often solved"
        lines.append(
            f"- Public TB2 unsolved rate (includes errors): {public['leaderboard_unsolved_pct']}% — {verb}"
        )
    if not lines:
        lines.append("- No local or public trial counts — stump % unknown")
    lines.append(f"- Band: `{band}`")
    return "\n".join(lines)


def write_card(task: dict, local: dict | None, public: dict, band: str) -> str:
    return f"""# {task['id']}

Harbor name: `{task['harbor_name']}`
Submission UUID: `{task.get('uuid', '')}`

## Task summary

{task_summary_md(task)}

## Log summary

{log_summary(task, local, public)}

## Agent summary

{agent_summary(task, local)}

## Stump the models?

{stump_section(local, public, band)}
"""


def main() -> None:
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    TASK_CARDS_DIR.mkdir(parents=True, exist_ok=True)
    for old in TASK_CARDS_DIR.glob("*.md"):
        old.unlink()
    latest_index = {}
    if INDEX_PATH.exists():
        for row in json.loads(INDEX_PATH.read_text(encoding="utf-8")):
            latest_index[row["uuid"]] = row
    task_dirs = discover_tasks(SOURCE_DIR)
    job_roots = discover_job_roots()
    local_trials = iter_trial_results(job_roots)
    local_by_task = aggregate_local(local_trials)

    inventory = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "archive_synced": True,
        "archive_note": (
            "Source is the private terminal-bench-tasks.zip archive. "
            "Latest revision of each submission UUID was extracted to tasks/latest. "
            "Official GitHub terminal-bench-2 is not used."
        ),
        "task_source": str(SOURCE_DIR),
        "n_task_folders": len(task_dirs),
        "n_local_trials": len(local_trials),
        "job_roots_configured": [str(p) for p in JOB_SEARCH_ROOTS],
        "job_roots_present": [str(p) for p in job_roots],
        "public_stats_source": None,
    }

    used_slugs: set[str] = set()
    records = []
    for task_dir in task_dirs:
        task = parse_task(task_dir)
        slug = task["id"]
        if slug in used_slugs:
            slug = f"{slug}-{task_dir.name[:8]}"
            task["id"] = slug
        used_slugs.add(slug)
        local = local_by_task.get(task["id"]) or local_by_task.get(task["uuid"])
        public = {
            "leaderboard_unsolved_pct": None,
            "n_trials": None,
            "n_passed": None,
            "n_failed": None,
            "n_errored": None,
            "valid_stump_pct": None,
        }
        has_any = bool(local)
        stump_pct = local.get("stump_pct") if local else None
        band = band_for(stump_pct, None, has_any)
        sort_score = stump_pct
        meta_row = latest_index.get(task["uuid"]) or {}
        record = {
            **{k: v for k, v in task.items() if k != "instruction"},
            "revisions": meta_row.get("revisions"),
            "latest_submission": meta_row.get("latest_name"),
            "local": local,
            "public": public,
            "stump_pct": stump_pct,
            "band": band,
            "sort_score": sort_score,
            "inferred_failure_modes": inferred_failure_modes(
                task["id"], task["category"], task["instruction"]
            ),
        }
        records.append(record)
        (TASK_CARDS_DIR / f"{task['id']}.md").write_text(
            write_card(task, local, public, band), encoding="utf-8"
        )

    diff_rank = {"hard": 0, "medium": 1, "easy": 2}
    records.sort(
        key=lambda r: (
            0 if r["sort_score"] is not None else 1,
            -(r["sort_score"] or 0),
            diff_rank.get(str(r.get("difficulty") or "").lower(), 3),
            r["id"],
        )
    )

    jsonl_path = CATALOG_DIR / "tasks.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for record in records:
            slim = dict(record)
            slim.pop("instruction_summary", None)
            fh.write(json.dumps(slim, ensure_ascii=False) + "\n")

    bands = defaultdict(int)
    for record in records:
        bands[record["band"]] += 1
    n_stump_known = sum(1 for r in records if r["stump_pct"] is not None)
    n_public = sum(1 for r in records if r["public"].get("leaderboard_unsolved_pct") is not None)

    index_rows = []
    for record in records:
        score = record["stump_pct"]
        score_s = f"{score:.1f}" if score is not None else "—"
        unsolved = record["public"].get("leaderboard_unsolved_pct")
        unsolved_s = f"{unsolved:.1f}" if unsolved is not None else "—"
        local = record["local"] or {}
        n_trials = local.get("n_trials") or record["public"].get("n_trials") or "—"
        valid_fail = local.get("valid_fail")
        if valid_fail is None:
            valid_fail = record["public"].get("n_failed")
        timeout = local.get("timeout")
        if timeout is None:
            timeout = record["public"].get("n_errored")
        index_rows.append(
            f"| [{record['id']}](tasks/{record['id']}.md) | {record.get('uuid', '')[:8]} | "
            f"{record['category'] or '—'} | {record['difficulty'] or '—'} | "
            f"{record.get('revisions') or '—'} | {n_trials} | "
            f"{valid_fail if valid_fail is not None else '—'} | "
            f"{timeout if timeout is not None else '—'} | {score_s} | `{record['band']}` |"
        )

    index = f"""# Terminal-Bench task catalog

Generated {inventory['generated_at']}.

Source: private `terminal-bench-tasks.zip` archive — latest revision of each
submission UUID under `tasks/latest` ({inventory['n_task_folders']} tasks).
Official GitHub terminal-bench-2 is **not** included.
Harbor trials found inside those submissions: **{inventory['n_local_trials']}**.

## How stump % is computed

- **Valid failure** = agent finished and the verifier scored 0.
- Timeouts and infra errors are excluded from stump %.
- `stump_pct = valid_failures / completed_trials * 100`.
- Band `stumps` means pass rate ≤ 40% (Terminus-like 0–2/5), i.e. stump ≥ 60%.
- `no_logs` means the submission zip had no Harbor `result.json` / `reward.txt`.
  We did not invent a stump % from the public TB2 leaderboard.

## Counts

- Tasks: {len(records)}
- Band `stumps`: {bands['stumps']}
- Band `borderline`: {bands['borderline']}
- Band `too_easy`: {bands['too_easy']}
- Band `no_logs`: {bands['no_logs']}
- Tasks with a measured stump %: {n_stump_known}

## Ranked tasks

| Task | UUID | Category | Difficulty | revisions | n_trials | valid_fail | timeout/infra | stump % | band |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
{chr(10).join(index_rows)}
"""
    (CATALOG_DIR / "index.md").write_text(index, encoding="utf-8")
    (CATALOG_DIR / "inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")

    readme = f"""# Catalog notes

Analysis catalog of the private Terminal-Bench archive (`terminal-bench-tasks.zip`).

## What is here

- [index.md](index.md) — ranked table and stump bands
- [tasks/](tasks/) — one card per task (summary, logs, agent, stump)
- [tasks.jsonl](tasks.jsonl) — machine-readable records
- [inventory.json](inventory.json) — source inventory

## Sources used

1. Task source: `tasks/latest` — latest zip per submission UUID from
   `terminal-bench-tasks.zip` (1170 submission archives, 448 unique tasks).
2. Harbor jobs: scanned `{', '.join(inventory['job_roots_configured'])}`.
   Found {inventory['n_local_trials']} trial `result.json` files inside the
   extracted submissions. Most zips are task source only (no agent run logs).
3. Official GitHub TB2 and public leaderboard rates are **not** used.

## Stump-rate rules

- Oracle presence is recorded; we did not re-run oracle or NOP.
- Valid failure = completed run, reward 0.
- Timeouts / infra do not count as stumping.
- Rebuild:

```
python scripts/unpack_tasks.py
python scripts/build_catalog.py
```
"""
    (CATALOG_DIR / "README.md").write_text(readme, encoding="utf-8")
    print(f"wrote {len(records)} task cards, {jsonl_path}, index, inventory")


if __name__ == "__main__":
    main()
