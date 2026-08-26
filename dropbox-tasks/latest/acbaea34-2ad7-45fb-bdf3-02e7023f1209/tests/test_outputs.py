"""Behavior tests for the thermal cycle simulation task."""

import copy
import csv
import grp
import json
import os
import pwd
import subprocess
from pathlib import Path

APP = Path("/app")
CLI = APP / "src" / "cli.js"
BASELINE = APP / "config" / "baseline.json"
THIN_PANEL = APP / "config" / "thin-panel.json"
SUMMARY_KEYS = [
    "scenario",
    "width",
    "height",
    "steps",
    "min_temperature_milli_c",
    "max_temperature_milli_c",
    "mean_temperature_milli_c",
    "hot_cell_count",
    "full_cure_cell_count",
    "peak_stress_ppm",
    "stressed_cell_count",
    "total_temperature_milli_c",
    "total_cure_ppm",
    "center_row_checksum",
    "center_column_checksum",
    "event_count",
    "first_full_cure_step",
    "stress_event_count",
    "first_stress_alert_step",
    "checkpoint_totals",
]
TRACE_KEYS = [
    "checkpoint",
    "name",
    "x",
    "y",
    "material",
    "temperature_milli_c",
    "cure_ppm",
    "local_gradient_milli_c",
    "temperature_delta_from_previous_checkpoint_milli_c",
]
MATERIAL_PROFILE_KEYS = [
    "material",
    "cell_count",
    "mean_temperature_milli_c",
    "total_cure_ppm",
    "peak_stress_ppm",
    "stress_event_count",
    "first_full_cure_step",
]
STABILITY_KEYS = [
    "checkpoint",
    "material",
    "peak_stress_ppm",
    "mean_stress_ppm",
    "stressed_cell_count",
    "new_stress_events",
]
TESTS_DIR = Path("/tests")
FIXTURES_DIR = TESTS_DIR / "fixtures"
BASELINE_FIXTURE = FIXTURES_DIR / "baseline.json"
THIN_PANEL_FIXTURE = FIXTURES_DIR / "thin-panel.json"
JS_MAX_SAFE_INTEGER = 9_007_199_254_740_991
JS_MIN_SAFE_INTEGER = -JS_MAX_SAFE_INTEGER


def chmod_if_possible(path, mode):
    try:
        path.chmod(mode)
    except OSError:
        pass


def prepare_workspace_for_agent(workspace):
    workspace.mkdir(parents=True, exist_ok=True)
    for path in [workspace, *workspace.parents]:
        if path == Path("/"):
            break
        if not str(path).startswith("/tmp"):
            continue
        chmod_if_possible(path, 0o777)
        if path == Path("/tmp"):
            break
    for root, dirs, files in os.walk(workspace):
        root_path = Path(root)
        chmod_if_possible(root_path, 0o777)
        for dirname in dirs:
            chmod_if_possible(root_path / dirname, 0o777)
        for filename in files:
            chmod_if_possible(root_path / filename, 0o666)


def restricted_user_kwargs():
    try:
        nobody = pwd.getpwnam("nobody")
        nogroup = grp.getgrnam("nogroup")
    except KeyError:
        return {}
    return {
        "user": nobody.pw_uid,
        "group": nogroup.gr_gid,
        "extra_groups": [],
    }


def hide_verifier_assets_from_submitted_code():
    for path in [Path("/tests"), Path("/oracle"), Path("/solution")]:
        if path.exists():
            chmod_if_possible(path, 0o700)


def write_node_guard(workspace):
    guard_path = workspace / "node-verifier-guard.cjs"
    if guard_path.exists():
        return guard_path
    guard_path.write_text(
        r"""
const fs = require('fs');
const path = require('path');

const blockedRoots = ['/tests', '/oracle', '/solution'];
const procRootPattern = /^\/proc\/(?:self|thread-self|\d+)\/root\/(?:tests|oracle|solution)(?:\/|$)/;
const originalRealpathSync = fs.realpathSync.native || fs.realpathSync;

function pathFrom(value) {
  if (Buffer.isBuffer(value)) return path.resolve(value.toString());
  if (value instanceof URL && value.protocol === 'file:') return path.resolve(value.pathname);
  if (typeof value === 'string') return path.resolve(value);
  return null;
}

function withinBlockedRoot(resolved) {
  return blockedRoots.some(
    (root) => resolved === root || resolved.startsWith(`${root}${path.sep}`)
  );
}

function isBlocked(value) {
  const resolved = pathFrom(value);
  if (resolved === null) return false;
  if (withinBlockedRoot(resolved) || procRootPattern.test(resolved)) return true;
  try {
    return withinBlockedRoot(originalRealpathSync.call(fs, resolved));
  } catch {
    return false;
  }
}

function blockPath(method, value) {
  if (!isBlocked(value)) return;
  const error = new Error(`verifier asset access blocked by tests: ${method}`);
  error.code = 'EACCES';
  throw error;
}

for (const method of [
  'access',
  'accessSync',
  'chmod',
  'chmodSync',
  'chown',
  'chownSync',
  'copyFile',
  'copyFileSync',
  'createReadStream',
  'createWriteStream',
  'existsSync',
  'lstat',
  'lstatSync',
  'mkdir',
  'mkdirSync',
  'open',
  'openSync',
  'opendir',
  'opendirSync',
  'readFile',
  'readFileSync',
  'readdir',
  'readdirSync',
  'readlink',
  'readlinkSync',
  'realpath',
  'realpathSync',
  'rename',
  'renameSync',
  'rm',
  'rmSync',
  'rmdir',
  'rmdirSync',
  'stat',
  'statSync',
  'unlink',
  'unlinkSync',
  'writeFile',
  'writeFileSync',
]) {
  const original = fs[method];
  if (typeof original !== 'function') continue;
  fs[method] = function guardedFsMethod(first, ...rest) {
    blockPath(method, first);
    return original.call(this, first, ...rest);
  };
}

if (fs.promises) {
  for (const method of [
    'access',
    'chmod',
    'chown',
    'copyFile',
    'lstat',
    'mkdir',
    'open',
    'opendir',
    'readFile',
    'readdir',
    'readlink',
    'realpath',
    'rename',
    'rm',
    'rmdir',
    'stat',
    'unlink',
    'writeFile',
  ]) {
    const original = fs.promises[method];
    if (typeof original !== 'function') continue;
    fs.promises[method] = async function guardedPromiseFsMethod(first, ...rest) {
      blockPath(method, first);
      return original.call(this, first, ...rest);
    };
  }
}
""".lstrip()
    )
    return guard_path


