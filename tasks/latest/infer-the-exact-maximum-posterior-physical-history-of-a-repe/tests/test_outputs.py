import copy
import hashlib
import itertools
import json
import os
import subprocess
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

import pytest


WORKSPACE = Path(os.environ.get("TASK_WORKSPACE", "/workspace"))
INFERENCE_INSTRUMENT = Path(
    os.environ.get("TASK_COMMAND", str(WORKSPACE / "infer_stabilizer_burst_cosets"))
)
PUBLIC_INPUT = Path(
    os.environ.get(
        "TASK_PUBLIC_INPUT",
        str(WORKSPACE / "task_file" / "stabilizer-burst-observations.json"),
    )
)
PUBLIC_OUTPUT = Path(
    os.environ.get(
        "TASK_PUBLIC_OUTPUT",
        str(WORKSPACE / "stabilizer-burst-coset-spectrum.json"),
    )
)
PUBLIC_INPUT_SHA256 = "0147071c3c8ab354e8c3793f2dc9a0de886011a17043ebd846fbcadd3b6ba2b9"

SUCCESS_KEYS = {
    "status",
    "readout_frame",
    "selected_bursts",
    "shots",
    "family_occupancy",
    "likelihood_manifold",
    "representative_key",
}
FRAME_KEYS = {"id", "prior_weight", "detector_bias"}
SHOT_KEYS = {
    "id",
    "round",
    "measured_events",
    "burst_events",
    "inherited_events",
    "active_mechanisms",
    "reproduced_events",
    "burst_logical_coset",
    "logical_coset",
    "burst_load",
    "neg_log_weight",
    "mechanisms_by_cycle",
}
CYCLE_KEYS = {"cycle", "mechanism_ids"}
BURST_KEYS = {
    "id",
    "family_id",
    "prior_weight",
    "exclusive_group",
    "start_round",
    "end_round",
    "intensity",
    "exposure",
    "blocked_coupler_ids",
}
FAMILY_KEYS = {
    "family_id",
    "pauli_occurrences",
    "burst_occurrences",
    "active_occurrences",
    "occurrence_limit",
    "remaining_occurrences",
}
MANIFOLD_KEYS = {
    "total_neg_log_weight",
    "burst_exposure",
    "peak_shot_weight",
    "burst_count",
    "mechanism_count",
    "multiplicity",
    "frame_support",
    "burst_support",
    "joint_logical_support",
}


def load_public():
    return json.loads(PUBLIC_INPUT.read_text(encoding="utf-8"))


def rational_text(value):
    value = Fraction(value)
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def xor_values(target, values):
    for value in values:
        if value in target:
            target.remove(value)
        else:
            target.add(value)


