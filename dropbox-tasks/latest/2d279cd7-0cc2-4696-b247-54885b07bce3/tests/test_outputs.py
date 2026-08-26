import os
import subprocess
import json
import tempfile

if False:
    subprocess.run(["node", "/app/environment/../run_entry.js", "config.json", "output.json"])


def _temp_path(suffix):
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        return f.name


def run_simulation(config_updates, extra_args=None, env=None, capped=False):
    defaults_path = "/app/config/defaults.json"
    with open(defaults_path, "r") as f:
        config = json.load(f)

    config.update(config_updates)

    cfg_path = _temp_path(".json")
    out_path = _temp_path(".json")

    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    try:
        with open(cfg_path, "w") as f:
            json.dump(config, f)

        if capped:
            res = subprocess.run(
                ["/app/run_capped.sh", cfg_path, out_path, *(extra_args or [])],
                capture_output=True,
                text=True,
                env=run_env,
            )
        else:
            res = subprocess.run(
                ["node", "/app/run_entry.js", cfg_path, out_path, *(extra_args or [])],
                capture_output=True,
                text=True,
                env=run_env,
            )

        output_data = None
        if res.returncode == 0 and os.path.exists(out_path):
            with open(out_path, "r") as f:
                output_data = json.load(f)

        return res.returncode, output_data, res.stdout + res.stderr
    finally:
        if os.path.exists(cfg_path):
            os.remove(cfg_path)
        if os.path.exists(out_path):
            os.remove(out_path)


def load_boundaries(halo_profile="default"):
    if halo_profile == "mixed":
        path = "/app/fixtures/halo_mixed.json"
    else:
        path = "/app/fixtures/halo_configuration.json"
    with open(path, "r") as f:
        return json.load(f)["boundaries"]


def reference_solve(grid_size, c, dx, dt, steps, stride, order, boundaries):
    ghost = 2
    W = grid_size + 2 * ghost
    prev = [0.0] * (W * W)
    curr = [0.0] * (W * W)
    next_grid = [0.0] * (W * W)

    centerX = grid_size / 2.0
    centerY = grid_size / 2.0
    sigma = 5.0
    amplitude = 5.0

    for i in range(grid_size):
        for j in range(grid_size):
            dist2 = (i - centerX) ** 2 + (j - centerY) ** 2
            val = amplitude * (2.718281828459045 ** (-dist2 / (2.0 * sigma**2)))
            idx = (i + ghost) * W + (j + ghost)
            curr[idx] = val
            prev[idx] = val

    def apply_boundaries(grid):
        N = grid_size
        H = ghost
        for i in range(W):
            row = i * W
            if boundaries["left"] == "dirichlet":
                for d in range(H):
                    grid[row + d] = 0.0
            elif boundaries["left"] == "neumann":
                for d in range(1, H + 1):
                    grid[row + H - d] = grid[row + H + d]

            if boundaries["right"] == "dirichlet":
                for d in range(H):
                    grid[row + H + N + d] = 0.0
            elif boundaries["right"] == "neumann":
                for d in range(1, H + 1):
                    grid[row + H + N - 1 + d] = grid[row + H + N - 1 - d]

        for j in range(W):
            if boundaries["top"] == "dirichlet":
                for d in range(H):
                    grid[d * W + j] = 0.0
            elif boundaries["top"] == "neumann":
                for d in range(1, H + 1):
                    grid[(H - d) * W + j] = grid[(H + d) * W + j]

            if boundaries["bottom"] == "dirichlet":
                for d in range(H):
                    grid[(H + N + d) * W + j] = 0.0
            elif boundaries["bottom"] == "neumann":
                for d in range(1, H + 1):
                    grid[(H + N - 1 + d) * W + j] = grid[(H + N - 1 - d) * W + j]

    apply_boundaries(prev)
    apply_boundaries(curr)

    traces = []

    def get_interior(grid):
        res = []
        for i in range(grid_size):
            row = (i + ghost) * W
            for j in range(grid_size):
                res.append(grid[row + ghost + j])
        return res

    if 0 % stride == 0:
        traces.append({"step": 0, "grid": get_interior(curr)})

    for step in range(1, steps + 1):
        apply_boundaries(curr)

        factor = (c * c) * (dt * dt)
        if order == 2:
            coeff = factor / (dx * dx)
            for i in range(ghost, grid_size + ghost):
                row = i * W
                for j in range(ghost, grid_size + ghost):
                    idx = row + j
                    laplacian = (
                        curr[idx + 1] + curr[idx - 1]
                        + curr[idx + W] + curr[idx - W]
                        - 4.0 * curr[idx]
                    )
                    next_grid[idx] = 2.0 * curr[idx] - prev[idx] + coeff * laplacian
        elif order == 4:
            coeff = factor / (12.0 * dx * dx)
            for i in range(ghost, grid_size + ghost):
                row = i * W
                for j in range(ghost, grid_size + ghost):
                    idx = row + j
                    laplacian = (
                        -curr[idx + 2] - curr[idx - 2]
                        - curr[idx + 2 * W] - curr[idx - 2 * W]
                        + 16.0 * (
                            curr[idx + 1] + curr[idx - 1]
                            + curr[idx + W] + curr[idx - W]
                        )
                        - 60.0 * curr[idx]
                    )
                    next_grid[idx] = 2.0 * curr[idx] - prev[idx] + coeff * laplacian

        apply_boundaries(next_grid)

        prev, curr = curr, prev
        curr, next_grid = next_grid, curr

        if step % stride == 0:
            traces.append({"step": step, "grid": get_interior(curr)})

    return traces


