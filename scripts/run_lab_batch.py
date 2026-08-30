"""Linux Harbor runner for frozen lab batches.

Going-forward protocol: terminus-2, -k 5, -n 1, two cheap arms
(claude-haiku-4-5 + gpt-4o-mini, with Sonnet fallback on OpenAI 429).

Do NOT use run_agents.ps1. Never print API keys. Jobs stay under gitignored jobs/.
On credit-too-low / 429, stop remaining Harbor jobs; keep completed trials.
Do not start a second `harbor run` while one is already on this host.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lab_common import (  # noqa: E402
    CHEAP_HAIKU_MODEL,
    CHEAP_SECOND_FALLBACK,
    CHEAP_SECOND_MODEL,
    JOBS_DIR,
    OPENAI_SECOND_CANDIDATES,
    PLANNED_ATTEMPTS,
    TASKS_LATEST,
    batch_jsonl_path,
    collect_trials,
    load_jsonl,
)

CREDIT_MARKERS = (
    "credit-balance-too-low",
    "credit_balance_too_low",
    "credit too low",
    "credit balance is too low",
    "credit balance too low",
    "insufficient_quota",
    "error code: 429",
    "error code: 400",
    "rate_limit",
)


def log(msg: str) -> None:
    print(msg, flush=True)


def load_env_file() -> None:
    """Load repo .env into os.environ without logging values."""
    path = ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def batch_rows(batch: int) -> list[dict]:
    path = batch_jsonl_path(batch)
    rows = load_jsonl(path)
    if len(rows) != 10:
        raise SystemExit(f"{path} has {len(rows)} rows, expected 10")
    return rows


def assert_keys() -> None:
    anthropic = os.environ.get("ANTHROPIC_API_KEY") or ""
    openai = os.environ.get("OPENAI_API_KEY") or ""
    if not anthropic:
        raise SystemExit("ANTHROPIC_API_KEY is not set in this shell.")
    if anthropic.startswith("sk-proj-"):
        raise SystemExit("ANTHROPIC_API_KEY is an OpenAI sk-proj- value. Need sk-ant-...")
    if not anthropic.startswith("sk-ant-"):
        raise SystemExit("ANTHROPIC_API_KEY must start with sk-ant-.")
    if not openai:
        raise SystemExit("OPENAI_API_KEY is not set in this shell.")
    if not (openai.startswith("sk-") or openai.startswith("sk-proj-")):
        raise SystemExit("OPENAI_API_KEY does not look like an OpenAI key.")
    log(f"Keys: anthropic_len={len(anthropic)} openai_len={len(openai)} (prefixes not printed)")


def harbor_run_lines() -> list[str]:
    try:
        proc = subprocess.run(["pgrep", "-af", "harbor run"], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return []
    lines = []
    for line in (proc.stdout or "").splitlines():
        if "harbor run" in line and "pgrep" not in line:
            lines.append(line)
    return lines


def wait_for_idle_harbor(*, timeout_s: int = 0) -> None:
    started = time.time()
    while True:
        lines = harbor_run_lines()
        if not lines:
            return
        waited = int(time.time() - started)
        log(f"Harbor already running ({len(lines)} process(es), waited {waited}s). Not starting a second job.")
        if timeout_s and waited >= timeout_s:
            raise SystemExit("Timed out waiting for the existing harbor run to finish.")
        time.sleep(20)


def confirm_harbor_k(trials: int, concurrent: int) -> None:
    if not shutil.which("harbor"):
        raise SystemExit("harbor is not on PATH. Install Harbor 0.22 on the evaluation host.")
    help_proc = subprocess.run(["harbor", "run", "--help"], capture_output=True, text=True, check=False)
    text = (help_proc.stdout or "") + "\n" + (help_proc.stderr or "")
    hits = [
        line.strip()
        for line in text.splitlines()
        if any(tok in line.lower() for tok in ("n-attempts", "n_attempts", "-k", "n-trials", "n_trials", "attempts"))
    ]
    log("Harbor n_trials vs -k (from harbor run --help):")
    for line in hits[:20]:
        log(f"  {line}")
    if not hits:
        log("  (no -k / n-attempts / n-trials lines parsed; still using -k as n_attempts)")
    log(
        f"Interpretation: n_trials = n_attempts × tasks × agents. -k {trials} => "
        f"{trials} independent trials. -n {concurrent} concurrency. --retry left off."
    )


def credit_blocked(blob: str) -> str | None:
    low = blob.lower()
    for marker in CREDIT_MARKERS:
        if marker in low:
            return marker
    return None


def job_credit_blocked(job_dir: Path) -> str | None:
    """Scan the whole Harbor job (log + trial exceptions), not just a log tail.

    A reused job directory can hide credit-too-low in the middle of job.log.
    Unique fill names avoid mixing yesterday's abort with today's trials.
    """
    if not job_dir.is_dir():
        return None
    job_log = job_dir / "job.log"
    if job_log.is_file():
        blob = job_log.read_text(encoding="utf-8", errors="replace")
        hit = credit_blocked(blob)
        if hit:
            return hit
    result_json = job_dir / "result.json"
    if result_json.is_file():
        hit = credit_blocked(result_json.read_text(encoding="utf-8", errors="replace"))
        if hit:
            return hit
    for path in job_dir.glob("*/result.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        exc = data.get("exception_info") or {}
        blob = " ".join(str(exc.get(key) or "") for key in ("exception_type", "exception_message"))
        hit = credit_blocked(blob)
        if hit:
            return hit
    return None


def api_model_id(slug: str) -> str:
    """LiteLLM `provider/model` → provider API model id."""
    value = (slug or "").strip()
    if "/" in value:
        return value.split("/", 1)[1]
    return value


def probe_http_arm(kind: str, model: str | None = None) -> dict:
    """Tiny provider probe. Does not print keys or response bodies with secrets."""
    import urllib.error
    import urllib.request

    if kind == "anthropic":
        model = model or "claude-haiku-4-5"
        key = os.environ.get("ANTHROPIC_API_KEY") or ""
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(
                {
                    "model": api_model_id(model),
                    "max_tokens": 8,
                    "messages": [{"role": "user", "content": "ping"}],
                }
            ).encode(),
            headers={
                "content-type": "application/json",
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
    else:
        model = model or "gpt-4o-mini"
        key = os.environ.get("OPENAI_API_KEY") or ""
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(
                {
                    "model": api_model_id(model),
                    "max_tokens": 8,
                    "messages": [{"role": "user", "content": "ping"}],
                }
            ).encode(),
            headers={
                "content-type": "application/json",
                "authorization": f"Bearer {key}",
            },
            method="POST",
        )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            code = resp.getcode()
            body = resp.read(400).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        code = exc.code
        body = exc.read(400).decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": 0, "error": type(exc).__name__, "blocked": str(exc)[:80]}
    blocked = credit_blocked(body)
    return {
        "ok": 200 <= code < 300 and not blocked,
        "status": code,
        "blocked": blocked,
        "model": api_model_id(model),
    }


def openai_candidate_slugs(preferred: str | None = None) -> list[str]:
    slugs: list[str] = []
    want = (preferred or "").strip()
    if want.startswith("openai/"):
        slugs.append(want)
    elif want and not want.startswith("anthropic/"):
        slugs.append(want if "/" in want else f"openai/{want}")
    for slug in OPENAI_SECOND_CANDIDATES:
        if slug not in slugs:
            slugs.append(slug)
    return slugs


def probe_openai_candidates(
    preferred: str | None = None, *, stop_on_first_ok: bool = False
) -> tuple[str | None, list[dict]]:
    """Probe cheap OpenAI slugs in protocol order. First HTTP 200 wins."""
    hits: list[dict] = []
    chosen: str | None = None
    for slug in openai_candidate_slugs(preferred):
        hit = probe_http_arm("openai", model=slug)
        row = {
            "slug": slug,
            "ok": hit.get("ok"),
            "status": hit.get("status"),
            "blocked": hit.get("blocked"),
        }
        hits.append(row)
        log(f"OpenAI {slug} probe: status={row['status']} ok={row['ok']} blocked={row['blocked']}")
        if hit.get("ok") and chosen is None:
            chosen = slug
            if stop_on_first_ok:
                break
    return chosen, hits


def write_stop(batch: int, payload: dict) -> Path:
    path = ROOT / "docs" / f"lab_batch_{int(batch):02d}_stop.json"
    body = dict(payload)
    body.setdefault("generated_utc", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    body.setdefault("batch", int(batch))
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    log(f"wrote {path.relative_to(ROOT)}")
    return path


# Credit/quota infra is not a Harbor attempt. Timeout still counts (the agent ran).
ATTEMPT_CLASSES = frozenset({"solved", "valid_fail", "timeout"})


def _model_matches(row: dict, model: str) -> bool:
    name = (row.get("model") or "").lower()
    agent = (row.get("agent") or "").lower()
    if agent == "oracle" or "oracle" in name:
        return False
    want = (model or "").lower()
    if not want:
        return True
    hay = name or agent
    return want in hay or hay in want


def recorded_n(slug: str, model: str, jobs_dir: Path) -> int:
    """All recorded non-oracle trials for this model (including credit infra)."""
    trials = collect_trials(jobs_dir)
    rows = trials.get(slug) or []
    n = 0
    seen = set()
    for row in rows:
        marker = row.get("trial_dir")
        if marker in seen:
            continue
        seen.add(marker)
        if _model_matches(row, model):
            n += 1
    return n


def attempted_n(slug: str, model: str, jobs_dir: Path) -> int:
    """Trials that count toward k=5: solved, valid_fail, or timeout. Infra does not."""
    trials = collect_trials(jobs_dir)
    rows = trials.get(slug) or []
    n = 0
    seen = set()
    for row in rows:
        marker = row.get("trial_dir")
        if marker in seen:
            continue
        seen.add(marker)
        if not _model_matches(row, model):
            continue
        if (row.get("classification") or "") in ATTEMPT_CLASSES:
            n += 1
    return n


def remaining_k(slug: str, model: str, planned: int, jobs_dir: Path) -> int:
    have = attempted_n(slug, model, jobs_dir)
    return max(0, planned - have)


def run_harbor(*, package: str, agent: str, model: str, k: int, job_name: str, concurrent: int, jobs_dir: Path) -> dict:
    pkg = TASKS_LATEST / package
    if not pkg.is_dir():
        raise SystemExit(f"Package missing: {pkg}")
    wait_for_idle_harbor()
    argv = [
        "harbor",
        "run",
        "-p",
        str(pkg),
        "-a",
        agent,
        "-k",
        str(k),
        "-n",
        str(concurrent),
        "-o",
        str(jobs_dir),
        "--job-name",
        job_name,
        "-y",
    ]
    if model:
        argv = [
            "harbor",
            "run",
            "-p",
            str(pkg),
            "-a",
            agent,
            "-m",
            model,
            "-k",
            str(k),
            "-n",
            str(concurrent),
            "-o",
            str(jobs_dir),
            "--job-name",
            job_name,
            "-y",
        ]
    log(">> " + " ".join(argv))
    jobs_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(argv, text=True, check=False, capture_output=False)
    blocked = job_credit_blocked(jobs_dir / job_name)
    # Nested Docker vfs grows fast; reclaim unused images between jobs.
    subprocess.run(["docker", "image", "prune", "-f"], check=False, capture_output=True)
    subprocess.run(["docker", "builder", "prune", "-af"], check=False, capture_output=True)
    return {
        "returncode": proc.returncode,
        "job_name": job_name,
        "blocked": blocked,
        "ok": proc.returncode == 0 and not blocked,
    }


def short_slug(slug: str, n: int = 28) -> str:
    return slug[:n]


class StopMeasure(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def measure_arm(*, rows: list[dict], model: str, arm: str, batch: int, planned: int, concurrent: int, jobs_dir: Path) -> None:
    for row in rows:
        slug = row["slug"]
        stalled = 0
        while True:
            k = remaining_k(slug, model, planned, jobs_dir)
            have = attempted_n(slug, model, jobs_dir)
            recorded = recorded_n(slug, model, jobs_dir)
            if k <= 0:
                log(
                    f"skip {arm} {slug[:48]} — {have} non-infra attempts "
                    f"(recorded={recorded}) already meet k={planned}"
                )
                break
            stamp = datetime.now(timezone.utc).strftime("%H%M%S")
            log(
                f"{arm} {slug[:48]} remaining k={k} "
                f"(non-infra attempts={have}, recorded including infra={recorded})"
            )
            # Unique name so Harbor does not resume yesterday's aborted fill dir.
            job = f"lab{batch:02d}-{arm}-{short_slug(slug)}-fill{k}-{stamp}"
            result = run_harbor(
                package=slug,
                agent="terminus-2",
                model=model,
                k=k,
                job_name=job,
                concurrent=concurrent,
                jobs_dir=jobs_dir,
            )
            if result["blocked"]:
                raise StopMeasure(f"{arm} blocked ({result['blocked']}) on {slug}")
            if result["returncode"] != 0:
                raise StopMeasure(f"{arm} harbor exit {result['returncode']} on {slug}")
            subprocess.run([sys.executable, str(ROOT / "scripts" / "ingest_lab_jobs.py")], check=False)
            subprocess.run([sys.executable, str(ROOT / "scripts" / "write_loss_notes.py")], check=False)
            after = attempted_n(slug, model, jobs_dir)
            if after <= have:
                stalled += 1
                log(
                    f"{arm} {slug[:48]} added no counted attempts "
                    f"(still {after}); stall {stalled}/2"
                )
                if stalled >= 2:
                    log(f"leaving {arm} {slug[:48]} short of k={planned}")
                    break
            else:
                stalled = 0


def phase_probe(args: argparse.Namespace) -> None:
    assert_keys()
    confirm_harbor_k(args.trials, args.concurrent)
    if not shutil.which("docker"):
        raise SystemExit("docker is not on PATH.")
    docker = subprocess.run(["docker", "info"], capture_output=True, text=True, check=False)
    if docker.returncode != 0:
        raise SystemExit("docker info failed.")
    anth = probe_http_arm("anthropic")
    log(
        f"Anthropic probe: status={anth.get('status')} ok={anth.get('ok')} "
        f"blocked={anth.get('blocked')}"
    )
    chosen, oai_hits = probe_openai_candidates(args.second_model)
    primary = next((row for row in oai_hits if row["slug"] == args.second_model), None)
    if primary is None:
        primary = oai_hits[0] if oai_hits else {"ok": False, "status": 0, "blocked": None}
    probe_path = ROOT / "docs" / f"lab_batch_{args.batch:02d}_status.json"
    payload = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "batch": args.batch,
        "planned_attempts": args.trials,
        "haiku_model": args.haiku_model,
        "second_model": chosen or args.second_model,
        "second_fallback": args.second_fallback,
        "openai_chosen": chosen,
        "openai_candidates": oai_hits,
        "anthropic": {k: anth.get(k) for k in ("ok", "status", "blocked")},
        "openai": {k: primary.get(k) for k in ("ok", "status", "blocked")},
        "harbor_running": harbor_run_lines(),
        "note": (
            "Probe only. Do not invent scores. Keys are not written. "
            "Harbor is not started when both cheap providers are blocked."
        ),
    }
    probe_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    log(f"wrote {probe_path.relative_to(ROOT)}")
    if not anth.get("ok") and not chosen:
        write_stop(
            args.batch,
            {
                "reason": "both cheap providers blocked",
                "halt_iterate": True,
                "anthropic": {k: anth.get(k) for k in ("ok", "status", "blocked")},
                "openai_chosen": None,
                "openai_candidates": oai_hits,
                "note": (
                    "Keep completed trials. Do not invent scores. "
                    "No second harbor run started."
                ),
            },
        )
        raise SystemExit("both cheap providers blocked (credit/429). Not starting Harbor.")
    if not anth.get("ok"):
        log(
            "Anthropic not ready; Haiku arm will be skipped. "
            f"OpenAI second arm can still run ({chosen})."
        )
    if not chosen:
        log(
            "All OpenAI slugs blocked; second arm will fall back to "
            f"{args.second_fallback} if Anthropic still has credit."
        )


def resolve_second_model(args: argparse.Namespace) -> str:
    chosen, _hits = probe_openai_candidates(args.second_model, stop_on_first_ok=True)
    if chosen:
        return chosen
    log(
        f"All OpenAI candidates blocked; falling back to {args.second_fallback}"
    )
    anth = probe_http_arm("anthropic")
    if not anth.get("ok"):
        raise StopMeasure("both cheap second-arm providers blocked")
    return args.second_fallback


def phase_oracle(args: argparse.Namespace) -> None:
    assert_keys()
    rows = batch_rows(args.batch)
    for i, row in enumerate(rows, start=1):
        run_harbor(
            package=row["slug"],
            agent="oracle",
            model="",
            k=1,
            job_name=f"lab{args.batch:02d}-oracle-{short_slug(row['slug'], 40)}",
            concurrent=args.concurrent,
            jobs_dir=JOBS_DIR,
        )
        if args.stop_after_tasks and i >= args.stop_after_tasks:
            log(f"StopAfterTasks={args.stop_after_tasks}")
            break


def phase_smoke(args: argparse.Namespace) -> str:
    assert_keys()
    confirm_harbor_k(1, args.concurrent)
    slug = args.smoke_slug or batch_rows(args.batch)[0]["slug"]
    haiku = run_harbor(
        package=slug,
        agent="terminus-2",
        model=args.haiku_model,
        k=1,
        job_name=f"lab{args.batch:02d}-smoke-haiku",
        concurrent=1,
        jobs_dir=JOBS_DIR,
    )
    if haiku["blocked"] or haiku["returncode"] != 0:
        raise SystemExit("Haiku smoke failed. Do not start the k=5 measure.")
    second = resolve_second_model(args)
    smoke = run_harbor(
        package=slug,
        agent="terminus-2",
        model=second,
        k=1,
        job_name=f"lab{args.batch:02d}-smoke-second",
        concurrent=1,
        jobs_dir=JOBS_DIR,
    )
    if smoke["blocked"] or smoke["returncode"] != 0:
        raise SystemExit(f"Second-arm smoke failed on {second}.")
    log(f"Smoke ok. Second arm={second}. Measure with --yes-measure.")
    return second


def phase_measure(args: argparse.Namespace) -> None:
    assert_keys()
    if not args.yes_measure:
        raise SystemExit("Refusing cheap k=5 measure without --yes-measure. Run --phase smoke first.")
    rows = batch_rows(args.batch)
    if args.stop_after_tasks:
        rows = rows[: args.stop_after_tasks]
    haiku_reason = None
    second_reason = None
    second_used = None
    anth = probe_http_arm("anthropic")
    try:
        if anth.get("ok"):
            measure_arm(
                rows=rows,
                model=args.haiku_model,
                arm="haiku",
                batch=args.batch,
                planned=args.trials,
                concurrent=args.concurrent,
                jobs_dir=JOBS_DIR,
            )
        else:
            haiku_reason = (
                f"haiku skipped (anthropic blocked={anth.get('blocked')} "
                f"status={anth.get('status')})"
            )
            log(haiku_reason + ". Continuing second arm if a provider is ready.")
    except StopMeasure as exc:
        haiku_reason = exc.reason
        log(f"Haiku STOP: {exc.reason}. Keeping completed trials. Continuing second arm.")
    try:
        second_used = resolve_second_model(args)
        measure_arm(
            rows=rows,
            model=second_used,
            arm="second",
            batch=args.batch,
            planned=args.trials,
            concurrent=args.concurrent,
            jobs_dir=JOBS_DIR,
        )
    except StopMeasure as exc:
        second_reason = exc.reason
        log(f"Second STOP: {exc.reason}. Keeping completed trials. Not inventing the rest.")
    if haiku_reason or second_reason:
        halt = bool(haiku_reason and second_reason)
        write_stop(
            args.batch,
            {
                "reason": " ; ".join(x for x in (haiku_reason, second_reason) if x),
                "halt_iterate": halt,
                "haiku_stop": haiku_reason,
                "second_stop": second_reason,
                "second_model_used": second_used,
                "note": "Keep completed trials. Do not invent scores.",
            },
        )
        if halt:
            log("both arms blocked; halt iterate")


def phase_empty(args: argparse.Namespace) -> None:
    for row in batch_rows(args.batch):
        run_harbor(
            package=row["slug"],
            agent="nop",
            model="",
            k=1,
            job_name=f"lab{args.batch:02d}-nop-{short_slug(row['slug'])}",
            concurrent=args.concurrent,
            jobs_dir=JOBS_DIR,
        )


def phase_classify() -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "ingest_lab_jobs.py")], check=False)
    catalog = ROOT / "scripts" / "update_catalog_from_jobs.py"
    if catalog.is_file():
        subprocess.run([sys.executable, str(catalog)], check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=["probe", "oracle", "smoke", "measure", "empty", "classify", "all"],
        default="probe",
    )
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--haiku-model", default=CHEAP_HAIKU_MODEL)
    parser.add_argument("--second-model", default=CHEAP_SECOND_MODEL)
    parser.add_argument("--second-fallback", default=CHEAP_SECOND_FALLBACK)
    parser.add_argument("--smoke-slug", default="")
    parser.add_argument("--trials", type=int, default=PLANNED_ATTEMPTS)
    parser.add_argument("--concurrent", type=int, default=1)
    parser.add_argument("--stop-after-tasks", type=int, default=0)
    parser.add_argument("--yes-measure", action="store_true")
    args = parser.parse_args()
    load_env_file()

    if args.phase == "probe":
        phase_probe(args)
    elif args.phase == "oracle":
        phase_oracle(args)
    elif args.phase == "smoke":
        phase_smoke(args)
    elif args.phase == "measure":
        phase_measure(args)
    elif args.phase == "empty":
        phase_empty(args)
    elif args.phase == "classify":
        phase_classify()
    elif args.phase == "all":
        phase_probe(args)
        phase_oracle(args)
        phase_smoke(args)
        if args.yes_measure:
            phase_measure(args)
        else:
            log("Smoke finished. Re-run with --phase measure --yes-measure to spend cheap k=5 jobs.")
        phase_classify()


if __name__ == "__main__":
    main()
