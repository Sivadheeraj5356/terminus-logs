import re

import numpy as np

ALLOWED = {"ry", "cx"}


def parse(text):
    """Parse a minimal OpenQASM 3 body into (n_qubits, gate_list).

    Recognised statements are the qubit declaration, ry(theta) q[i], and
    cx q[c], q[t]. Header lines, includes, comments, and blank lines are
    ignored. Any other gate token is reported so the caller can reject it.
    Returns (nq, gates) where each gate is either ("ry", theta, target) or
    ("cx", control, target).
    """
    nq = None
    gates = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.endswith(";"):
            line = line[:-1].strip()
        if not line or line.startswith("//"):
            continue
        low = line.lower()
        if (
            low.startswith("openqasm")
            or low.startswith("include")
            or low.startswith("bit")
            or low.startswith("creg")
            or low.startswith("gate ")
        ):
            continue
        mq = re.search(r"qubit\s*\[\s*(\d+)\s*\]", low)
        if mq:
            nq = int(mq.group(1))
            continue
        mq2 = re.search(r"qreg\s+\w+\s*\[\s*(\d+)\s*\]", low)
        if mq2:
            nq = int(mq2.group(1))
            continue
        name = low.split()[0].split("(")[0]
        idxs = [int(x) for x in re.findall(r"\[\s*(\d+)\s*\]", line)]
        if name == "ry":
            mt = re.search(r"ry\s*\(([^)]*)\)", line)
            if mt is None:
                gates.append(("bad", []))
                continue
            theta = float(mt.group(1).strip())
            gates.append(("ry", theta, idxs[0]))
        elif name == "cx":
            gates.append(("cx", idxs[0], idxs[1]))
        else:
            gates.append((name, idxs))
    return nq, gates


def only_allowed(gates):
    for g in gates:
        if g[0] not in ALLOWED:
            return False
    return True


def cx_count(gates):
    return sum(1 for g in gates if g[0] == "cx")


def simulate(gates, n):
    """Return the complex128 statevector produced by the gate list from
    |0...0>. Statevector index j has qubit k on bit (n-1-k): qubit 0 is the
    most significant bit (big-endian), matching the disclosed convention."""
    sv = np.zeros(1 << n, dtype=np.complex128)
    sv[0] = 1.0
    for g in gates:
        if g[0] == "ry":
            sv = _apply_ry(sv, n, g[2], g[1])
        elif g[0] == "cx":
            sv = _apply_cx(sv, n, g[1], g[2])
        else:
            raise ValueError("illegal gate " + str(g[0]))
    return sv


def _apply_ry(sv, n, qk, theta):
    c = np.cos(theta / 2.0)
    s = np.sin(theta / 2.0)
    bit = n - 1 - qk
    mask = 1 << bit
    out = sv.copy()
    idx = np.arange(len(sv))
    zero = idx[(idx & mask) == 0]
    one = zero | mask
    a0 = sv[zero]
    a1 = sv[one]
    out[zero] = c * a0 - s * a1
    out[one] = s * a0 + c * a1
    return out


def _apply_cx(sv, n, ctrl, tgt):
    bc = n - 1 - ctrl
    bt = n - 1 - tgt
    mc = 1 << bc
    mt = 1 << bt
    out = sv.copy()
    idx = np.arange(len(sv))
    sel = idx[(idx & mc) != 0]
    out[sel] = sv[sel ^ mt]
    return out


def phase_aligned_distance(sv, target):
    """L2 distance between sv and target after removing a global phase.

    target is a real nonnegative vector; align on its first nonzero entry.
    """
    tgt = np.asarray(target, dtype=np.complex128)
    ref = None
    for i in range(len(tgt)):
        if abs(tgt[i]) > 1e-12:
            ref = i
            break
    if ref is None:
        return float(np.linalg.norm(sv))
    a = sv[ref]
    if abs(a) > 1e-12:
        phase = a / abs(a)
        sv = sv / phase
    return float(np.linalg.norm(sv - tgt))
