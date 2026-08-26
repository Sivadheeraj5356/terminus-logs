from __future__ import annotations

import hashlib


def run_journal(spec: dict) -> dict:
    from structlib.wasm_runtime import WasmRuntime

    m = WasmRuntime(spec).run()
    d = hashlib.sha256(repr(m).encode()).hexdigest()[:16]
    return {"metrics": m, "digest": d, "valid": True}