def assert_traces_match(output_data, ref_traces, tol=1e-5):
    assert len(output_data["traces"]) == len(ref_traces)
    for t_idx, trace in enumerate(output_data["traces"]):
        ref_grid = ref_traces[t_idx]["grid"]
        sim_grid = trace["grid"]
        assert len(sim_grid) == len(ref_grid)
        for i in range(len(ref_grid)):
            assert abs(sim_grid[i] - ref_grid[i]) <= tol, (
                f"Mismatch at step {trace['step']}, index {i}: "
                f"sim {sim_grid[i]} vs ref {ref_grid[i]}"
            )


def test_t01_mixed_edge_convergence():
    """Mixed-edge configuration converges to reference within physical tolerances."""
    ret, output_data, output_log = run_simulation({
        "gridSize": 64,
        "steps": 30,
        "stride": 10,
        "order": 2,
        "haloProfile": "mixed",
        "dx": 0.1,
        "dt": 0.05,
    })
    assert ret == 0, f"Simulation exit: {output_log}"
    assert output_data is not None

    boundaries = load_boundaries("mixed")
    ref_traces = reference_solve(64, 1.0, 0.1, 0.05, 30, 10, 2, boundaries)
    assert_traces_match(output_data, ref_traces)


def test_t02_heap_triple_run():
    """Three sequential large runs complete under external heap ceiling."""
    cfg = {
        "gridSize": 128,
        "steps": 100,
        "stride": 20,
        "order": 2,
    }
    for run_idx in range(3):
        ret, output_data, output_log = run_simulation(cfg, capped=True)
        assert ret == 0, (
            f"Run {run_idx} exit {ret} under capped runner: {output_log}"
        )
        assert output_data is not None


def test_t03_dt_limit():
    """Rejects dt values that violate Courant-Friedrichs-Lewy limits."""
    ret, output_data, output_log = run_simulation({
        "gridSize": 32,
        "steps": 10,
        "dt": 0.08,
        "order": 2,
    })
    assert ret != 0, "Expected simulation to exit with error due to CFL violation for order 2"
    assert "CFL" in output_log

    ret2, output_data2, output_log2 = run_simulation({
        "gridSize": 32,
        "steps": 10,
        "dt": 0.05,
        "order": 4,
    })
    assert ret2 != 0, "Expected simulation to exit with error due to CFL violation for order 4"
    assert "CFL" in output_log2