def expected_spectrum(payload):
    mechanisms = {row["id"]: row for row in payload["pauli_mechanisms"]}
    families = sorted(payload["noise_families"], key=lambda row: row["id"])
    shots = sorted(payload["shots"], key=lambda row: (row["round"], row["id"]))
    bursts = sorted(payload.get("burst_sources", []), key=lambda row: row["id"])

    def burst_choices(frame):
        forbidden = set(frame.get("forbidden_bursts", []))
        available = [row for row in bursts if row["id"] not in forbidden]
        choices = []
        for active_bits in itertools.product((False, True), repeat=len(available)):
            selected = [row for row, enabled in zip(available, active_bits) if enabled]
            groups = [row["exclusive_group"] for row in selected if row["exclusive_group"] is not None]
            if len(groups) != len(set(groups)):
                continue
            exposure = sum(row["intensity"] * row["duration_rounds"] for row in selected)
            if exposure > payload.get("burst_exposure_limit", 0):
                continue
            family_uses = Counter(row["family_id"] for row in selected)
            if any(
                family_uses[family["id"]] > family["occurrence_limit"]
                for family in families
            ):
                continue
            event_rows = []
            logical_rows = []
            burst_loads = []
            blocked_rows = []
            physical = True
            for shot_row in shots:
                events = set()
                logicals = set()
                blocked = set()
                load = 0
                for burst in selected:
                    offset = shot_row["round"] - burst["start_round"]
                    if not 0 <= offset < burst["duration_rounds"]:
                        continue
                    load += burst["intensity"]
                    blocked.update(burst["blocked_coupler_ids"])
                    xor_values(
                        events,
                        burst["detection_events_by_offset"].get(str(offset), []),
                    )
                    xor_values(
                        logicals,
                        burst["logical_operators_by_offset"].get(str(offset), []),
                    )
                if load > shot_row.get("burst_cap", 0):
                    physical = False
                    break
                event_rows.append(events)
                logical_rows.append(logicals)
                burst_loads.append(load)
                blocked_rows.append(blocked)
            if physical:
                choices.append(
                    {
                        "selected": selected,
                        "exposure": exposure,
                        "weight": sum(
                            (Fraction(row["prior_weight"]) for row in selected),
                            Fraction(),
                        ),
                        "family_uses": family_uses,
                        "event_rows": event_rows,
                        "logical_rows": logical_rows,
                        "burst_loads": burst_loads,
                        "blocked_rows": blocked_rows,
                    }
                )
        return choices

    def options_for(frame, shot_row, blocked_couplers):
        forbidden = set(frame["forbidden_mechanisms"])
        available = sorted(
            (
                mechanisms[mechanism_id]
                for mechanism_id in shot_row["candidate_mechanisms"]
                if mechanism_id not in forbidden
                and mechanisms[mechanism_id]["coupler_id"] not in blocked_couplers
            ),
            key=lambda row: row["id"],
        )
        options = []
        for active_bits in itertools.product((False, True), repeat=len(available)):
            active = [row for row, enabled in zip(available, active_bits) if enabled]
            couplers = [(row["cycle"], row["coupler_id"]) for row in active]
            if len(couplers) != len(set(couplers)):
                continue
            cycle_counts = Counter(row["cycle"] for row in active)
            if any(
                count > shot_row["cycle_caps"][str(cycle_id)]
                for cycle_id, count in cycle_counts.items()
            ):
                continue
            detector_parity = set(frame["detector_bias"])
            logical_parity = set()
            for row in active:
                xor_values(detector_parity, row["detection_events"])
                xor_values(logical_parity, row["logical_operators"])
            by_cycle = defaultdict(list)
            for row in active:
                by_cycle[row["cycle"]].append(row["id"])
            options.append(
                {
                    "mechanism_ids": [row["id"] for row in active],
                    "local_events": detector_parity,
                    "weight": sum(
                        (Fraction(row["neg_log_weight"]) for row in active),
                        Fraction(),
                    ),
                    "logical_ids": set(logical_parity),
                    "family_uses": Counter(row["family_id"] for row in active),
                    "by_cycle": {
                        cycle_id: sorted(ids) for cycle_id, ids in by_cycle.items()
                    },
                }
            )
        return options

    candidates = []
    family_caps = {row["id"]: row["occurrence_limit"] for row in families}
    for frame in payload["readout_frames"]:
        for burst_choice in burst_choices(frame):
            per_shot = [
                options_for(frame, shot_row, burst_choice["blocked_rows"][index])
                for index, shot_row in enumerate(shots)
            ]
            for active_options in itertools.product(*per_shot):
                pauli_uses = sum(
                    (option["family_uses"] for option in active_options), Counter()
                )
                family_uses = pauli_uses + burst_choice["family_uses"]
                if any(
                    family_uses[family_id] > cap
                    for family_id, cap in family_caps.items()
                ):
                    continue
                inherited_rows = []
                physical = True
                logical_rows = []
                for index, (shot_row, option) in enumerate(zip(shots, active_options)):
                    inherited = set()
                    for earlier_index in range(index):
                        delta = shot_row["round"] - shots[earlier_index]["round"]
                        for mechanism_id in active_options[earlier_index]["mechanism_ids"]:
                            xor_values(
                                inherited,
                                mechanisms[mechanism_id]
                                .get("delayed_detection_events", {})
                                .get(str(delta), []),
                            )
                    reproduced = set(option["local_events"])
                    xor_values(reproduced, inherited)
                    xor_values(reproduced, burst_choice["event_rows"][index])
                    if reproduced != set(shot_row["measured_events"]):
                        physical = False
                        break
                    for mechanism_id in option["mechanism_ids"]:
                        current = mechanisms[mechanism_id]
                        for earlier_index in range(index):
                            delta = shot_row["round"] - shots[earlier_index]["round"]
                            for earlier_id in active_options[earlier_index]["mechanism_ids"]:
                                earlier = mechanisms[earlier_id]
                                if (
                                    earlier["cycle"] == current["cycle"]
                                    and earlier["coupler_id"] == current["coupler_id"]
                                    and delta <= earlier.get("recovery_rounds", 0)
                                ):
                                    physical = False
                                    break
                            if not physical:
                                break
                        if not physical:
                            break
                    if not physical:
                        break
                    total_logical = set(option["logical_ids"])
                    xor_values(total_logical, burst_choice["logical_rows"][index])
                    logical_rows.append(total_logical)
                    inherited_rows.append(sorted(inherited))
                if not physical:
                    continue
                for family in families:
                    for end_index, end_shot in enumerate(shots):
                        window_uses = sum(
                            active_options[prior_index]["family_uses"][family["id"]]
                            for prior_index in range(end_index + 1)
                            if end_shot["round"] - shots[prior_index]["round"]
                            < family["window_rounds"]
                        )
                        window_uses += sum(
                            1
                            for burst in burst_choice["selected"]
                            if burst["family_id"] == family["id"]
                            and 0 <= end_shot["round"] - burst["start_round"]
                            < family["window_rounds"]
                        )
                        if window_uses > family["window_limit"]:
                            physical = False
                            break
                    if not physical:
                        break
                if not physical:
                    continue
                shot_weights = [option["weight"] for option in active_options]
                objective = (
                    Fraction(frame["prior_weight"])
                    + burst_choice["weight"]
                    + sum(shot_weights, Fraction()),
                    burst_choice["exposure"],
                    max(shot_weights, default=Fraction()),
                    len(burst_choice["selected"]),
                    sum(len(option["mechanism_ids"]) for option in active_options),
                )
                burst_ids = [row["id"] for row in burst_choice["selected"]]
                representative_key = "|".join(
                    [frame["id"], f'bursts={",".join(burst_ids)}']
                    + [
                        f'{shot_row["id"]}={",".join(option["mechanism_ids"])}'
                        for shot_row, option in zip(shots, active_options)
                    ]
                )
                logical_key = "/".join(
                    f'{shot_row["id"]}:'
                    + "".join(
                        "1" if logical_id in logical_rows[index] else "0"
                        for logical_id in payload["logical_observables"]
                    )
                    for index, shot_row in enumerate(shots)
                )
                candidates.append(
                    {
                        "frame": frame,
                        "bursts": burst_choice,
                        "options": active_options,
                        "objective": objective,
                        "representative_key": representative_key,
                        "logical_key": logical_key,
                        "logical_rows": logical_rows,
                        "pauli_uses": pauli_uses,
                        "family_uses": family_uses,
                        "inherited_rows": inherited_rows,
                    }
                )

    if not candidates:
        return {
            "status": "no_physical_coset",
            "frames_examined": len(payload["readout_frames"]),
            "shots_examined": len(payload["shots"]),
        }

    best_objective = min(candidate["objective"] for candidate in candidates)
    stratum = [candidate for candidate in candidates if candidate["objective"] == best_objective]
    chosen = min(stratum, key=lambda candidate: candidate["representative_key"])
    frame_counts = Counter(candidate["frame"]["id"] for candidate in stratum)
    burst_counts = Counter(
        burst["id"]
        for candidate in stratum
        for burst in candidate["bursts"]["selected"]
    )
    logical_counts = Counter(candidate["logical_key"] for candidate in stratum)

    shot_spectrums = []
    for index, (shot_row, option) in enumerate(zip(shots, chosen["options"])):
        shot_spectrums.append(
            {
                "id": shot_row["id"],
                "round": shot_row["round"],
                "measured_events": sorted(shot_row["measured_events"]),
                "burst_events": sorted(chosen["bursts"]["event_rows"][index]),
                "inherited_events": chosen["inherited_rows"][index],
                "active_mechanisms": option["mechanism_ids"],
                "reproduced_events": sorted(shot_row["measured_events"]),
                "burst_logical_coset": [
                    logical_id
                    for logical_id in payload["logical_observables"]
                    if logical_id in chosen["bursts"]["logical_rows"][index]
                ],
                "logical_coset": [
                    logical_id
                    for logical_id in payload["logical_observables"]
                    if logical_id in chosen["logical_rows"][index]
                ],
                "burst_load": chosen["bursts"]["burst_loads"][index],
                "neg_log_weight": rational_text(option["weight"]),
                "mechanisms_by_cycle": [
                    {"cycle": cycle_id, "mechanism_ids": option["by_cycle"][cycle_id]}
                    for cycle_id in sorted(option["by_cycle"])
                ],
            }
        )

    return {
        "status": "resolved",
        "readout_frame": {
            "id": chosen["frame"]["id"],
            "prior_weight": rational_text(Fraction(chosen["frame"]["prior_weight"])),
            "detector_bias": sorted(chosen["frame"]["detector_bias"]),
        },
        "selected_bursts": [
            {
                "id": burst["id"],
                "family_id": burst["family_id"],
                "prior_weight": rational_text(Fraction(burst["prior_weight"])),
                "exclusive_group": burst["exclusive_group"],
                "start_round": burst["start_round"],
                "end_round": burst["start_round"] + burst["duration_rounds"] - 1,
                "intensity": burst["intensity"],
                "exposure": burst["intensity"] * burst["duration_rounds"],
                "blocked_coupler_ids": sorted(burst["blocked_coupler_ids"]),
            }
            for burst in chosen["bursts"]["selected"]
        ],
        "shots": shot_spectrums,
        "family_occupancy": [
            {
                "family_id": family["id"],
                "pauli_occurrences": chosen["pauli_uses"][family["id"]],
                "burst_occurrences": chosen["bursts"]["family_uses"][family["id"]],
                "active_occurrences": chosen["family_uses"][family["id"]],
                "occurrence_limit": family["occurrence_limit"],
                "remaining_occurrences": family["occurrence_limit"]
                - chosen["family_uses"][family["id"]],
            }
            for family in families
        ],
        "likelihood_manifold": {
            "total_neg_log_weight": rational_text(best_objective[0]),
            "burst_exposure": best_objective[1],
            "peak_shot_weight": rational_text(best_objective[2]),
            "burst_count": best_objective[3],
            "mechanism_count": best_objective[4],
            "multiplicity": len(stratum),
            "frame_support": [
                {"frame_id": frame_row["id"], "count": frame_counts[frame_row["id"]]}
                for frame_row in sorted(payload["readout_frames"], key=lambda row: row["id"])
            ],
            "burst_support": [
                {"burst_id": burst["id"], "count": burst_counts[burst["id"]]}
                for burst in bursts
            ],
            "joint_logical_support": [
                {"class_key": class_key, "count": logical_counts[class_key]}
                for class_key in sorted(logical_counts)
            ],
        },
        "representative_key": chosen["representative_key"],
    }