def run_node(arguments, workspace, timeout, cwd=None):
    guard_path = write_node_guard(workspace)
    prepare_workspace_for_agent(workspace)
    hide_verifier_assets_from_submitted_code()
    env = os.environ.copy()
    node_options = env.get("NODE_OPTIONS", "")
    guard_option = f"--require={guard_path}"
    env["NODE_OPTIONS"] = (
        f"{node_options} {guard_option}".strip()
        if node_options
        else guard_option
    )
    return subprocess.run(
        arguments,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        cwd=cwd,
        env=env,
        **restricted_user_kwargs(),
    )


def boundary_at(config, x, y):
    if x == 0:
        return config["boundaries"]["left"]
    if x == config["width"] - 1:
        return config["boundaries"]["right"]
    if y == 0:
        return config["boundaries"]["top"]
    if y == config["height"] - 1:
        return config["boundaries"]["bottom"]
    return None


def material_at(config, x, y):
    return (
        x // config["block_width"]
        + 2 * (y // config["block_height"])
        + config["material_offset"]
    ) % len(config["materials"])


def clamp(value, minimum, maximum):
    return min(maximum, max(minimum, value))


def rounded_mean(values):
    total = sum(values)
    count = len(values)
    return (2 * total + count) // (2 * count)


def stats(config, temperature, cure, stress):
    values = [value for row in temperature for value in row]
    cures = [value for row in cure for value in row]
    stresses = [value for row in stress for value in row]
    return {
        "total_temperature_milli_c": sum(values),
        "total_cure_ppm": sum(cures),
        "hot_cell_count": sum(
            value >= config["activation_temperature_milli_c"] for value in values
        ),
        "full_cure_cell_count": sum(
            value >= config["full_cure_ppm"] for value in cures
        ),
        "peak_stress_ppm": max(stresses),
        "stressed_cell_count": sum(
            value >= config["stress_alert_ppm"] for value in stresses
        ),
    }


def copy_fields(temperature, cure, stress):
    return {
        "temperature": [row[:] for row in temperature],
        "cure": [row[:] for row in cure],
        "stress": [row[:] for row in stress],
    }


def local_gradient(temperature, x, y):
    center = temperature[y][x]
    deltas = []
    if x > 0:
        deltas.append(abs(center - temperature[y][x - 1]))
    if x < len(temperature[0]) - 1:
        deltas.append(abs(center - temperature[y][x + 1]))
    if y > 0:
        deltas.append(abs(center - temperature[y - 1][x]))
    if y < len(temperature) - 1:
        deltas.append(abs(center - temperature[y + 1][x]))
    return max(deltas) if deltas else 0


def initial_fields(config):
    temperature = [
        [0 for _ in range(config["width"])] for _ in range(config["height"])
    ]
    cure = [
        [0 for _ in range(config["width"])] for _ in range(config["height"])
    ]
    for y in range(config["height"]):
        for x in range(config["width"]):
            boundary = boundary_at(config, x, y)
            if boundary is not None:
                temperature[y][x] = boundary["temperature_milli_c"]
                cure[y][x] = boundary["cure_ppm"]
                continue
            value = config["base_temperature_milli_c"]
            for hotspot in config["hotspots"]:
                distance = abs(x - hotspot["x"]) + abs(y - hotspot["y"])
                value += max(
                    0,
                    hotspot["peak_milli_c"]
                    - hotspot["decay_per_cell_milli_c"] * distance,
                )
            temperature[y][x] = clamp(
                value,
                config["temperature_floor_milli_c"],
                config["temperature_ceiling_milli_c"],
            )
            cure[y][x] = config["base_cure_ppm"]
    return temperature, cure


def pulse_heat(config, step, x, y):
    total = 0
    for pulse in config["heater_pulses"]:
        if pulse["start_step"] <= step <= pulse["end_step"]:
            distance = abs(x - pulse["x"]) + abs(y - pulse["y"])
            total += max(
                0,
                pulse["strength_milli_c"]
                - pulse["decay_per_cell_milli_c"] * distance,
            )
    return total


def relief_at(config, step, x, y):
    total = 0
    for window in config["relief_windows"]:
        if window["start_step"] <= step <= window["end_step"]:
            distance = abs(x - window["x"]) + abs(y - window["y"])
            if distance <= window["radius"]:
                total += max(
                    0,
                    window["relief_ppm"]
                    - window["falloff_ppm_per_cell"] * distance,
                )
    return total


def expected_result(config):
    temperature, cure = initial_fields(config)
    stress = [
        [0 for _ in range(config["width"])] for _ in range(config["height"])
    ]
    checkpoints = {"0": stats(config, temperature, cure, stress)}
    checkpoint_snapshots = {"0": copy_fields(temperature, cure, stress)}
    checkpoint_steps = set(config["checkpoint_steps"])
    crossed = {
        (x, y)
        for y in range(config["height"])
        for x in range(config["width"])
        if boundary_at(config, x, y) is None
        and cure[y][x] >= config["full_cure_ppm"]
    }
    stressed = set()
    events = []
    stress_events = []
    for step in range(1, config["steps"] + 1):
        next_temperature = [row[:] for row in temperature]
        for y in range(config["height"]):
            for x in range(config["width"]):
                boundary = boundary_at(config, x, y)
                if boundary is not None:
                    next_temperature[y][x] = boundary["temperature_milli_c"]
                    continue
                material_index = material_at(config, x, y)
                material = config["materials"][material_index]
                numerator = (
                    material["retain"] * temperature[y][x]
                    + material["horizontal"]
                    * (temperature[y][x - 1] + temperature[y][x + 1])
                    + material["vertical"]
                    * (temperature[y - 1][x] + temperature[y + 1][x])
                    + material["diagonal"]
                    * (
                        temperature[y - 1][x - 1]
                        + temperature[y - 1][x + 1]
                        + temperature[y + 1][x - 1]
                        + temperature[y + 1][x + 1]
                    )
                )
                denominator = (
                    material["retain"]
                    + 2 * material["horizontal"]
                    + 2 * material["vertical"]
                    + 4 * material["diagonal"]
                )
                mixed = numerator // denominator
                cure_term = (
                    (cure[y][x] - config["base_cure_ppm"])
                    * material["heater_gain"]
                    // 1_000_000
                )
                next_temperature[y][x] = clamp(
                    mixed + pulse_heat(config, step, x, y) + cure_term,
                    config["temperature_floor_milli_c"],
                    config["temperature_ceiling_milli_c"],
                )

        next_cure = [row[:] for row in cure]
        for y in range(config["height"]):
            for x in range(config["width"]):
                boundary = boundary_at(config, x, y)
                if boundary is not None:
                    next_cure[y][x] = boundary["cure_ppm"]
                    continue
                material_index = material_at(config, x, y)
                material = config["materials"][material_index]
                if (
                    next_temperature[y][x]
                    >= config["activation_temperature_milli_c"]
                ):
                    delta = material["cure_rate_ppm"] + (
                        next_temperature[y][x]
                        - config["activation_temperature_milli_c"]
                    ) // 2500
                else:
                    delta = -material["cool_rate_ppm"]
                next_cure[y][x] = clamp(cure[y][x] + delta, 0, 1_000_000)
                coordinate = (x, y)
                if (
                    coordinate not in crossed
                    and cure[y][x] < config["full_cure_ppm"]
                    <= next_cure[y][x]
                ):
                    crossed.add(coordinate)
                    events.append(
                        {
                            "step": step,
                            "x": x,
                            "y": y,
                            "material": material_index,
                            "temperature_milli_c": next_temperature[y][x],
                            "cure_ppm": next_cure[y][x],
                        }
                    )
        next_stress = [row[:] for row in stress]
        for y in range(config["height"]):
            for x in range(config["width"]):
                boundary = boundary_at(config, x, y)
                if boundary is not None:
                    next_stress[y][x] = 0
                    continue
                material_index = material_at(config, x, y)
                material = config["materials"][material_index]
                generated_stress = (
                    abs(next_temperature[y][x] - temperature[y][x])
                    * material["stress_gain"]
                    + max(0, next_cure[y][x] - cure[y][x])
                    * material["cure_stress_gain"]
                ) // 1000
                retained_stress = (
                    stress[y][x] * material["stress_retain_ppm"] // 1_000_000
                )
                relief = material["stress_relief_ppm"] + relief_at(
                    config, step, x, y
                )
                next_stress[y][x] = clamp(
                    retained_stress + generated_stress - relief, 0, 1_000_000
                )
                coordinate = (x, y)
                if (
                    coordinate not in stressed
                    and stress[y][x] < config["stress_alert_ppm"]
                    <= next_stress[y][x]
                ):
                    stressed.add(coordinate)
                    stress_events.append(
                        {
                            "step": step,
                            "x": x,
                            "y": y,
                            "material": material_index,
                            "stress_ppm": next_stress[y][x],
                        }
                    )
        temperature = next_temperature
        cure = next_cure
        stress = next_stress
        if step in checkpoint_steps:
            key = str(step)
            checkpoints[key] = stats(config, temperature, cure, stress)
            checkpoint_snapshots[key] = copy_fields(temperature, cure, stress)
    return {
        "temperature": temperature,
        "cure": cure,
        "stress": stress,
        "events": events,
        "stress_events": stress_events,
        "checkpoint_totals": checkpoints,
        "checkpoint_snapshots": checkpoint_snapshots,
    }


def expected_summary(config, result):
    final_stats = stats(
        config, result["temperature"], result["cure"], result["stress"]
    )
    values = [value for row in result["temperature"] for value in row]
    center_y = config["height"] // 2
    center_x = config["width"] // 2
    return {
        "scenario": config["scenario"],
        "width": config["width"],
        "height": config["height"],
        "steps": config["steps"],
        "min_temperature_milli_c": min(values),
        "max_temperature_milli_c": max(values),
        "mean_temperature_milli_c": rounded_mean(values),
        "hot_cell_count": final_stats["hot_cell_count"],
        "full_cure_cell_count": final_stats["full_cure_cell_count"],
        "peak_stress_ppm": final_stats["peak_stress_ppm"],
        "stressed_cell_count": final_stats["stressed_cell_count"],
        "total_temperature_milli_c": final_stats["total_temperature_milli_c"],
        "total_cure_ppm": final_stats["total_cure_ppm"],
        "center_row_checksum": sum(
            (x + 1) * result["temperature"][center_y][x]
            for x in range(config["width"])
        ),
        "center_column_checksum": sum(
            (y + 1) * result["temperature"][y][center_x]
            for y in range(config["height"])
        ),
        "event_count": len(result["events"]),
        "first_full_cure_step": (
            result["events"][0]["step"] if result["events"] else None
        ),
        "stress_event_count": len(result["stress_events"]),
        "first_stress_alert_step": (
            result["stress_events"][0]["step"]
            if result["stress_events"]
            else None
        ),
        "checkpoint_totals": result["checkpoint_totals"],
    }


def run_cli(config_path, out_dir):
    return run_node(
        ["node", str(CLI), "--config", str(config_path), "--out", str(out_dir)],
        out_dir.parent,
        timeout=60,
    )


def read_csv(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def expected_trace_rows(config, result):
    rows = []
    previous_temperatures = {}
    for checkpoint in config["checkpoint_steps"]:
        snapshot = result["checkpoint_snapshots"][str(checkpoint)]
        temperature = snapshot["temperature"]
        cure = snapshot["cure"]
        for sensor in config["sensor_points"]:
            x = sensor["x"]
            y = sensor["y"]
            sensor_key = sensor["name"]
            current_temperature = temperature[y][x]
            previous_temperature = previous_temperatures.get(
                sensor_key, current_temperature
            )
            rows.append(
                {
                    "checkpoint": str(checkpoint),
                    "name": sensor_key,
                    "x": str(x),
                    "y": str(y),
                    "material": str(material_at(config, x, y)),
                    "temperature_milli_c": str(current_temperature),
                    "cure_ppm": str(cure[y][x]),
                    "local_gradient_milli_c": str(local_gradient(temperature, x, y)),
                    "temperature_delta_from_previous_checkpoint_milli_c": str(
                        current_temperature - previous_temperature
                    ),
                }
            )
            previous_temperatures[sensor_key] = current_temperature
    return rows


def expected_material_profile_rows(config, result):
    rows = []
    first_event_by_material = {}
    for event in result["events"]:
        first_event_by_material.setdefault(event["material"], event["step"])
    stress_event_count_by_material = {}
    for event in result["stress_events"]:
        stress_event_count_by_material[event["material"]] = (
            stress_event_count_by_material.get(event["material"], 0) + 1
        )
    for material_index in range(len(config["materials"])):
        temperatures = []
        stresses = []
        cure_total = 0
        for y in range(config["height"]):
            for x in range(config["width"]):
                if material_at(config, x, y) == material_index:
                    temperatures.append(result["temperature"][y][x])
                    stresses.append(result["stress"][y][x])
                    cure_total += result["cure"][y][x]
        rows.append(
            {
                "material": str(material_index),
                "cell_count": str(len(temperatures)),
                "mean_temperature_milli_c": (
                    ""
                    if not temperatures
                    else str(rounded_mean(temperatures))
                ),
                "total_cure_ppm": str(cure_total),
                "peak_stress_ppm": str(max(stresses) if stresses else 0),
                "stress_event_count": str(
                    stress_event_count_by_material.get(material_index, 0)
                ),
                "first_full_cure_step": (
                    ""
                    if material_index not in first_event_by_material
                    else str(first_event_by_material[material_index])
                ),
            }
        )
    return rows


def expected_stability_rows(config, result):
    rows = []
    previous_checkpoint = 0
    for checkpoint in config["checkpoint_steps"]:
        snapshot = result["checkpoint_snapshots"][str(checkpoint)]
        stress = snapshot["stress"]
        for material_index in range(len(config["materials"])):
            values = [
                stress[y][x]
                for y in range(config["height"])
                for x in range(config["width"])
                if material_at(config, x, y) == material_index
            ]
            new_events = sum(
                previous_checkpoint < event["step"] <= checkpoint
                and event["material"] == material_index
                for event in result["stress_events"]
            )
            rows.append(
                {
                    "checkpoint": str(checkpoint),
                    "material": str(material_index),
                    "peak_stress_ppm": str(max(values) if values else 0),
                    "mean_stress_ppm": (
                        ""
                        if not values
                        else str(rounded_mean(values))
                    ),
                    "stressed_cell_count": str(
                        sum(value >= config["stress_alert_ppm"] for value in values)
                    ),
                    "new_stress_events": str(new_events),
                }
            )
        previous_checkpoint = checkpoint
    return rows


def assert_case(config_path, out_dir, verifier_config_path=None):
    config = json.loads((verifier_config_path or config_path).read_text())
    if verifier_config_path is not None:
        assert json.loads(config_path.read_text()) == config
    expected = expected_result(config)
    completed = run_cli(config_path, out_dir)
    assert completed.returncode == 0, completed.stderr
    assert sorted(path.name for path in out_dir.iterdir()) == [
        "events.csv",
        "field.csv",
        "material_profile.csv",
        "stability.csv",
        "summary.json",
        "trace.csv",
    ]
    expected_field = [
        {
            "x": str(x),
            "y": str(y),
            "material": str(material_at(config, x, y)),
            "temperature_milli_c": str(expected["temperature"][y][x]),
            "cure_ppm": str(expected["cure"][y][x]),
        }
        for y in range(config["height"])
        for x in range(config["width"])
    ]
    assert read_csv(out_dir / "field.csv") == expected_field
    expected_events = [
        {key: str(value) for key, value in event.items()}
        for event in expected["events"]
    ]
    assert read_csv(out_dir / "events.csv") == expected_events
    summary_text = (out_dir / "summary.json").read_text()
    expected_summary_obj = expected_summary(config, expected)
    expected_summary_text = json.dumps(expected_summary_obj, indent=2) + "\n"
    summary = json.loads(summary_text)
    assert list(summary) == SUMMARY_KEYS
    assert summary == expected_summary_obj
    assert summary_text == expected_summary_text
    trace_rows = read_csv(out_dir / "trace.csv")
    assert trace_rows and list(trace_rows[0]) == TRACE_KEYS
    assert trace_rows == expected_trace_rows(config, expected)
    material_profile_rows = read_csv(out_dir / "material_profile.csv")
    assert material_profile_rows and list(material_profile_rows[0]) == MATERIAL_PROFILE_KEYS
    assert material_profile_rows == expected_material_profile_rows(config, expected)
    stability_rows = read_csv(out_dir / "stability.csv")
    assert stability_rows and list(stability_rows[0]) == STABILITY_KEYS
    assert stability_rows == expected_stability_rows(config, expected)
    return config, expected, summary


def recross_config():
    config = json.loads(BASELINE_FIXTURE.read_text())
    config.update(
        {
            "scenario": "recross-cycle",
            "width": 5,
            "height": 5,
            "steps": 8,
            "block_width": 2,
            "block_height": 2,
            "material_offset": 7,
            "base_temperature_milli_c": -10000,
            "base_cure_ppm": 100000,
            "temperature_floor_milli_c": -50000,
            "temperature_ceiling_milli_c": 120000,
            "activation_temperature_milli_c": 20000,
            "full_cure_ppm": 130000,
            "stress_alert_ppm": 9000,
            "checkpoint_steps": [0, 1, 2, 5, 6, 8],
            "materials": [
                {
                    "retain": 0,
                    "horizontal": 1,
                    "vertical": 1,
                    "diagonal": 0,
                    "heater_gain": 0,
                    "stress_retain_ppm": 350000,
                    "stress_gain": 700,
                    "cure_stress_gain": 95,
                    "stress_relief_ppm": 400,
                    "cure_rate_ppm": 50000,
                    "cool_rate_ppm": 60000,
                },
                {
                    "retain": 1,
                    "horizontal": 2,
                    "vertical": 2,
                    "diagonal": 0,
                    "heater_gain": 0,
                    "stress_retain_ppm": 920000,
                    "stress_gain": 880,
                    "cure_stress_gain": 120,
                    "stress_relief_ppm": 250,
                    "cure_rate_ppm": 50000,
                    "cool_rate_ppm": 60000,
                },
            ],
            "boundaries": {
                side: {"temperature_milli_c": -50000, "cure_ppm": 0}
                for side in ["left", "right", "top", "bottom"]
            },
            "hotspots": [],
            "heater_pulses": [
                {
                    "start_step": step,
                    "end_step": step,
                    "x": 2,
                    "y": 2,
                    "strength_milli_c": 80000,
                    "decay_per_cell_milli_c": 30000,
                }
                for step in [1, 6]
            ],
            "relief_windows": [
                {
                    "start_step": 2,
                    "end_step": 5,
                    "x": 1,
                    "y": 2,
                    "radius": 1,
                    "relief_ppm": 1200,
                    "falloff_ppm_per_cell": 500,
                }
            ],
            "sensor_points": [
                {"name": "center", "x": 2, "y": 2},
                {"name": "top-edge", "x": 3, "y": 0},
            ],
        }
    )
    return config


def wide_range_valid_config():
    config = recross_config()
    config.update(
        {
            "scenario": "wide-contract-ranges",
            "block_width": 125,
            "block_height": 140,
            "base_temperature_milli_c": -250000,
            "hotspots": [
                {
                    "x": 2,
                    "y": 2,
                    "peak_milli_c": 1200000,
                    "decay_per_cell_milli_c": 250000,
                }
            ],
            "heater_pulses": [
                {
                    "start_step": 1,
                    "end_step": 2,
                    "x": 2,
                    "y": 2,
                    "strength_milli_c": 1400000,
                    "decay_per_cell_milli_c": 150000,
                }
            ],
            "relief_windows": [
                {
                    "start_step": 2,
                    "end_step": 5,
                    "x": 1,
                    "y": 2,
                    "radius": 1,
                    "relief_ppm": 1300000,
                    "falloff_ppm_per_cell": 200000,
                }
            ],
        }
    )
    for material in config["materials"]:
        material.update(
            {
                "retain": 1200000,
                "horizontal": 1100000,
                "vertical": 1050000,
                "diagonal": 1000001,
                "heater_gain": 1150000,
                "stress_gain": 1250000,
                "cure_stress_gain": 1350000,
                "stress_relief_ppm": 1450000,
                "cure_rate_ppm": 1100000,
                "cool_rate_ppm": 1050000,
            }
        )
    return config


def starting_above_recross_config():
    config = recross_config()
    config.update(
        {
            "scenario": "starting-above-recross",
            "steps": 3,
            "base_cure_ppm": 150000,
            "checkpoint_steps": [0, 1, 2, 3],
            "heater_pulses": [
                {
                    "start_step": 2,
                    "end_step": 2,
                    "x": 2,
                    "y": 2,
                    "strength_milli_c": 80000,
                    "decay_per_cell_milli_c": 30000,
                }
            ],
            "relief_windows": [],
        }
    )
    return config


def exact_integer_config():
    config = recross_config()
    config.update(
        {
            "scenario": "exact-safe-integer-limits",
            "steps": 2,
            "block_width": JS_MAX_SAFE_INTEGER,
            "block_height": JS_MAX_SAFE_INTEGER - 1,
            "material_offset": JS_MAX_SAFE_INTEGER,
            "base_temperature_milli_c": JS_MAX_SAFE_INTEGER - 100000,
            "temperature_floor_milli_c": JS_MAX_SAFE_INTEGER - 200000,
            "temperature_ceiling_milli_c": JS_MAX_SAFE_INTEGER,
            "activation_temperature_milli_c": JS_MAX_SAFE_INTEGER - 150000,
            "base_cure_ppm": 1000,
            "full_cure_ppm": 900000,
            "stress_alert_ppm": 500000,
            "checkpoint_steps": [0, 1, 2],
            "materials": [
                {
                    "retain": JS_MAX_SAFE_INTEGER,
                    "horizontal": JS_MAX_SAFE_INTEGER - 2,
                    "vertical": JS_MAX_SAFE_INTEGER - 4,
                    "diagonal": JS_MAX_SAFE_INTEGER - 6,
                    "heater_gain": JS_MAX_SAFE_INTEGER - 8,
                    "stress_retain_ppm": 1000000,
                    "stress_gain": JS_MAX_SAFE_INTEGER - 10,
                    "cure_stress_gain": JS_MAX_SAFE_INTEGER - 12,
                    "stress_relief_ppm": 0,
                    "cure_rate_ppm": 250000,
                    "cool_rate_ppm": 250000,
                },
                {
                    "retain": JS_MAX_SAFE_INTEGER - 1,
                    "horizontal": JS_MAX_SAFE_INTEGER - 3,
                    "vertical": JS_MAX_SAFE_INTEGER - 5,
                    "diagonal": JS_MAX_SAFE_INTEGER - 7,
                    "heater_gain": JS_MAX_SAFE_INTEGER - 9,
                    "stress_retain_ppm": 999999,
                    "stress_gain": JS_MAX_SAFE_INTEGER - 11,
                    "cure_stress_gain": JS_MAX_SAFE_INTEGER - 13,
                    "stress_relief_ppm": 1,
                    "cure_rate_ppm": 250001,
                    "cool_rate_ppm": 249999,
                },
            ],
            "boundaries": {
                "left": {
                    "temperature_milli_c": JS_MAX_SAFE_INTEGER - 10,
                    "cure_ppm": 1000,
                },
                "right": {
                    "temperature_milli_c": JS_MAX_SAFE_INTEGER - 20,
                    "cure_ppm": 2000,
                },
                "top": {
                    "temperature_milli_c": JS_MAX_SAFE_INTEGER - 30,
                    "cure_ppm": 3000,
                },
                "bottom": {
                    "temperature_milli_c": JS_MAX_SAFE_INTEGER - 40,
                    "cure_ppm": 4000,
                },
            },
            "hotspots": [
                {
                    "x": 2,
                    "y": 2,
                    "peak_milli_c": JS_MAX_SAFE_INTEGER,
                    "decay_per_cell_milli_c": JS_MAX_SAFE_INTEGER - 1,
                }
            ],
            "heater_pulses": [
                {
                    "start_step": 1,
                    "end_step": 2,
                    "x": 2,
                    "y": 2,
                    "strength_milli_c": JS_MAX_SAFE_INTEGER,
                    "decay_per_cell_milli_c": JS_MAX_SAFE_INTEGER - 2,
                }
            ],
            "relief_windows": [
                {
                    "start_step": 1,
                    "end_step": 2,
                    "x": 2,
                    "y": 2,
                    "radius": JS_MAX_SAFE_INTEGER,
                    "relief_ppm": JS_MAX_SAFE_INTEGER,
                    "falloff_ppm_per_cell": JS_MAX_SAFE_INTEGER - 3,
                }
            ],
            "sensor_points": [
                {"name": "center", "x": 2, "y": 2},
                {"name": "left-edge", "x": 0, "y": 2},
            ],
        }
    )
    return config


def test_baseline_field_and_summary_match_the_contract(tmp_path):
    """The baseline case must match every final cell and summary field."""
    out_dir = tmp_path / "baseline-out"
    out_dir.mkdir()
    (out_dir / "stale.txt").write_text("old")
    assert_case(BASELINE, out_dir, BASELINE_FIXTURE)


def test_thin_panel_covers_rectangular_grid_and_corner_priority(tmp_path):
    """A tall case must preserve row order, material layout, and corner priority."""
    config, expected, _ = assert_case(
        THIN_PANEL, tmp_path / "thin-out", THIN_PANEL_FIXTURE
    )
    rows = read_csv(tmp_path / "thin-out" / "field.csv")
    by_coordinate = {(int(row["x"]), int(row["y"])): row for row in rows}
    assert int(by_coordinate[(0, 0)]["temperature_milli_c"]) == (
        config["boundaries"]["left"]["temperature_milli_c"]
    )
    assert int(
        by_coordinate[(config["width"] - 1, 0)]["temperature_milli_c"]
    ) == config["boundaries"]["right"]["temperature_milli_c"]
    assert expected["temperature"][0][1] == (
        config["boundaries"]["top"]["temperature_milli_c"]
    )


def test_event_log_keeps_only_the_first_threshold_crossing(tmp_path):
    """Cooling and reheating must not duplicate or invent cure events."""
    config = recross_config()
    config_path = tmp_path / "recross.json"
    config_path.write_text(json.dumps(config))
    _, expected, summary = assert_case(config_path, tmp_path / "recross-out")
    coordinates = [(event["x"], event["y"]) for event in expected["events"]]
    assert len(coordinates) == len(set(coordinates))
    assert summary["event_count"] > 0
    above_config = starting_above_recross_config()
    above_path = tmp_path / "starting-above-recross.json"
    above_path.write_text(json.dumps(above_config))
    _, above_expected, above_summary = assert_case(
        above_path, tmp_path / "starting-above-recross-out"
    )
    assert above_expected["events"] == []
    assert above_summary["event_count"] == 0


def test_valid_config_uses_contract_ranges_without_extra_caps(tmp_path):
    """Valid configs may use full safe integers with exact calculations."""
    config = wide_range_valid_config()
    config_path = tmp_path / "wide-ranges.json"
    config_path.write_text(json.dumps(config))
    _, _, summary = assert_case(config_path, tmp_path / "wide-ranges-out")
    assert summary["scenario"] == "wide-contract-ranges"
    exact_config = exact_integer_config()
    exact_path = tmp_path / "exact-safe-integers.json"
    exact_path.write_text(json.dumps(exact_config))
    _, exact_expected, exact_summary = assert_case(
        exact_path, tmp_path / "exact-safe-integers-out"
    )
    assert exact_summary == expected_summary(exact_config, exact_expected)
    assert exact_summary["total_temperature_milli_c"] > JS_MAX_SAFE_INTEGER


def test_checkpoint_values_use_synchronous_temperature_and_next_step_cure(tmp_path):
    """Every configured checkpoint must reflect the specified two-phase update."""
    config, expected, summary = assert_case(
        BASELINE, tmp_path / "checkpoint-out", BASELINE_FIXTURE
    )
    assert list(summary["checkpoint_totals"]) == [
        str(step) for step in config["checkpoint_steps"]
    ]
    assert summary["checkpoint_totals"] == expected["checkpoint_totals"]


def test_trace_reports_checkpoint_sensors_and_gradients(tmp_path):
    """The sensor trace must use checkpoint snapshots, gradients, and deltas."""
    config, _, _ = assert_case(
        THIN_PANEL, tmp_path / "trace-out", THIN_PANEL_FIXTURE
    )
    rows = read_csv(tmp_path / "trace-out" / "trace.csv")
    assert len(rows) == len(config["checkpoint_steps"]) * len(
        config["sensor_points"]
    )
    assert [row["checkpoint"] for row in rows[:3]] == ["0", "0", "0"]
    assert [row["name"] for row in rows[:3]] == [
        sensor["name"] for sensor in config["sensor_points"]
    ]
    assert any(int(row["local_gradient_milli_c"]) > 0 for row in rows)
    assert any(
        int(row["temperature_delta_from_previous_checkpoint_milli_c"]) != 0
        for row in rows
    )


def test_material_profile_summarizes_each_material(tmp_path):
    """The material profile must aggregate final cells and first events."""
    config, expected, _ = assert_case(
        BASELINE, tmp_path / "profile-out", BASELINE_FIXTURE
    )
    rows = read_csv(tmp_path / "profile-out" / "material_profile.csv")
    assert len(rows) == len(config["materials"])
    assert rows == expected_material_profile_rows(config, expected)
    assert sum(int(row["cell_count"]) for row in rows) == (
        config["width"] * config["height"]
    )


def test_invalid_configs_leave_an_existing_output_untouched(tmp_path):
    """Validation failures must preserve all prior output directory contents."""
    original = json.loads(BASELINE_FIXTURE.read_text())
    invalid_payloads = [("malformed-json", "{not json")]

    def add_case(name, mutator):
        config = copy.deepcopy(original)
        mutator(config)
        invalid_payloads.append((name, json.dumps(config)))

    add_case("empty-scenario", lambda config: config.update({"scenario": ""}))
    add_case("width-too-small", lambda config: config.update({"width": 4}))
    add_case("height-too-large", lambda config: config.update({"height": 81}))
    add_case("zero-steps", lambda config: config.update({"steps": 0}))
    add_case("zero-block-width", lambda config: config.update({"block_width": 0}))
    add_case(
        "unsafe-block-width",
        lambda config: config.update({"block_width": JS_MAX_SAFE_INTEGER + 1}),
    )
    add_case(
        "unsafe-base-temperature",
        lambda config: config.update(
            {"base_temperature_milli_c": JS_MIN_SAFE_INTEGER - 1}
        ),
    )
    add_case(
        "bad-temperature-range",
        lambda config: config.update(
            {
                "temperature_floor_milli_c": 5000,
                "temperature_ceiling_milli_c": 5000,
            }
        ),
    )
    add_case(
        "activation-outside-range",
        lambda config: config.update({"activation_temperature_milli_c": 999999}),
    )
    add_case("single-material", lambda config: config.update({"materials": config["materials"][:1]}))
    add_case(
        "zero-stencil-weight",
        lambda config: config["materials"][0].update(
            {"retain": 0, "horizontal": 0, "vertical": 0, "diagonal": 0}
        ),
    )
    add_case(
        "bad-stress-retain",
        lambda config: config["materials"][0].update({"stress_retain_ppm": 1000001}),
    )
    add_case(
        "boundary-temperature-outside-range",
        lambda config: config["boundaries"]["left"].update(
            {"temperature_milli_c": config["temperature_ceiling_milli_c"] + 1}
        ),
    )
    add_case(
        "hotspot-outside-grid",
        lambda config: config["hotspots"][0].update({"x": config["width"]}),
    )
    add_case(
        "negative-hotspot-peak",
        lambda config: config["hotspots"][0].update({"peak_milli_c": -1}),
    )
    add_case(
        "negative-hotspot-decay",
        lambda config: config["hotspots"][0].update({"decay_per_cell_milli_c": -1}),
    )
    add_case(
        "duplicate-checkpoint",
        lambda config: config["checkpoint_steps"].__setitem__(
            2, config["checkpoint_steps"][1]
        ),
    )
    add_case(
        "pulse-start-zero",
        lambda config: config["heater_pulses"][0].update({"start_step": 0}),
    )
    add_case(
        "pulse-end-after-steps",
        lambda config: config["heater_pulses"][0].update(
            {"end_step": config["steps"] + 1}
        ),
    )
    add_case(
        "pulse-outside-grid",
        lambda config: config["heater_pulses"][0].update({"y": config["height"]}),
    )
    add_case(
        "negative-pulse-decay",
        lambda config: config["heater_pulses"][0].update(
            {"decay_per_cell_milli_c": -1}
        ),
    )
    add_case(
        "negative-pulse-strength",
        lambda config: config["heater_pulses"][0].update({"strength_milli_c": -1}),
    )
    add_case(
        "bad-relief-radius",
        lambda config: config["relief_windows"][0].update({"radius": -1}),
    )
    add_case(
        "negative-relief-amount",
        lambda config: config["relief_windows"][0].update({"relief_ppm": -1}),
    )
    add_case(
        "negative-relief-falloff",
        lambda config: config["relief_windows"][0].update(
            {"falloff_ppm_per_cell": -1}
        ),
    )
    add_case("empty-sensors", lambda config: config.update({"sensor_points": []}))
    add_case(
        "duplicate-sensor-name",
        lambda config: config["sensor_points"][1].update(
            {"name": config["sensor_points"][0]["name"]}
        ),
    )
    add_case(
        "invalid-sensor-name",
        lambda config: config["sensor_points"][0].update({"name": "bad name!"}),
    )
    add_case(
        "sensor-outside-grid",
        lambda config: config["sensor_points"][0].update({"x": config["width"]}),
    )
    add_case("bad-stress-alert", lambda config: config.update({"stress_alert_ppm": 0}))

    for index, (name, payload) in enumerate(invalid_payloads):
        config_path = tmp_path / f"invalid-{index}-{name}.json"
        config_path.write_text(payload)
        out_dir = tmp_path / f"preserved-{index}"
        out_dir.mkdir()
        marker = out_dir / "prior.txt"
        marker.write_text("keep this")
        completed = run_cli(config_path, out_dir)
        assert completed.returncode != 0
        assert list(out_dir.iterdir()) == [marker]
        assert marker.read_text() == "keep this"


def test_bad_arguments_fail_without_touching_output_paths(tmp_path):
    """Missing, duplicate, unknown, and relative arguments must preserve outputs."""
    cases = [
        (["--config", str(BASELINE)], []),
        (
            [
                "--config",
                str(BASELINE),
                "--config",
                str(BASELINE),
                "--out",
                str(tmp_path / "a"),
            ],
            [tmp_path / "a"],
        ),
        (
            ["--config", str(BASELINE), "--out", "relative-output"],
            [tmp_path / "relative-output"],
        ),
        (
            [
                "--unknown",
                "value",
                "--config",
                str(BASELINE),
                "--out",
                str(tmp_path / "b"),
            ],
            [tmp_path / "b"],
        ),
        (
            [
                "--config",
                str(BASELINE),
                "--out",
                str(tmp_path / "c"),
                "--out",
                str(tmp_path / "d"),
            ],
            [tmp_path / "c", tmp_path / "d"],
        ),
    ]
    for index, (arguments, protected_dirs) in enumerate(cases):
        markers = []
        for out_dir in protected_dirs:
            out_dir.mkdir()
            marker = out_dir / "prior.txt"
            marker.write_text(f"keep this {index}")
            markers.append((out_dir, marker))
        completed = run_node(
            ["node", str(CLI), *arguments],
            tmp_path,
            timeout=20,
            cwd=tmp_path,
        )
        assert completed.returncode != 0
        for out_dir, marker in markers:
            assert list(out_dir.iterdir()) == [marker]
            assert marker.read_text() == f"keep this {index}"


def test_node_guard_blocks_proc_root_alias_to_tests(tmp_path):
    """The Node guard must deny proc-root aliases for hidden test files."""
    probe = tmp_path / "guard-probe.cjs"
    probe.write_text(
        """
const fs = require('fs');
let blocked = false;
try {
  fs.readFileSync('/proc/self/root/tests/test_outputs.py', 'utf8');
} catch (error) {
  blocked = error.code === 'EACCES';
}
if (!blocked) {
  process.stderr.write('proc root alias was not blocked\\n');
  process.exit(1);
}
""".lstrip()
    )
    completed = run_node(["node", str(probe)], tmp_path, timeout=20, cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr


def test_node_guard_allows_local_child_processes(tmp_path):
    """Submitted Node code may use local helper processes during a correct run."""
    probe = tmp_path / "child-process-probe.cjs"
    probe.write_text(
        """
const { spawnSync } = require('child_process');
const result = spawnSync(process.execPath, ['-e', 'process.stdout.write("helper ok")'], {
  encoding: 'utf8',
});
if (result.status !== 0 || result.stdout !== 'helper ok') {
  process.stderr.write(result.stderr || 'local child process failed\\n');
  process.exit(1);
}
""".lstrip()
    )
    completed = run_node(["node", str(probe)], tmp_path, timeout=20, cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr
