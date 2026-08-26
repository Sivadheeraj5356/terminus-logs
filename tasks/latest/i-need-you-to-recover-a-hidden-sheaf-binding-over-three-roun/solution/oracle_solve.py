#!/usr/bin/env python3
"""Reference oracle: recover every hidden sheaf binding by REAL PLAY.

This runs at grading time as the unprivileged agent user, dials the keeper over the Unix endpoint,
and drives ONLY the documented tally grammar (read / name / bind / next). It holds no stretches and
reads no keeper file: it recovers each round's two stretches purely by naming handfuls and reasoning
about the bound counts, exactly as a human tally clerk would.

The hard part is the garbled reply. Exactly one reply per round is wrong (its bound count shifted by
one). A strict "keep only bindings matching every reply" filter throws the true binding away the
moment the wrong reply lands, so this solver instead keeps every binding that disagrees with AT MOST
ONE reply so far. It chooses each handful to split the surviving set as hard as possible under that
model, then binds the stretches once the survivors collapse to a single candidate (or the
lexicographically smallest survivor if the budget runs out first).

There is no ANSWERS table, no privileged reveal, and no reading of /opt/keeper: the only channel
used is the same endpoint any tally dialer uses.
"""
import os
import re
import socket
import sys
import time

ENDPOINT_PATH = os.environ.get("RB_KEEPER_ENDPOINT", "/run/ryebank/ryebank.sock")

DEFAULT_N = 12
DEFAULT_BUDGET = 8


# --------------------------------------------------------------------------- IO

def send(cmd):
    """One request/response over the endpoint, matching the tally dialer's one-shot protocol."""
    last = ""
    for _ in range(150):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(30)
            s.connect(ENDPOINT_PATH)
        except OSError as exc:
            last = str(exc)
            time.sleep(0.2)
            continue
        try:
            s.sendall((cmd + "\n").encode())
            try:
                s.shutdown(socket.SHUT_WR)
            except OSError:
                pass
            chunks = []
            while True:
                d = s.recv(4096)
                if not d:
                    break
                chunks.append(d)
            text = b"".join(chunks).decode("utf-8", "replace")
            # The keeper binds its endpoint before the per-session secret is generated and answers
            # "warming up" until ready; treat that like a not-yet-bound endpoint and retry the whole
            # request. Generation finishes in well under a second, so this window is tiny.
            if "warming up" in text:
                last = "keeper warming up"
                time.sleep(0.2)
                continue
            return text
        finally:
            s.close()
    raise SystemExit(f"oracle cannot reach the keeper at {ENDPOINT_PATH}: {last}")


# ---------------------------------------------------------------- game model

def all_bindings(n):
    """Every legal binding: two disjoint, non-adjacent stretches over sheaves 1..n, left stretch
    first. A stretch is an inclusive run [lo,hi]; the two stretches are separated by at least one
    loose sheaf (left.hi < right.lo - 1)."""
    runs = [(lo, hi) for lo in range(1, n + 1) for hi in range(lo, n + 1)]
    out = []
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            a, b = runs[i], runs[j]
            if a[1] < b[0] - 1:
                out.append((a, b))
            elif b[1] < a[0] - 1:
                out.append((b, a))
    return out


def bound(hand, binding):
    """How many handful sheaves are bound: how many fall inside either run. Mirrors the keeper.
    hand is a tuple of sheaf numbers; binding is a pair of (lo,hi) stretches."""
    n = 0
    for p in hand:
        for lo, hi in binding:
            if lo <= p <= hi:
                n += 1
                break
    return n


def garble(o, m):
    """The single garbled count the keeper would emit for a truthful o against a handful of m
    sheaves: the first legal minimal shift in the keeper's fixed order down-one then up-one. The
    solver uses this only to enumerate which counts a handful could plausibly produce, never to
    learn a binding."""
    for cand in (o - 1, o + 1):
        if 0 <= cand <= m and cand != o:
            return cand
    return o


# ---------------------------------------------------------------- deduction

def parse_count(reply):
    """Pull the bound count out of a keeper name reply like 'bound 2\\n...'."""
    m = re.search(r"bound\s+(\d+)", reply)
    if not m:
        raise SystemExit(f"oracle could not parse a count from:\n{reply}")
    return int(m.group(1))


