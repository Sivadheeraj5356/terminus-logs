from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lib.journal import save_checkpoint
from structlib.wasm_runtime import WasmRuntime


def _persist_checkpoint(rt: WasmRuntime, root: Path) -> dict:
    return save_checkpoint(
        root,
        rt._generation,
        rt.fuel,
        rt.caps,
        rt.host_calls,
        rt.fuel_used,
    )


def run_journal(spec: dict) -> dict:
    m = WasmRuntime(spec).run()
    d = hashlib.sha256(repr(m).encode()).hexdigest()[:16]
    return {"metrics": m, "digest": d, "valid": True}


def run_recovery(spec: dict, data_root: Path | None = None) -> dict:
    root = data_root or Path("/app/data/wasm")
    rt = WasmRuntime(spec)
    live = rt.run()
    checkpoint = _persist_checkpoint(rt, root)
    generation = int(spec.get("profile_generation", 0)) + 1
    replay_rt = WasmRuntime(spec)
    replay = replay_rt.run_replay(checkpoint, generation)
    probes = WasmRuntime.probe_map(live, replay, checkpoint)
    segments = [
        {"label": "live", "source": "budget", "note": f"fuel_used={live[1]}; remaining={checkpoint.get('fuel_remaining', 0)}"},
        {"label": "live", "source": "access", "note": f"executed={live[0]}; violations={live[2]}"},
        {"label": "live", "source": "boundary", "note": f"escapes={live[3]}"},
        {"label": "live", "source": "audit", "note": f"cap_drift={live[4]}"},
        {"label": "replay", "source": "journal", "note": f"generation={generation}; calls={len(checkpoint.get('host_calls', []))}"},
    ]
    return {
        "live_metrics": live,
        "replay_metrics": replay,
        "live_digest": WasmRuntime.metrics_digest(live),
        "replay_digest": WasmRuntime.metrics_digest(replay),
        "probes": probes,
        "segments": segments,
        "generation": generation,
    }


def write_observations(doc: dict, out: Path | None = None) -> Path:
    target = out or Path("/app/output/sandbox_observations.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "runs": [
            {
                "label": "live",
                "generation": doc.get("generation", 0) - 1,
                "sandbox_digest": doc["live_digest"],
                "metrics": doc["live_metrics"],
                "segments": [s for s in doc["segments"] if s["label"] == "live"],
            },
            {
                "label": "replay",
                "generation": doc["generation"],
                "sandbox_digest": doc["replay_digest"],
                "metrics": doc["replay_metrics"],
                "segments": [s for s in doc["segments"] if s["label"] == "replay"],
            },
        ],
        "probes": doc["probes"],
    }
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return target