def test_t04_rim_blowup():
    """Long mixed-edge run remains finite without late-stage blowup."""
    ret, output_data, output_log = run_simulation({
        "gridSize": 64,
        "steps": 220,
        "stride": 20,
        "order": 2,
        "haloProfile": "mixed",
    })
    assert ret == 0, f"Simulation exit: {output_log}"
    assert output_data is not None

    for trace in output_data["traces"]:
        for val in trace["grid"]:
            assert val == val, f"NaN detected at step {trace['step']}"
            assert abs(val) < float("inf"), f"Non-finite value at step {trace['step']}"


def test_t05_trace_immutable():
    """Emitted trace snapshots do not alias live buffer storage."""
    js_code = """
    const { op_a } = require('/app/base/src/op_a.js');
    const { sample_d } = require('/app/trace/src/sample_d.js');

    const buffers = op_a(32, 2);
    const { curr, prev, width, ghost } = buffers;
    for (let i = 0; i < 32; i++) {
        const row = (i + ghost) * width;
        for (let j = 0; j < 32; j++) {
            const idx = row + ghost + j;
            const v = Math.exp(-((i - 16) ** 2 + (j - 16) ** 2) / 50);
            curr[idx] = v;
            prev[idx] = v;
        }
    }
    const snap = sample_d(buffers, 0, 0.0);
    const saved = snap.grid.slice();
    const overwrite = 1.0 + Math.random();
    for (let k = 0; k < curr.length; k++) curr[k] = overwrite;
    let drift = 0;
    for (let i = 0; i < saved.length; i++) {
        drift += Math.abs(snap.grid[i] - saved[i]);
    }
    console.log(drift);
    """
    path_js = _temp_path(".js")
    try:
        with open(path_js, "w") as f:
            f.write(js_code)
        res = subprocess.run(["node", path_js], capture_output=True, text=True, cwd="/app")
        assert res.returncode == 0, res.stderr
        drift = float(res.stdout.strip())
        assert drift < 1e-9, f"sample_d aliases live buffer (drift={drift})"
    finally:
        if os.path.exists(path_js):
            os.remove(path_js)


def test_t06_order_trade():
    """Order 4 matches reference solver; order 2 and 4 stencils diverge."""
    cfg = {
        "gridSize": 32,
        "steps": 10,
        "stride": 10,
        "dt": 0.015,
    }
    ret2, out2, log2 = run_simulation({**cfg, "order": 2})
    ret4, out4, log4 = run_simulation({**cfg, "order": 4})

    assert ret2 == 0, f"Order 2 run exit: {log2}"
    assert ret4 == 0, f"Order 4 run exit: {log4}"

    boundaries = load_boundaries("default")
    ref4 = reference_solve(32, 1.0, 0.1, 0.015, 10, 10, 4, boundaries)
    assert_traces_match(out4, ref4)

    grid2 = out2["traces"][-1]["grid"]
    grid4 = out4["traces"][-1]["grid"]
    diff = sum(abs(a - b) for a, b in zip(grid2, grid4))
    assert diff > 1e-6, "Order 2 and Order 4 stencils produced identical results"


def test_t07_restart_hygiene():
    """Sequential allocations return zero-initialized storage."""
    js_code = """
    const { op_a } = require('/app/base/src/op_a.js');

    const buffers1 = op_a(32, 2);
    buffers1.curr.fill(1.0);

    const buffers2 = op_a(32, 2);
    let sum = 0;
    for (let i = 0; i < buffers2.curr.length; i++) {
        sum += buffers2.curr[i];
    }
    console.log(sum);
    """
    path_js = _temp_path(".js")
    try:
        with open(path_js, "w") as f:
            f.write(js_code)
        res = subprocess.run(["node", path_js], capture_output=True, text=True, cwd="/app")
        assert res.returncode == 0
        sum_val = float(res.stdout.strip())
        assert sum_val == 0.0, (
            f"Restart hygiene failure: sequential allocation returned dirty buffer with sum {sum_val}"
        )
    finally:
        if os.path.exists(path_js):
            os.remove(path_js)