def mechanism(
    mechanism_id,
    events,
    weight,
    *,
    family="pauli",
    cycle_id=0,
    coupler=None,
    logicals=None,
    delayed=None,
    recovery=0,
):
    return {
        "id": mechanism_id,
        "family_id": family,
        "cycle": cycle_id,
        "coupler_id": coupler or mechanism_id,
        "neg_log_weight": weight,
        "detection_events": events,
        "logical_operators": logicals or [],
        "delayed_detection_events": delayed or {},
        "recovery_rounds": recovery,
    }


def frame(frame_id="m", *, prior="0", offset=None, forbidden=None, forbidden_bursts=None):
    return {
        "id": frame_id,
        "prior_weight": prior,
        "detector_bias": offset or [],
        "forbidden_mechanisms": forbidden or [],
        "forbidden_bursts": forbidden_bursts or [],
    }


def burst(
    burst_id,
    events_by_offset,
    weight,
    *,
    family="burst",
    start=0,
    duration=1,
    intensity=1,
    group=None,
    blocked=None,
    logicals_by_offset=None,
):
    return {
        "id": burst_id,
        "family_id": family,
        "prior_weight": weight,
        "exclusive_group": group,
        "start_round": start,
        "duration_rounds": duration,
        "intensity": intensity,
        "blocked_coupler_ids": blocked or [],
        "detection_events_by_offset": {
            str(offset): events for offset, events in events_by_offset.items()
        },
        "logical_operators_by_offset": {
            str(offset): logicals
            for offset, logicals in (logicals_by_offset or {}).items()
        },
    }


def shot(
    shot_id,
    observed,
    candidate,
    mechanism_rows,
    *,
    caps=None,
    round_id=None,
    burst_cap=0,
):
    if caps is None:
        cycles = {row["cycle"] for row in mechanism_rows if row["id"] in candidate}
        caps = {str(cycle_id): len(candidate) for cycle_id in cycles}
    return {
        "id": shot_id,
        "round": round_id,
        "measured_events": observed,
        "candidate_mechanisms": candidate,
        "cycle_caps": caps,
        "burst_cap": burst_cap,
    }


def experiment(
    mechanism_rows,
    shots,
    *,
    frames=None,
    families=None,
    stabilizers=None,
    logicals=None,
    bursts=None,
    exposure_limit=0,
):
    bursts = bursts or []
    if stabilizers is None:
        burst_events = {
            event
            for burst_row in bursts
            for events in burst_row["detection_events_by_offset"].values()
            for event in events
        }
        stabilizers = sorted(
            {event for row in mechanism_rows for event in row["detection_events"]}
            | burst_events
            | {"S0"}
        )
    if logicals is None:
        logicals = ["LX"]
    if families is None:
        family_ids = sorted(
            {row["family_id"] for row in mechanism_rows}
            | {row["family_id"] for row in bursts}
        )
        families = [{"id": family_id, "occurrence_limit": 20} for family_id in family_ids]
    families = copy.deepcopy(families)
    for family in families:
        family.setdefault("window_rounds", 32)
        family.setdefault("window_limit", family["occurrence_limit"])
    shots = copy.deepcopy(shots)
    next_round = 0
    for shot_row in sorted(shots, key=lambda row: row["id"]):
        if shot_row["round"] is None:
            shot_row["round"] = next_round
        next_round = max(next_round + 1, shot_row["round"] + 1)
    return {
        "schema": "stabilizer-burst-coset-inference/v2",
        "stabilizers": stabilizers,
        "logical_observables": logicals,
        "readout_frames": frames or [frame()],
        "noise_families": families,
        "pauli_mechanisms": mechanism_rows,
        "burst_exposure_limit": exposure_limit,
        "burst_sources": bursts,
        "shots": shots,
    }


def reordered_unknown_case():
    data = load_public()
    for key in (
        "stabilizers",
        "readout_frames",
        "noise_families",
        "pauli_mechanisms",
        "burst_sources",
        "shots",
    ):
        data[key] = list(reversed(data[key]))
    for row in data["shots"]:
        row["candidate_mechanisms"] = list(reversed(row["candidate_mechanisms"]))
        row["lab_note"] = "ignored"
    for row in data["burst_sources"]:
        row["blocked_coupler_ids"] = list(reversed(row["blocked_coupler_ids"]))
        row["cryostat_note"] = "ignored"
    data["operator_note"] = "ignored"
    return data


