"""Verifier-only reference. Mirrors duel_rules.md + session_semantics.md."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

POS_MIN, POS_MAX = 0, 9
IN_LEFT, IN_RIGHT, IN_ATTACK, IN_BLOCK, IN_SPECIAL = 1, 2, 4, 8, 16
INITIAL = ((2, 100, 0), (7, 100, 0))


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _delta(inp):
    left = inp & IN_LEFT
    right = inp & IN_RIGHT
    if left and not right:
        return -1
    if right and not left:
        return 1
    return 0


def step(state, in0, in1):
    (pos0, hp0, m0), (pos1, hp1, m1) = state
    np0 = _clamp(pos0 + _delta(in0), POS_MIN, POS_MAX)
    np1 = _clamp(pos1 + _delta(in1), POS_MIN, POS_MAX)
    if np0 >= np1:
        np0, np1 = pos0, pos1
    dist = np1 - np0

    def action(atk_in, atk_meter, opp_in):
        if (atk_in & IN_SPECIAL) and atk_meter >= 10 and dist <= 3:
            return 25, -10
        if (atk_in & IN_ATTACK) and dist <= 1:
            return (3 if (opp_in & IN_BLOCK) else 10), 2
        return 0, 0

    dmg_to_1, dm0 = action(in0, m0, in1)
    dmg_to_0, dm1 = action(in1, m1, in0)
    nhp0 = _clamp(hp0 - dmg_to_0, 0, 100)
    nhp1 = _clamp(hp1 - dmg_to_1, 0, 100)
    nm0 = _clamp(m0 + dm0, 0, 20)
    nm1 = _clamp(m1 + dm1, 0, 20)
    return ((np0, nhp0, nm0), (np1, nhp1, nm1))


def _ser(state):
    (p0, p1) = state
    return bytes([p0[0], p0[1], p0[2], p1[0], p1[1], p1[2]])


def _digest(states):
    buf = bytearray()
    for st in states:
        buf += _ser(st)
    return hashlib.sha256(bytes(buf)).hexdigest()


def remote_for_tick(confirmed, k, inputs):
    if k <= confirmed:
        return inputs[k][1]
    if confirmed >= 0:
        return inputs[confirmed][1]
    return 0


def run_host(inputs):
    st = INITIAL
    states = [st]
    for (i0, i1) in inputs:
        st = step(st, i0, i1)
        states.append(st)
    return _digest(states), st


def drive_online(inputs, delay):
    n = len(inputs)
    saved = [INITIAL] * (n + 1)
    pred_used = [0] * n
    pred_state = [INITIAL] * n
    confirmed = -1
    rollbacks = 0

    def receive(f, upper):
        nonlocal confirmed, rollbacks
        r = f - delay
        if 0 <= r < n and r < f and r > confirmed:
            confirmed = r
            if pred_used[r] != inputs[r][1]:
                rollbacks += 1
                st = saved[r]
                for k in range(r, upper):
                    ri = remote_for_tick(confirmed, k, inputs)
                    pred_used[k] = ri
                    st = step(st, inputs[k][0], ri)
                    saved[k + 1] = st

    for f in range(n):
        receive(f, f)
        ri = remote_for_tick(confirmed, f, inputs)
        pred_used[f] = ri
        st = step(saved[f], inputs[f][0], ri)
        saved[f + 1] = st
        pred_state[f] = st
    for f in range(n, n + delay):
        receive(f, n)

    conf_digest = _digest([INITIAL] + [saved[k + 1] for k in range(n)])
    pred_digest = _digest([INITIAL] + [pred_state[k] for k in range(n)])
    return {
        "pred_digest": pred_digest,
        "confirmed_digest": conf_digest,
        "rollbacks": rollbacks,
        "final": saved[n],
    }


def row_for(tape):
    inputs = [(int(a), int(b)) for a, b in tape["inputs"]]
    delay = int(tape["delay"])
    host_digest, host_final = run_host(inputs)
    cli = drive_online(inputs, delay)
    return {
        "tape_id": tape.get("tape_id", ""),
        "delay": delay,
        "ticks": len(inputs),
        "host_digest": host_digest,
        "pred_digest": cli["pred_digest"],
        "confirmed_digest": cli["confirmed_digest"],
        "rollbacks": cli["rollbacks"],
        "converged": cli["confirmed_digest"] == host_digest,
        "final_hp": [host_final[0][1], host_final[1][1]],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tape-json")
    parser.add_argument("--tape-file")
    args = parser.parse_args()
    if args.tape_json:
        tape = json.loads(args.tape_json)
    else:
        tape = json.loads(Path(args.tape_file).read_text(encoding="utf-8"))
    print(json.dumps(row_for(tape)))


if __name__ == "__main__":
    main()
