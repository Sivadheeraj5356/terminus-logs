# Tidevault CPU training and calibration

`train.py` creates the first-party checkpoint lineage for this task. It plays deterministic exploratory Tidevault games with scoring tides after the half-full ninth ply and full eighteenth ply, labels every decision with a fixed tide-aware tactical teacher and the final result, trains quantized integer policy and value weights for sixteen epochs, and retains epochs 1, 2, 4, 8, and 16. Gold closes the first tide and Violet closes the second. Training uses only the Python standard library and the mirrored `core.py` and `model.py`; it requires no network, accelerator, downloaded engine, or third-party game data.

From the task directory, reproduce a release-sized lineage with:

```sh
python3 solution/training/train.py \
  --output-dir solution/training-output/tidevault-linear-v1 \
  --games 1200 \
  --seed 20260720
```

The command writes five canonical `.tvnn` files and `training.log`. Repeating it with the same source, game count, and seed must reproduce the dataset digest, checkpoint bytes, and log exactly. Checkpoint epoch is not treated as a strength claim; retained models are selected only by measured matches.

`probe.py` measures first-player balance, draw frequency, scores, margins, and final board weights under random and tide-aware tactical policies:

```sh
python3 solution/training/probe.py \
  --random-games 50000 \
  --baseline-games 2000 \
  --seed 20260720
```

`screen.py` runs every retained checkpoint pair in both colors at one equal search tuple. Its budget, width, depth, epochs, games, seed, and checkpoint directory are command-line options. A typical screen is:

```sh
python3 solution/training/screen.py \
  --checkpoint-dir solution/training-output/tidevault-linear-v1 \
  --node-budget 512 \
  --width 24 \
  --max-depth 18 \
  --games-per-color 2
```

`tournament.py` compares any two exact checkpoints with independently specified search budgets, widths, depths, and deterministic rank-lapse settings. `difficulty_sweep.py` plays a visible, human-like tide-aware Gold proxy against a chosen runtime checkpoint across `budget:games` pairs. These tools emit canonical state hashes and payload digests so calibration records can be reproduced without relying on wall-clock timings.

Training outputs are provenance evidence and must be excluded from the flat submission archive. The protected runtime receives only the selected mid checkpoint; the solution receives only the distinct measured strong checkpoint and the source required to reproduce its public-API decisions.