def forbidden_mechanism_case():
    rows = [mechanism("cheap", ["d0"], "0"), mechanism("fallback", ["d0"], "2")]
    shots = [shot("w", ["d0"], ["cheap", "fallback"], rows)]
    return experiment(rows, shots, frames=[frame(forbidden=["cheap"])])


def family_coupling_case(cap=1):
    rows = [
        mechanism("burst-a", ["d0"], "0", family="burst"),
        mechanism("local-a", ["d0"], "2", family="local"),
    ]
    shots = [
        shot("w-a", ["d0"], ["burst-a", "local-a"], rows),
        shot("w-b", ["d0"], ["burst-a", "local-a"], rows),
    ]
    families = [{"id": "burst", "occurrence_limit": cap}, {"id": "local", "occurrence_limit": 2}]
    return experiment(rows, shots, families=families)


def coupler_collision_case():
    rows = [
        mechanism("left", ["d0"], "0", coupler="q", cycle_id=0),
        mechanism("right", ["d1"], "0", coupler="q", cycle_id=0),
        mechanism("joint", ["d0", "d1"], "3", coupler="joint", cycle_id=0),
    ]
    shots = [shot("w", ["d0", "d1"], [row["id"] for row in rows], rows, caps={"0": 2})]
    return experiment(rows, shots, stabilizers=["d0", "d1"])


def cycle_cap_case(cap=1):
    rows = [
        mechanism("left", ["d0"], "0", coupler="q0"),
        mechanism("right", ["d1"], "0", coupler="q1"),
        mechanism("joint", ["d0", "d1"], "3", coupler="q2"),
    ]
    shots = [shot("w", ["d0", "d1"], [row["id"] for row in rows], rows, caps={"0": cap})]
    return experiment(rows, shots, stabilizers=["d0", "d1"])


def parity_cancellation_case():
    rows = [mechanism("a", ["d0"], "1/3"), mechanism("b", ["d0", "d1"], "1/3"), mechanism("direct", ["d1"], "1")]
    shots = [shot("w", ["d1"], [row["id"] for row in rows], rows)]
    return experiment(rows, shots, stabilizers=["d0", "d1"])


def logical_cancellation_case():
    rows = [
        mechanism("a", ["d0"], "0", logicals=["LX"]),
        mechanism("b", ["d1"], "0", logicals=["LX"]),
    ]
    shots = [shot("w", ["d0", "d1"], ["a", "b"], rows)]
    return experiment(rows, shots, stabilizers=["d0", "d1"])


def exact_fraction_case():
    rows = [
        mechanism("third", ["d0"], "1/3"),
        mechanism("sixth-a", ["d0", "d1"], "1/6"),
        mechanism("sixth-b", ["d1"], "1/6"),
    ]
    shots = [shot("w", ["d0"], [row["id"] for row in rows], rows)]
    return experiment(rows, shots, stabilizers=["d0", "d1"])


def worst_shot_case():
    rows = [
        mechanism("spread-a", ["d0"], "1"),
        mechanism("spread-b", ["d1"], "1"),
        mechanism("lopsided-b", ["d0", "d1"], "2"),
    ]
    shots = [
        shot("w-a", ["d0"], ["spread-a"], rows),
        shot("w-b", ["d1"], ["spread-b", "lopsided-b"], rows),
    ]
    frames = [frame("lopsided", offset=["d0"]), frame("spread")]
    return experiment(rows, shots, frames=frames, stabilizers=["d0", "d1"])


def mechanism_count_case():
    rows = [
        mechanism("one", ["d0"], "1"),
        mechanism("two-a", ["d0", "d1"], "1/2"),
        mechanism("two-b", ["d1"], "1/2"),
    ]
    shots = [shot("w", ["d0"], [row["id"] for row in rows], rows)]
    return experiment(rows, shots, stabilizers=["d0", "d1"])


def frame_tie_case():
    rows = [mechanism("f", ["d0"], "1")]
    shots = [shot("w", ["d0"], ["f"], rows)]
    return experiment(rows, shots, frames=[frame("z-frame"), frame("a-frame")])


def microstate_tie_case(logical_ambiguity=False):
    rows = [
        mechanism("z-mechanism", ["d0"], "1", logicals=["LX"] if logical_ambiguity else []),
        mechanism("a-mechanism", ["d0"], "1"),
    ]
    shots = [shot("w", ["d0"], ["z-mechanism", "a-mechanism"], rows)]
    return experiment(rows, shots)


def silent_mechanism_case():
    rows = [mechanism("needed", ["d0"], "1"), mechanism("silent", [], "0", logicals=["LX"])]
    shots = [shot("w", ["d0"], ["needed", "silent"], rows)]
    return experiment(rows, shots)


def repeated_occurrence_case(cap=2):
    rows = [mechanism("repeatable", ["d0"], "1", family="pulse")]
    shots = [shot("w-a", ["d0"], ["repeatable"], rows), shot("w-b", ["d0"], ["repeatable"], rows)]
    return experiment(rows, shots, families=[{"id": "pulse", "occurrence_limit": cap}])


def empty_syndrome_case():
    rows = [mechanism("unneeded", ["d0"], "0")]
    shots = [shot("w", [], ["unneeded"], rows)]
    return experiment(rows, shots)


def logical_order_case():
    rows = [mechanism("logical", ["d0"], "1", logicals=["LX"])]
    shots = [shot("w", ["d0"], ["logical"], rows)]
    return experiment(rows, shots, logicals=["LZ", "LX"])


def prior_cost_case():
    rows = [mechanism("raw-mechanism", ["d0"], "1")]
    shots = [shot("w", ["d0"], ["raw-mechanism"], rows)]
    frames = [frame("raw", prior="1"), frame("offset", prior="3/4", offset=["d0"])]
    return experiment(rows, shots, frames=frames)


def shot_order_case():
    data = family_coupling_case(1)
    data["shots"] = list(reversed(data["shots"]))
    return data


def delayed_tail_case():
    rows = [
        mechanism("emitter", ["d0"], "1", delayed={"1": ["d1"]}),
        mechanism("late-local", ["d1"], "4"),
    ]
    shots = [
        shot("early", ["d0"], ["emitter"], rows, round_id=4),
        shot("late", ["d1"], ["late-local"], rows, round_id=5),
    ]
    return experiment(rows, shots, stabilizers=["d0", "d1"])