def read_status():
    """Recover (rounds_total, n, budget) from the live read output."""
    st = send("read")
    total = n = budget = None
    m = re.search(r"round\s+\d+\s+of\s+(\d+)", st)
    if m:
        total = int(m.group(1))
    m = re.search(r"sheaves\s+1\.\.(\d+)", st)
    if m:
        n = int(m.group(1))
    m = re.search(r"budget\s+(\d+)", st)
    if m:
        budget = int(m.group(1))
    if total is None:
        raise SystemExit(f"oracle could not read the round count from read:\n{st}")
    return total, n or DEFAULT_N, budget or DEFAULT_BUDGET


def make_handfuls(n):
    """The handful pool the solver names with. Contiguous windows of every position and length sweep
    out where each stretch begins and ends, and the two parity handfuls split odd from even sheaves;
    together they carry the most information about a two-stretch binding while keeping the pool small
    enough to evaluate the worst-case split quickly. Each handful leaves out at least one sheaf."""
    pool = []
    seen = set()
    for lo in range(1, n + 1):
        for hi in range(lo, n + 1):
            c = tuple(range(lo, hi + 1))
            if 0 < len(c) < n and c not in seen:
                seen.add(c)
                pool.append(c)
    for parity in (0, 1):
        c = tuple(p for p in range(1, n + 1) if p % 2 == parity)
        if 0 < len(c) < n and c not in seen:
            seen.add(c)
            pool.append(c)
    return pool


def surviving(cands, history):
    """Every candidate binding that disagrees with at most one reply."""
    out = []
    for c in cands:
        misses = 0
        ok = True
        for hand, obs in history:
            if bound(hand, c) != obs:
                misses += 1
                if misses > 1:
                    ok = False
                    break
        if ok:
            out.append(c)
    return out


def choose_handful(cands, history, handfuls):
    """Pick the handful minimising the worst-case number of survivors under the at-most-one-wrong
    model. For each handful, every true binding in the surviving set could yield its truthful count
    or (if this handful is the garbled one) the garbled count, so both are reachable; we take the
    observation leaving the most survivors and minimise that. Ties break toward the tightest total
    spread, then by a stable key for determinism."""
    base_miss = {}
    for c in cands:
        misses = 0
        for hand, obs in history:
            if bound(hand, c) != obs:
                misses += 1
        base_miss[c] = misses

    best = None
    best_key = None
    for hand in handfuls:
        m = len(hand)
        reachable = set()
        for t in cands:
            o = bound(hand, t)
            reachable.add(o)
            reachable.add(garble(o, m))
        worst = 0
        total = 0
        for obs in reachable:
            cnt = 0
            for c in cands:
                miss = base_miss[c] + (0 if bound(hand, c) == obs else 1)
                if miss <= 1:
                    cnt += 1
            if cnt == 0:
                continue
            if cnt > worst:
                worst = cnt
            total += cnt
        key = (worst, total, hand)
        if best_key is None or key < best_key:
            best_key = key
            best = hand
    return best


def fmt_bind(binding):
    a, b = binding
    return f"{a[0]}-{a[1]},{b[0]}-{b[1]}"


def solve_round(n, budget, all_b, handfuls):
    """Play one round to a bind, using only name/bind. Returns the reply text from the keeper's bind
    so the caller can confirm the win."""
    cands = list(all_b)
    history = []
    used = 0
    # A fixed diverse opener (first contiguous window) carries no prior info yet keeps the run
    # deterministic and cheap on the first move.
    opener = handfuls[0]
    while used < budget:
        if len(cands) <= 1:
            break
        hand = opener if used == 0 else choose_handful(cands, history, handfuls)
        reply = send("name " + ",".join(str(p) for p in hand))
        obs = parse_count(reply)
        used += 1
        history.append((hand, obs))
        cands = surviving(cands, history)
        if not cands:
            cands = surviving(list(all_b), history) or list(all_b)
    guess = cands[0] if cands else all_b[0]
    return send("bind " + fmt_bind(guess))


def main():
    total, n, budget = read_status()
    all_b = all_bindings(n)
    handfuls = make_handfuls(n)
    for i in range(total):
        reply = solve_round(n, budget, all_b, handfuls)
        if "correct" not in reply:
            sys.stderr.write(f"oracle failed to recover round {i + 1}:\n{reply}\n")
            sys.exit(1)
        if i + 1 < total:
            send("next")
    print("solve complete")


if __name__ == "__main__":
    main()
