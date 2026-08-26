import hashlib
import json

MOD = 1_000_000_007
PHASE_ORDER = "PIF"


def parse(text):
    rows = [
        line.strip().split()
        for line in text.replace("\r\n", "\n").splitlines()
        if line.strip()
    ]
    data = {}
    index = 0

    assert rows[index] == ["VERSION", "1"]
    index += 1
    data["hmax"] = int(rows[index][1])
    index += 1
    data["scan_lo"], data["scan_hi"] = map(int, rows[index][1:])
    index += 1
    data["amin"], data["amax"], data["drift"] = map(int, rows[index][1:])
    index += 1
    data["zmin"], data["zmax"] = map(int, rows[index][1:])
    index += 1
    data["max_imp"], data["max_missing"], data["min_cons"] = map(
        int, rows[index][1:]
    )
    index += 1
    data["phases"] = rows[index][1:]
    index += 1

    scans = []
    for _ in range(2):
        name = rows[index][1]
        index += 1
        peaks = []
        while rows[index][0] != "END":
            _, peak_id, q_value, tolerance, weight = rows[index]
            peaks.append(
                (peak_id, int(q_value), int(tolerance), int(weight))
            )
            index += 1
        index += 1
        scans.append((name, peaks))

    data["scans"] = scans
    return data


def shells(data, phase):
    representatives = {}
    for h_value in range(data["hmax"] + 1):
        for k_value in range(h_value + 1):
            for l_value in range(k_value + 1):
                if h_value + k_value + l_value == 0:
                    continue
                allowed = (
                    phase == "P"
                    or (
                        phase == "I"
                        and (h_value + k_value + l_value) % 2 == 0
                    )
                    or (
                        phase == "F"
                        and h_value % 2 == k_value % 2 == l_value % 2
                    )
                )
                if not allowed:
                    continue
                shell = h_value * h_value + k_value * k_value + l_value * l_value
                representative = (h_value, k_value, l_value)
                representatives[shell] = min(
                    representatives.get(shell, (99, 99, 99)),
                    representative,
                )
    return [
        (shell, *representatives[shell])
        for shell in sorted(representatives)
    ]


def scan_plans(data, scan_index, phase_shells, scale, shift):
    peaks = data["scans"][scan_index][1]
    plans = []

    def visit(peak_index, last_shell, impurity_count, assignment):
        if peak_index == len(peaks):
            used = {shell for shell in assignment if shell}
            missing = []
            if used:
                low_shell = min(used)
                high_shell = max(used)
                missing = [
                    shell
                    for shell, *_ in phase_shells
                    if low_shell < shell < high_shell
                    and data["scan_lo"]
                    <= scale * shell + shift
                    <= data["scan_hi"]
                    and shell not in used
                ]
            if len(missing) > data["max_missing"]:
                return

            residual = sum(
                abs(peaks[index][1] - (scale * shell + shift))
                for index, shell in enumerate(assignment)
                if shell
            )
            indexed_weight = sum(
                peaks[index][3]
                for index, shell in enumerate(assignment)
                if shell
            )
            plans.append(
                (tuple(assignment), tuple(missing), residual, indexed_weight)
            )
            return

        if impurity_count < data["max_imp"]:
            visit(
                peak_index + 1,
                last_shell,
                impurity_count + 1,
                assignment + [0],
            )

        _, q_value, tolerance, _ = peaks[peak_index]
        for shell, *_ in phase_shells:
            if shell <= last_shell:
                continue
            if abs(q_value - (scale * shell + shift)) <= tolerance:
                visit(
                    peak_index + 1,
                    shell,
                    impurity_count,
                    assignment + [shell],
                )

    visit(0, 0, 0, [])
    return plans