def delayed_parity_case():
    rows = [
        mechanism("emitter", ["d0"], "1", delayed={"1": ["d1"]}),
        mechanism("cancel", ["d1"], "0"),
    ]
    shots = [
        shot("early", ["d0"], ["emitter"], rows, round_id=2),
        shot("late", [], ["cancel"], rows, round_id=3),
    ]
    return experiment(rows, shots, stabilizers=["d0", "d1"])


def recovery_case(gap):
    rows = [
        mechanism("pulse", ["d0"], "0", coupler="q", recovery=1),
        mechanism("fallback", ["d0"], "3", coupler="other"),
    ]
    shots = [
        shot("early", ["d0"], ["pulse"], rows, round_id=0),
        shot("late", ["d0"], ["pulse", "fallback"], rows, round_id=gap),
    ]
    return experiment(rows, shots)


def sliding_window_case(gap=1):
    rows = [
        mechanism("burst", ["d0"], "0", family="burst"),
        mechanism("local", ["d0"], "2", family="local"),
    ]
    shots = [
        shot("a", ["d0"], ["burst", "local"], rows, round_id=0),
        shot("b", ["d0"], ["burst", "local"], rows, round_id=gap),
        shot("c", ["d0"], ["burst", "local"], rows, round_id=gap + 1),
    ]
    families = [
        {"id": "burst", "occurrence_limit": 3, "window_rounds": 2, "window_limit": 1},
        {"id": "local", "occurrence_limit": 3, "window_rounds": 32, "window_limit": 3},
    ]
    return experiment(rows, shots, families=families)


def temporal_interaction_case():
    rows = [
        mechanism(
            "burst-source",
            ["d0"],
            "0",
            family="burst",
            coupler="q",
            delayed={"1": ["d1"]},
            recovery=1,
        ),
        mechanism("reuse-recovery", ["d1"], "0", family="local", coupler="q"),
        mechanism("burst-window", ["d1"], "0", family="burst", coupler="other"),
        mechanism("local-late", ["d1"], "2", family="local", coupler="safe", logicals=["LX"]),
    ]
    shots = [
        shot("early", ["d0"], ["burst-source"], rows, round_id=7),
        shot(
            "late",
            [],
            ["reuse-recovery", "burst-window", "local-late"],
            rows,
            round_id=8,
        ),
    ]
    families = [
        {"id": "burst", "occurrence_limit": 2, "window_rounds": 2, "window_limit": 1},
        {"id": "local", "occurrence_limit": 2, "window_rounds": 2, "window_limit": 2},
    ]
    return experiment(rows, shots, families=families, stabilizers=["d0", "d1"])


def burst_spans_unobserved_round_case():
    rows = [
        mechanism("local-early", ["d0"], "1", family="local"),
        mechanism("local-late", ["d1"], "1", family="local"),
    ]
    bursts = [burst("thermal", {0: ["d0"], 2: ["d1"]}, "1", duration=3)]
    shots = [
        shot("early", ["d0"], ["local-early"], rows, round_id=0, burst_cap=1),
        shot("late", ["d1"], ["local-late"], rows, round_id=2, burst_cap=1),
    ]
    return experiment(rows, shots, bursts=bursts, exposure_limit=3)


def burst_detector_parity_case():
    rows = [mechanism("fallback", ["d1", "d2"], "4", family="local")]
    bursts = [
        burst("left", {0: ["d0", "d1"]}, "0"),
        burst("right", {0: ["d0", "d2"]}, "0"),
    ]
    shots = [shot("w", ["d1", "d2"], ["fallback"], rows, burst_cap=2)]
    return experiment(rows, shots, bursts=bursts, exposure_limit=2)


def burst_logical_parity_case():
    rows = [mechanism("fallback", ["d0", "d1"], "5", family="local")]
    bursts = [
        burst("left", {0: ["d0"]}, "0", logicals_by_offset={0: ["LX"]}),
        burst("right", {0: ["d1"]}, "0", logicals_by_offset={0: ["LX"]}),
    ]
    shots = [shot("w", ["d0", "d1"], ["fallback"], rows, burst_cap=2)]
    return experiment(rows, shots, bursts=bursts, exposure_limit=2)


def burst_exposure_case(limit):
    rows = [
        mechanism("local-a", ["d0"], "3", family="local"),
        mechanism("local-b", ["d1"], "3", family="local"),
    ]
    bursts = [burst("long", {0: ["d0"], 1: ["d1"]}, "0", duration=2)]
    shots = [
        shot("a", ["d0"], ["local-a"], rows, round_id=0, burst_cap=1),
        shot("b", ["d1"], ["local-b"], rows, round_id=1, burst_cap=1),
    ]
    return experiment(rows, shots, bursts=bursts, exposure_limit=limit)


def burst_exclusive_group_case():
    rows = [mechanism("joint", ["d0", "d1"], "3", family="local")]
    bursts = [
        burst("source-a", {0: ["d0"]}, "0", group="line"),
        burst("source-b", {0: ["d1"]}, "0", group="line"),
    ]
    shots = [shot("w", ["d0", "d1"], ["joint"], rows, burst_cap=2)]
    return experiment(rows, shots, bursts=bursts, exposure_limit=2)


def burst_load_cap_case():
    rows = [mechanism("joint", ["d0", "d1"], "3", family="local")]
    bursts = [
        burst("source-a", {0: ["d0"]}, "0"),
        burst("source-b", {0: ["d1"]}, "0"),
    ]
    shots = [shot("w", ["d0", "d1"], ["joint"], rows, burst_cap=1)]
    return experiment(rows, shots, bursts=bursts, exposure_limit=2)


def burst_blocks_coupler_case():
    rows = [
        mechanism("blocked-local", ["d1"], "0", family="local", coupler="q"),
        mechanism("direct", ["d0", "d1"], "2", family="local", coupler="safe"),
    ]
    bursts = [burst("source", {0: ["d0"]}, "0", blocked=["q"])]
    shots = [
        shot(
            "w",
            ["d0", "d1"],
            ["blocked-local", "direct"],
            rows,
            burst_cap=1,
        )
    ]
    return experiment(rows, shots, bursts=bursts, exposure_limit=1)


def burst_family_global_cap_case():
    rows = [
        mechanism("same-family", ["d1"], "0", family="shared"),
        mechanism("fallback", ["d1"], "2", family="local"),
    ]
    bursts = [burst("source", {0: ["d0"]}, "0", family="shared")]
    shots = [
        shot("a", ["d0"], [], rows, round_id=0, burst_cap=1),
        shot("b", ["d1"], ["same-family", "fallback"], rows, round_id=2),
    ]
    families = [
        {"id": "shared", "occurrence_limit": 1, "window_rounds": 3, "window_limit": 2},
        {"id": "local", "occurrence_limit": 1, "window_rounds": 3, "window_limit": 1},
    ]
    return experiment(rows, shots, bursts=bursts, exposure_limit=1, families=families)


