from __future__ import annotations

import importlib.util
from pathlib import Path


BASE = Path("/app/task_file")
if not BASE.exists():
    BASE = Path(__file__).parent.parent / "environment" / "task_file"

spec = importlib.util.spec_from_file_location("public_model", BASE / "scripts" / "model.py")
public_model = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(public_model)


def score_strict(input_dir=None, output_dir=None):
    input_dir = input_dir or BASE / "input_data"
    output_dir = output_dir or BASE / "output_data"
    return public_model.score_strict(input_dir, output_dir)