def solve(data):
    best_objective = None
    best_key = None
    best_plan = None
    optimal_count = 0

    for phase in data["phases"]:
        phase_shells = shells(data, phase)
        for scale_zero in range(data["amin"], data["amax"] + 1):
            for scale_one in range(data["amin"], data["amax"] + 1):
                if abs(scale_one - scale_zero) > data["drift"]:
                    continue
                for shift_zero in range(data["zmin"], data["zmax"] + 1):
                    scan_zero_plans = scan_plans(
                        data,
                        0,
                        phase_shells,
                        scale_zero,
                        shift_zero,
                    )
                    for shift_one in range(data["zmin"], data["zmax"] + 1):
                        scan_one_plans = scan_plans(
                            data,
                            1,
                            phase_shells,
                            scale_one,
                            shift_one,
                        )
                        for scan_zero in scan_zero_plans:
                            for scan_one in scan_one_plans:
                                shells_zero = {
                                    shell for shell in scan_zero[0] if shell
                                }
                                shells_one = {
                                    shell for shell in scan_one[0] if shell
                                }
                                consensus = len(shells_zero & shells_one)
                                if consensus < data["min_cons"]:
                                    continue

                                objective = (
                                    -scan_zero[3] - scan_one[3],
                                    -consensus,
                                    scan_zero[2] + scan_one[2],
                                    len(scan_zero[1]) + len(scan_one[1]),
                                    len(shells_zero ^ shells_one),
                                    abs(scale_one - scale_zero)
                                    + abs(shift_one - shift_zero),
                                )
                                canonical_key = (
                                    PHASE_ORDER.index(phase),
                                    scale_zero,
                                    shift_zero,
                                    scale_one,
                                    shift_one,
                                    scan_zero[0],
                                    scan_one[0],
                                )
                                candidate = (
                                    phase,
                                    (scale_zero, scale_one),
                                    (shift_zero, shift_one),
                                    scan_zero,
                                    scan_one,
                                    phase_shells,
                                )

                                if (
                                    best_objective is None
                                    or objective < best_objective
                                ):
                                    best_objective = objective
                                    best_key = canonical_key
                                    best_plan = candidate
                                    optimal_count = 1
                                elif objective == best_objective:
                                    optimal_count = (optimal_count + 1) % MOD
                                    if canonical_key < best_key:
                                        best_key = canonical_key
                                        best_plan = candidate

    return best_objective, best_plan, optimal_count


def render(data):
    _, best_plan, optimal_count = solve(data)
    if best_plan is None:
        body = {"status": "infeasible", "optimal_count": 0}
    else:
        phase, scales, shifts, scan_zero, scan_one, phase_shells = best_plan
        representatives = {
            shell: (h_value, k_value, l_value)
            for shell, h_value, k_value, l_value in phase_shells
        }
        scans = []

        for scan_index, scan_plan in enumerate((scan_zero, scan_one)):
            name, peaks = data["scans"][scan_index]
            assignments = []
            impurities = []
            for peak_index, shell in enumerate(scan_plan[0]):
                peak_id, q_value, _, _ = peaks[peak_index]
                if not shell:
                    impurities.append(peak_id)
                    continue
                predicted = scales[scan_index] * shell + shifts[scan_index]
                assignments.append(
                    {
                        "peak": peak_id,
                        "shell": shell,
                        "hkl": list(representatives[shell]),
                        "predicted": predicted,
                        "residual": abs(q_value - predicted),
                    }
                )
            scans.append(
                {
                    "name": name,
                    "assignments": assignments,
                    "impurities": impurities,
                    "missing_shells": list(scan_plan[1]),
                }
            )

        shells_zero = {shell for shell in scan_zero[0] if shell}
        shells_one = {shell for shell in scan_one[0] if shell}
        body = {
            "status": "ok",
            "phase": phase,
            "calibration": [
                {
                    "scan": data["scans"][0][0],
                    "scale": scales[0],
                    "shift": shifts[0],
                },
                {
                    "scan": data["scans"][1][0],
                    "scale": scales[1],
                    "shift": shifts[1],
                },
            ],
            "objective": {
                "indexed_weight": scan_zero[3] + scan_one[3],
                "consensus": len(shells_zero & shells_one),
                "residual": scan_zero[2] + scan_one[2],
                "missing": len(scan_zero[1]) + len(scan_one[1]),
                "orphans": len(shells_zero ^ shells_one),
                "motion": abs(scales[1] - scales[0])
                + abs(shifts[1] - shifts[0]),
            },
            "optimal_count": optimal_count,
            "scans": scans,
        }

    preimage = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    body["digest"] = hashlib.sha256(preimage.encode()).hexdigest()
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False) + "\n"