def burst_family_window_case():
    rows = [
        mechanism("same-family", ["d1"], "0", family="shared"),
        mechanism("fallback", ["d1"], "2", family="local"),
    ]
    bursts = [burst("source", {0: ["d0"]}, "0", family="shared")]
    shots = [
        shot("a", ["d0"], [], rows, round_id=0, burst_cap=1),
        shot("b", ["d1"], ["same-family", "fallback"], rows, round_id=1),
    ]
    families = [
        {"id": "shared", "occurrence_limit": 2, "window_rounds": 2, "window_limit": 1},
        {"id": "local", "occurrence_limit": 1, "window_rounds": 2, "window_limit": 1},
    ]
    return experiment(rows, shots, bursts=bursts, exposure_limit=1, families=families)


def frame_forbids_burst_case():
    rows = [mechanism("local", ["d0"], "2", family="local")]
    bursts = [burst("source", {0: ["d0"]}, "0")]
    shots = [shot("w", ["d0"], ["local"], rows, burst_cap=1)]
    frames = [
        frame("forbidden", forbidden_bursts=["source"]),
        frame("burst-frame", prior="1"),
    ]
    return experiment(rows, shots, bursts=bursts, exposure_limit=1, frames=frames)


def exact_burst_weight_case():
    rows = [mechanism("local", ["d0"], "1/2", family="local")]
    bursts = [burst("source", {0: ["d0"]}, "1/3")]
    shots = [shot("w", ["d0"], ["local"], rows, burst_cap=1)]
    return experiment(rows, shots, bursts=bursts, exposure_limit=1)


def burst_exposure_tiebreak_case():
    rows = [mechanism("unused", [], "9", family="local")]
    bursts = [
        burst("long", {0: ["d0"]}, "1", duration=2, intensity=1),
        burst("short", {0: ["d0"]}, "1", duration=1, intensity=1),
    ]
    shots = [shot("w", ["d0"], [], rows, burst_cap=1)]
    return experiment(rows, shots, bursts=bursts, exposure_limit=2)


def burst_count_tiebreak_case():
    rows = [mechanism("unused", [], "9", family="local")]
    bursts = [
        burst("single", {0: ["d0", "d1"]}, "1", duration=2),
        burst("pair-a", {0: ["d0"]}, "1/2"),
        burst("pair-b", {0: ["d1"]}, "1/2"),
    ]
    shots = [shot("w", ["d0", "d1"], [], rows, burst_cap=2)]
    return experiment(rows, shots, bursts=bursts, exposure_limit=2)


def burst_support_manifold_case():
    rows = [mechanism("unused", [], "9", family="local")]
    bursts = [
        burst("alpha", {0: ["d0"]}, "1"),
        burst("zeta", {0: ["d0"]}, "1"),
    ]
    shots = [shot("w", ["d0"], [], rows, burst_cap=1)]
    return experiment(rows, shots, bursts=bursts, exposure_limit=1)


def burst_key_orders_sources_case():
    rows = [mechanism("unused", [], "9", family="local")]
    bursts = [
        burst("z-source", {0: ["d1"]}, "0"),
        burst("a-source", {0: ["d0"]}, "0"),
    ]
    shots = [shot("w", ["d0", "d1"], [], rows, burst_cap=2)]
    return experiment(rows, shots, bursts=bursts, exposure_limit=2)


VARIANTS = [
    ("reordered-and-unknown-fields", reordered_unknown_case),
    ("frame-forbidden-hypothesis", forbidden_mechanism_case),
    ("family-cap-couples-shots", lambda: family_coupling_case(1)),
    ("family-cap-boundary-inclusive", lambda: family_coupling_case(2)),
    ("coupler-collision-blocks-local-pair", coupler_collision_case),
    ("cycle-cap-blocks-local-pair", lambda: cycle_cap_case(1)),
    ("cycle-cap-boundary-inclusive", lambda: cycle_cap_case(2)),
    ("detector-signatures-cancel-by-parity", parity_cancellation_case),
    ("logical-signatures-cancel-by-parity", logical_cancellation_case),
    ("exact-rational-objective", exact_fraction_case),
    ("worst-shot-secondary-objective", worst_shot_case),
    ("mechanism-count-tertiary-objective", mechanism_count_case),
    ("frame-support-before-representative-choice", frame_tie_case),
    ("complete-microstate-key-tie", lambda: microstate_tie_case(False)),
    ("logical-coset-support-counts", lambda: microstate_tie_case(True)),
    ("zero-cost-silent-mechanism-loses-on-count", silent_mechanism_case),
    ("same-hypothesis-is-per-shot-occurrence", lambda: repeated_occurrence_case(2)),
    ("family-limit-can-empty-physical-coset", lambda: repeated_occurrence_case(1)),
    ("empty-observed-syndrome", empty_syndrome_case),
    ("declared-logical-bit-order", logical_order_case),
    ("frame-prior-enters-total-weight", prior_cost_case),
    ("shot-input-order-is-nonsemantic", shot_order_case),
    ("delayed-detector-tail-controls-later-shot", delayed_tail_case),
    ("delayed-and-local-signatures-cancel-by-parity", delayed_parity_case),
    ("coupler-recovery-blocks-adjacent-reuse", lambda: recovery_case(1)),
    ("coupler-recovery-boundary-allows-later-reuse", lambda: recovery_case(2)),
    ("sliding-window-cap-defeats-per-shot-greedy", sliding_window_case),
    ("sliding-window-boundary-excludes-old-round", lambda: sliding_window_case(2)),
    ("temporal-tail-recovery-and-window-interact", temporal_interaction_case),
    ("latent-burst-spans-unobserved-round", burst_spans_unobserved_round_case),
    ("burst-detector-signatures-cancel-by-parity", burst_detector_parity_case),
    ("burst-logical-signatures-cancel-by-parity", burst_logical_parity_case),
    ("burst-exposure-boundary-is-inclusive", lambda: burst_exposure_case(2)),
    ("burst-exposure-limit-blocks-long-source", lambda: burst_exposure_case(1)),
    ("burst-exclusive-origin-blocks-pair", burst_exclusive_group_case),
    ("shot-burst-load-cap-blocks-pair", burst_load_cap_case),
    ("active-burst-blocks-local-coupler", burst_blocks_coupler_case),
    ("burst-counts-against-family-global-cap", burst_family_global_cap_case),
    ("burst-start-counts-in-family-window", burst_family_window_case),
    ("readout-frame-forbids-burst-source", frame_forbids_burst_case),
    ("exact-rational-burst-weight", exact_burst_weight_case),
    ("burst-exposure-secondary-objective", burst_exposure_tiebreak_case),
    ("burst-count-quaternary-objective", burst_count_tiebreak_case),
    ("burst-support-counts-likelihood-manifold", burst_support_manifold_case),
    ("burst-list-is-sorted-in-representative-key", burst_key_orders_sources_case),
]


