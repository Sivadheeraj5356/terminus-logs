import json
import math
import random
import sys

import numpy as np
from scipy import ndimage


def run_case(payload):
    results = []
    for item in payload["inputs"]:
        mode = item.get("mode", "reflect")
        truncate = float(item.get("truncate", 4.0))
        values = ndimage.gaussian_filter1d(
            np.asarray(item["signal"], dtype=float),
            sigma=float(item["sigma"]),
            mode=mode,
            truncate=truncate,
        )
        results.append({"filtered": [float(v) for v in values.tolist()]})
    return {"results": results}


def generate():
    rng = random.Random(101)
    inputs = []
    modes = ["reflect", "nearest", "wrap", "constant"]
    for _ in range(10):
        count = rng.choice([6, 7, 8, 9])
        signal = [round(rng.uniform(-2.0, 2.5) + 0.4 * math.sin(i), 6) for i in range(count)]
        inputs.append({
            "signal": signal,
            "sigma": rng.choice([0.6, 1.0, 1.4]),
            "mode": rng.choice(modes),
            "truncate": rng.choice([2.0, 3.5, 4.0]),
        })
    return {"inputs": inputs}


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--generate":
        print(json.dumps(generate()))
        raise SystemExit(0)
    with open(sys.argv[1], "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    print(json.dumps(run_case(payload)))