def test_t09_split_run_fidelity():
    """Interrupted checkpoint resume matches uninterrupted reference stream."""
    ckpt_path = "/app/work/sim.ckpt"
    if os.path.exists(ckpt_path):
        os.remove(ckpt_path)

    common = {
        "gridSize": 32,
        "steps": 200,
        "stride": 50,
        "order": 2,
        "dx": 0.1,
        "dt": 0.05,
    }

    ret_full, out_full, log_full = run_simulation(common)
    assert ret_full == 0, f"Continuous run exit: {log_full}"

    half = dict(common)
    half["steps"] = 100
    ret_a, out_a, log_a = run_simulation(
        half,
        extra_args=["--checkpoint", ckpt_path],
    )
    assert ret_a == 0, f"First segment exit: {log_a}"
    assert os.path.exists(ckpt_path), "Checkpoint file not written"

    ret_b, out_b, log_b = run_simulation(
        common,
        extra_args=["--checkpoint", ckpt_path, "--resume"],
    )
    assert ret_b == 0, f"Resumed run exit: {log_b}"

    boundaries = load_boundaries("default")
    ref_traces = reference_solve(32, 1.0, 0.1, 0.05, 200, 50, 2, boundaries)
    assert_traces_match(out_full, ref_traces)

    final_ref = ref_traces[-1]["grid"]
    final_split = out_b["traces"][-1]["grid"]
    for i in range(len(final_ref)):
        assert abs(final_split[i] - final_ref[i]) <= 1e-5, (
            f"Split-run final mismatch at {i}: {final_split[i]} vs {final_ref[i]}"
        )

    mid_ref = next(t for t in ref_traces if t["step"] == 100)["grid"]
    mid_split = next(t for t in out_a["traces"] if t["step"] == 100)["grid"]
    for i in range(len(mid_ref)):
        assert abs(mid_split[i] - mid_ref[i]) <= 1e-5, (
            f"First segment mismatch at step 100, index {i}"
        )

    if os.path.exists(ckpt_path):
        os.remove(ckpt_path)


def test_t10_ckpt_epoch_reject():
    """Corrupted checkpoint epoch is rejected on resume."""
    ckpt_path = "/app/work/sim.ckpt"
    if os.path.exists(ckpt_path):
        os.remove(ckpt_path)

    cfg = {
        "gridSize": 32,
        "steps": 50,
        "stride": 10,
        "order": 2,
    }
    ret, out, log = run_simulation(cfg, extra_args=["--checkpoint", ckpt_path])
    assert ret == 0, log
    assert os.path.exists(ckpt_path)

    with open(ckpt_path, "r+b") as f:
        data = bytearray(f.read())
    epoch = data[12] | (data[13] << 8) | (data[14] << 16) | (data[15] << 24)
    epoch += 1
    data[12] = epoch & 0xFF
    data[13] = (epoch >> 8) & 0xFF
    data[14] = (epoch >> 16) & 0xFF
    data[15] = (epoch >> 24) & 0xFF
    with open(ckpt_path, "wb") as f:
        f.write(data)

    ret2, out2, log2 = run_simulation(
        {"gridSize": 32, "steps": 100, "stride": 10, "order": 2},
        extra_args=["--checkpoint", ckpt_path, "--resume"],
    )
    assert ret2 != 0, "Expected resume to reject stale checkpoint epoch"
    assert "epoch" in log2.lower() or "checksum" in log2.lower()

    if os.path.exists(ckpt_path):
        os.remove(ckpt_path)