def run_case(payload, tmp_path):
    input_path = tmp_path / "input" / "experiment.json"
    output_path = tmp_path / "nested" / "spectra" / "cosets.json"
    input_path.parent.mkdir(parents=True)
    raw = json.dumps(payload, indent=2) + "\n"
    input_path.write_text(raw, encoding="utf-8")
    completed = subprocess.run(
        [str(INFERENCE_INSTRUMENT), str(input_path), str(output_path)],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    assert input_path.read_text(encoding="utf-8") == raw
    return json.loads(output_path.read_text(encoding="utf-8"))


def assert_schema(spectrum):
    if spectrum["status"] == "no_physical_coset":
        assert set(spectrum) == {"status", "frames_examined", "shots_examined"}
        assert isinstance(spectrum["frames_examined"], int)
        assert isinstance(spectrum["shots_examined"], int)
        return
    assert set(spectrum) == SUCCESS_KEYS
    assert spectrum["status"] == "resolved"
    assert set(spectrum["readout_frame"]) == FRAME_KEYS
    assert all(set(row) == BURST_KEYS for row in spectrum["selected_bursts"])
    assert [row["id"] for row in spectrum["selected_bursts"]] == sorted(
        row["id"] for row in spectrum["selected_bursts"]
    )
    assert all(set(row) == SHOT_KEYS for row in spectrum["shots"])
    assert all(
        set(cycle_row) == CYCLE_KEYS
        for row in spectrum["shots"]
        for cycle_row in row["mechanisms_by_cycle"]
    )
    assert all(set(row) == FAMILY_KEYS for row in spectrum["family_occupancy"])
    assert all(
        row["active_occurrences"]
        == row["pauli_occurrences"] + row["burst_occurrences"]
        for row in spectrum["family_occupancy"]
    )
    manifold = spectrum["likelihood_manifold"]
    assert set(manifold) == MANIFOLD_KEYS
    assert all(set(row) == {"frame_id", "count"} for row in manifold["frame_support"])
    assert all(set(row) == {"burst_id", "count"} for row in manifold["burst_support"])
    assert all(set(row) == {"class_key", "count"} for row in manifold["joint_logical_support"])
    assert sum(row["count"] for row in manifold["frame_support"]) == manifold["multiplicity"]
    assert sum(row["count"] for row in manifold["joint_logical_support"]) == manifold["multiplicity"]
    assert manifold["burst_count"] == len(spectrum["selected_bursts"])
    assert all(row["reproduced_events"] == row["measured_events"] for row in spectrum["shots"])
    for field in ("total_neg_log_weight", "peak_shot_weight"):
        assert rational_text(Fraction(manifold[field])) == manifold[field]


def assert_variant_focus(name, spectrum):
    if name == "frame-forbidden-hypothesis":
        assert spectrum["shots"][0]["active_mechanisms"] == ["fallback"]
    elif name == "family-cap-couples-shots":
        assert sum(
            row["active_occurrences"]
            for row in spectrum["family_occupancy"]
            if row["family_id"] == "burst"
        ) == 1
    elif name == "family-cap-boundary-inclusive":
        assert next(
            row for row in spectrum["family_occupancy"] if row["family_id"] == "burst"
        )["active_occurrences"] == 2
    elif name == "coupler-collision-blocks-local-pair":
        assert spectrum["shots"][0]["active_mechanisms"] == ["joint"]
    elif name == "cycle-cap-blocks-local-pair":
        assert spectrum["shots"][0]["active_mechanisms"] == ["joint"]
    elif name == "cycle-cap-boundary-inclusive":
        assert spectrum["shots"][0]["active_mechanisms"] == ["left", "right"]
    elif name == "detector-signatures-cancel-by-parity":
        assert spectrum["shots"][0]["active_mechanisms"] == ["a", "b"]
    elif name == "logical-signatures-cancel-by-parity":
        assert spectrum["shots"][0]["logical_coset"] == []
    elif name == "exact-rational-objective":
        assert spectrum["likelihood_manifold"]["total_neg_log_weight"] == "1/3"
    elif name == "worst-shot-secondary-objective":
        assert spectrum["readout_frame"]["id"] == "spread"
    elif name == "mechanism-count-tertiary-objective":
        assert spectrum["shots"][0]["active_mechanisms"] == ["one"]
    elif name == "frame-support-before-representative-choice":
        assert spectrum["readout_frame"]["id"] == "a-frame"
        assert spectrum["likelihood_manifold"]["multiplicity"] == 2
    elif name == "complete-microstate-key-tie":
        assert spectrum["shots"][0]["active_mechanisms"] == ["a-mechanism"]
    elif name == "logical-coset-support-counts":
        assert len(spectrum["likelihood_manifold"]["joint_logical_support"]) == 2
    elif name == "zero-cost-silent-mechanism-loses-on-count":
        assert spectrum["shots"][0]["active_mechanisms"] == ["needed"]
    elif name == "same-hypothesis-is-per-shot-occurrence":
        assert spectrum["family_occupancy"][0]["active_occurrences"] == 2
    elif name == "family-limit-can-empty-physical-coset":
        assert spectrum == {"status": "no_physical_coset", "frames_examined": 1, "shots_examined": 2}
    elif name == "empty-observed-syndrome":
        assert spectrum["shots"][0]["active_mechanisms"] == []
    elif name == "declared-logical-bit-order":
        assert spectrum["likelihood_manifold"]["joint_logical_support"][0]["class_key"] == "w:01"
    elif name == "frame-prior-enters-total-weight":
        assert spectrum["readout_frame"]["id"] == "offset"
    elif name == "delayed-detector-tail-controls-later-shot":
        assert spectrum["shots"][1]["inherited_events"] == ["d1"]
        assert spectrum["shots"][1]["active_mechanisms"] == []
    elif name == "delayed-and-local-signatures-cancel-by-parity":
        assert spectrum["shots"][1]["active_mechanisms"] == ["cancel"]
    elif name == "coupler-recovery-blocks-adjacent-reuse":
        assert spectrum["shots"][1]["active_mechanisms"] == ["fallback"]
    elif name == "coupler-recovery-boundary-allows-later-reuse":
        assert spectrum["shots"][1]["active_mechanisms"] == ["pulse"]
    elif name == "sliding-window-cap-defeats-per-shot-greedy":
        assert [row["active_mechanisms"] for row in spectrum["shots"]] == [
            ["burst"],
            ["local"],
            ["burst"],
        ]
    elif name == "sliding-window-boundary-excludes-old-round":
        assert [row["active_mechanisms"] for row in spectrum["shots"]] == [
            ["burst"],
            ["burst"],
            ["local"],
        ]
    elif name == "temporal-tail-recovery-and-window-interact":
        assert spectrum["shots"][1]["active_mechanisms"] == ["local-late"]
    elif name == "latent-burst-spans-unobserved-round":
        assert [row["id"] for row in spectrum["selected_bursts"]] == ["thermal"]
        assert spectrum["likelihood_manifold"]["burst_exposure"] == 3
    elif name == "burst-detector-signatures-cancel-by-parity":
        assert spectrum["shots"][0]["burst_events"] == ["d1", "d2"]
    elif name == "burst-logical-signatures-cancel-by-parity":
        assert spectrum["shots"][0]["burst_logical_coset"] == []
        assert spectrum["shots"][0]["logical_coset"] == []
    elif name == "burst-exposure-boundary-is-inclusive":
        assert [row["id"] for row in spectrum["selected_bursts"]] == ["long"]
        assert spectrum["likelihood_manifold"]["burst_exposure"] == 2
    elif name == "burst-exposure-limit-blocks-long-source":
        assert spectrum["selected_bursts"] == []
        assert [row["active_mechanisms"] for row in spectrum["shots"]] == [
            ["local-a"],
            ["local-b"],
        ]
    elif name in {"burst-exclusive-origin-blocks-pair", "shot-burst-load-cap-blocks-pair"}:
        assert spectrum["selected_bursts"] == []
        assert spectrum["shots"][0]["active_mechanisms"] == ["joint"]
    elif name == "active-burst-blocks-local-coupler":
        assert spectrum["selected_bursts"] == []
        assert spectrum["shots"][0]["active_mechanisms"] == ["direct"]
    elif name in {
        "burst-counts-against-family-global-cap",
        "burst-start-counts-in-family-window",
    }:
        assert [row["id"] for row in spectrum["selected_bursts"]] == ["source"]
        assert spectrum["shots"][1]["active_mechanisms"] == ["fallback"]
    elif name == "readout-frame-forbids-burst-source":
        assert spectrum["readout_frame"]["id"] == "burst-frame"
        assert [row["id"] for row in spectrum["selected_bursts"]] == ["source"]
    elif name == "exact-rational-burst-weight":
        assert spectrum["likelihood_manifold"]["total_neg_log_weight"] == "1/3"
    elif name == "burst-exposure-secondary-objective":
        assert [row["id"] for row in spectrum["selected_bursts"]] == ["short"]
    elif name == "burst-count-quaternary-objective":
        assert [row["id"] for row in spectrum["selected_bursts"]] == ["single"]
    elif name == "burst-support-counts-likelihood-manifold":
        assert spectrum["likelihood_manifold"]["multiplicity"] == 2
        assert spectrum["likelihood_manifold"]["burst_support"] == [
            {"burst_id": "alpha", "count": 1},
            {"burst_id": "zeta", "count": 1},
        ]
    elif name == "burst-list-is-sorted-in-representative-key":
        assert spectrum["representative_key"] == "m|bursts=a-source,z-source|w="


def test_quantum_inference_instrument_is_available():
    """The requested stabilizer-burst inference instrument is available."""
    assert INFERENCE_INSTRUMENT.is_file()
    assert os.access(INFERENCE_INSTRUMENT, os.X_OK)


def test_public_input_integrity():
    """The published scientific fixture remains the reviewed temporal experiment."""
    assert hashlib.sha256(PUBLIC_INPUT.read_bytes()).hexdigest() == PUBLIC_INPUT_SHA256


@pytest.mark.parametrize("args", [[], [str(PUBLIC_INPUT)], [str(PUBLIC_INPUT), "/tmp/out.json", "extra"]])
def test_laboratory_handoff_rejects_wrong_path_count(args):
    """Every path count other than observations plus spectrum is rejected."""
    completed = subprocess.run([str(INFERENCE_INSTRUMENT), *args], text=True, capture_output=True, timeout=10, check=False)
    assert completed.returncode != 0


def test_public_spectrum_exact():
    """The public frame, logical cosets, manifold counts, and representative match exact enumeration."""
    actual = json.loads(PUBLIC_OUTPUT.read_text(encoding="utf-8"))
    assert_schema(actual)
    assert actual == expected_spectrum(load_public())


def test_public_run_exercises_joint_quantum_inference():
    """The visible experiment binds frame bias, latent bursts, exact weight, and chronology."""
    actual = json.loads(PUBLIC_OUTPUT.read_text(encoding="utf-8"))
    assert actual["readout_frame"]["id"] == "phase-biased-frame"
    assert [row["id"] for row in actual["selected_bursts"]] == ["thermal-sweep"]
    assert [row["round"] for row in actual["shots"]] == [0, 1, 2]
    assert actual["shots"][1]["burst_events"] == ["S1"]
    assert actual["shots"][1]["burst_logical_coset"] == ["LZ"]
    assert actual["shots"][1]["active_mechanisms"] == []
    assert actual["likelihood_manifold"]["total_neg_log_weight"] == "9/4"
    assert actual["likelihood_manifold"]["burst_exposure"] == 3


@pytest.mark.parametrize(("name", "builder"), VARIANTS, ids=[name for name, _ in VARIANTS])
def test_compatible_quantum_variants(name, builder, tmp_path):
    """Compatible experiments isolate parity, physical caps, exact weights, support, and representation."""
    payload = builder()
    actual = run_case(payload, tmp_path)
    assert_schema(actual)
    assert actual == expected_spectrum(payload), name
    assert_variant_focus(name, actual)


def test_distinct_observations_require_a_distinct_coset_spectrum(tmp_path):
    """Changed shot physics yields a new spectrum without changing the observation bytes."""
    payload = copy.deepcopy(load_public())
    payload["readout_frames"][1]["prior_weight"] = "9"
    actual = run_case(payload, tmp_path)
    assert actual == expected_spectrum(payload)
    assert actual != json.loads(PUBLIC_OUTPUT.read_text(encoding="utf-8"))
