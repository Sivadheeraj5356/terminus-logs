"""Verifier for the link rate provisioner.

Recomputes every derived figure independently from the raw Redis registry
bytes and the API's backing documents, then checks the provisioned system
state, the manifest, and the seal against that recomputation.
"""

import functools
import grp
import hashlib
import json
import os
import pwd
import socket
import stat
import struct
import subprocess

MANIFEST_PATH = "/app/out/link-manifest.json"
SEAL_PATH = "/app/out/seal.hex"
TOOL_PATH = "/app/bin/provision-link-rates"
SNAPSHOT_PATH = "/logs/verifier/access-snapshot.log"
PRIVATE_DIR = "/opt/api-private"
STATE_BASE = "/var/lib/link-rate"

MASK64 = (1 << 64) - 1
FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3
UNIT = 1500
BURST_DIVISOR = 5500
BURST_MIN = 24
RATE_DIVISOR = 40000
TIER_BASE = {"background": 2000, "general": 5000, "express": 12000}
TIER_CEIL = {"background": 3500, "general": 8000, "express": 18000}


def _redis_cmd(sock_file, sock, *args):
    out = b"*%d\r\n" % len(args)
    for a in args:
        if isinstance(a, str):
            a = a.encode()
        out += b"$%d\r\n%s\r\n" % (len(a), a)
    sock.sendall(out)
    return _redis_reply(sock_file)


def _redis_reply(sock_file):
    line = sock_file.readline().rstrip(b"\r\n")
    kind, rest = line[:1], line[1:]
    if kind == b"+":
        return rest.decode()
    if kind == b":":
        return int(rest)
    if kind == b"-":
        raise AssertionError("redis error: %s" % rest.decode())
    if kind == b"$":
        n = int(rest)
        if n < 0:
            return None
        data = sock_file.read(n + 2)
        return data[:n]
    if kind == b"*":
        return [_redis_reply(sock_file) for _ in range(int(rest))]
    raise AssertionError("unexpected redis reply")


def _parse_ledger(blob):
    assert blob[:4] == b"LKR1", "bad ledger magic"
    assert blob[4] == 1, "bad ledger version"
    flags = blob[5]
    count = struct.unpack("<H", blob[6:8])[0]
    payload = blob[8:-2]
    assert struct.unpack(">H", blob[-2:])[0] == sum(payload) % 65521, (
        "ledger trailer mismatch"
    )
    values, v = [], 0
    for b in payload:
        v = (v << 7) | (b & 0x7F)
        if not (b & 0x80):
            values.append(v)
            v = 0
    assert len(values) == count, "ledger varint count mismatch"
    return (flags & 1) == 1, values


def _apply_ops(value, ops):
    v = value
    for op in ops:
        if op["op"] == "scale":
            v = (v * op["num"]) // op["den"]
        elif op["op"] == "add":
            v = v + op["k"]
        elif op["op"] == "floor":
            v = max(v, op["k"])
        else:
            raise AssertionError("unknown op")
    return v


def _smooth(adjusted, drop_carry=False):
    s = [adjusted[0]]
    carry = 0
    for d in range(1, len(adjusted)):
        t = 5 * s[-1] + adjusted[d] + (0 if drop_carry else carry)
        s.append(t // 6)
        carry = t % 6
    return s


def _weight(s_value):
    return (s_value + UNIT - 1) // UNIT


def _le(value, width):
    return int(value).to_bytes(width, "little")


def _fold(acc, data):
    for b in data:
        acc = ((acc ^ b) * FNV_PRIME) & MASK64
    return acc


def _seal_chain(rows, mode="pre"):
    acc = FNV_OFFSET
    sub = 0
    for pos, day, s_val, w_val in rows:
        sub = (sub + s_val + w_val) & MASK64
        snap = acc
        body = _le(pos, 2) + _le(day, 2) + _le(s_val, 8) + _le(sub, 8)
        if mode == "pre":
            acc = _fold(acc, body + _le(snap, 8))
        else:
            acc = _fold(acc, body)
            acc = _fold(acc, _le(acc, 8))
    return acc


def _shaping_values(smoothed, weights, tier):
    peak = max(smoothed)
    total_units = sum(weights)
    rate = min(TIER_BASE[tier] + total_units // RATE_DIVISOR, TIER_CEIL[tier])
    burst = max((peak + BURST_DIVISOR - 1) // BURST_DIVISOR, BURST_MIN)
    return {
        "peak": peak,
        "total_units": total_units,
        "rate_kbit": rate,
        "burst_kib": burst,
    }


@functools.lru_cache(maxsize=1)
def _reference():
    """Recompute the whole pipeline from raw registry bytes and API docs."""
    with open(PRIVATE_DIR + "/links.json") as f:
        links = json.load(f)["links"]
    with open(PRIVATE_DIR + "/shaping.json") as f:
        shaping = json.load(f)
    meta = {link["iface_id"]: link for link in links}

    sock = socket.create_connection(("127.0.0.1", 6379), timeout=5.0)
    sock_file = sock.makefile("rb")
    registry_order = [
        x.decode() for x in _redis_cmd(sock_file, sock, "LRANGE", "link:index", "0", "-1")
    ]
    ledgers = {
        iface: _redis_cmd(sock_file, sock, "GET", "link:ledger:" + iface)
        for iface in registry_order
    }
    sock.close()

    detached, smoothed, naive_nocarry, naive_revops, weights = {}, {}, {}, {}, {}
    for iface in registry_order:
        is_detached, raws = _parse_ledger(ledgers[iface])
        ops = shaping[iface]["ops"]
        adjusted = [_apply_ops(v, ops) for v in raws]
        adjusted_rev = [_apply_ops(v, list(reversed(ops))) for v in raws]
        detached[iface] = is_detached
        smoothed[iface] = _smooth(adjusted)
        naive_nocarry[iface] = _smooth(adjusted, drop_carry=True)
        naive_revops[iface] = _smooth(adjusted_rev)
        weights[iface] = [_weight(s) for s in smoothed[iface]]

    rows = []
    for pos, iface in enumerate(registry_order):
        for day, s_val in enumerate(smoothed[iface]):
            rows.append((pos, day, s_val, weights[iface][day]))

    values = {}
    for iface in registry_order:
        if not detached[iface]:
            values[iface] = _shaping_values(
                smoothed[iface], weights[iface], meta[iface]["tier"]
            )

    return {
        "registry_order": registry_order,
        "meta": meta,
        "detached": detached,
        "smoothed": smoothed,
        "naive_nocarry": naive_nocarry,
        "naive_revops": naive_revops,
        "weights": weights,
        "rows": rows,
        "values": values,
        "seal": "%016x" % _seal_chain(rows, "pre"),
    }


def _manifest():
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def _active_ids(ref):
    return sorted(iface for iface, d in ref["detached"].items() if not d)


def _expected_dropin(iface, vals):
    return (
        "[Match]\n"
        "Name=%s\n"
        "\n"
        "[TokenBucketFilter]\n"
        "Parent=root\n"
        "Rate=%dK\n"
        "BurstBytes=%dK\n"
        "LatencySec=0.05\n" % (iface, vals["rate_kbit"], vals["burst_kib"])
    )


def _expected_env(iface, uid, tier, vals):
    return (
        "IFACE=%s\n"
        "LINK_UID=%d\n"
        "TIER=%s\n"
        "PEAK=%d\n"
        "TOTAL_UNITS=%d\n"
        "RATE_KBIT=%d\n"
        "BURST_KIB=%d\n"
        % (
            iface, uid, tier, vals["peak"], vals["total_units"],
            vals["rate_kbit"], vals["burst_kib"],
        )
    )


def test_manifest_shape():
    """The manifest exists with the documented schema and ordering, and seal.hex mirrors its seal."""
    manifest = _manifest()
    assert set(manifest) == {"interfaces", "detached", "row_count", "seal"}
    ids = [e["iface_id"] for e in manifest["interfaces"]]
    assert ids == sorted(ids)
    assert manifest["detached"] == sorted(manifest["detached"])
    for entry in manifest["interfaces"]:
        assert set(entry) == {
            "iface_id", "uid", "tier", "peak", "total_units",
            "rate_kbit", "burst_kib",
        }
    seal = manifest["seal"]
    assert isinstance(seal, str) and len(seal) == 16
    assert seal == seal.lower() and all(c in "0123456789abcdef" for c in seal)
    with open(SEAL_PATH) as f:
        assert f.read() == seal + "\n"


def test_accounts_provisioned():
    """Every active interface has its group and nologin user with the fixed uid and state home."""
    ref = _reference()
    for iface in _active_ids(ref):
        uid = ref["meta"][iface]["uid"]
        group = grp.getgrnam(iface)
        assert group.gr_gid == uid, iface
        user = pwd.getpwnam(iface)
        assert user.pw_uid == uid and user.pw_gid == uid, iface
        assert user.pw_shell == "/usr/sbin/nologin", iface
        assert user.pw_dir == STATE_BASE + "/" + iface, iface


def test_state_directories():
    """Every active interface's state directory exists with mode 0750 and the right owner."""
    ref = _reference()
    for iface in _active_ids(ref):
        uid = ref["meta"][iface]["uid"]
        st = os.stat(STATE_BASE + "/" + iface)
        assert stat.S_ISDIR(st.st_mode), iface
        assert stat.S_IMODE(st.st_mode) == 0o750, iface
        assert st.st_uid == uid and st.st_gid == uid, iface


def test_networkd_dropins():
    """Every active interface's networkd drop-in carries exactly the documented lines."""
    ref = _reference()
    for iface in _active_ids(ref):
        with open("/etc/systemd/network/40-" + iface + ".network") as f:
            assert f.read() == _expected_dropin(iface, ref["values"][iface]), iface


def test_policy_env_files():
    """Every active interface's env file carries exactly the documented lines in order."""
    ref = _reference()
    for iface in _active_ids(ref):
        meta = ref["meta"][iface]
        with open("/etc/link-rate.d/" + iface + ".env") as f:
            content = f.read()
        assert content == _expected_env(
            iface, meta["uid"], meta["tier"], ref["values"][iface]
        ), iface


def test_detached_absent():
    """Detached interfaces left no account and no files, yet appear in the manifest list."""
    ref = _reference()
    manifest = _manifest()
    detached = sorted(iface for iface, d in ref["detached"].items() if d)
    assert manifest["detached"] == detached
    active_ids = {e["iface_id"] for e in manifest["interfaces"]}
    for iface in detached:
        assert iface not in active_ids
        for lookup, name in ((pwd.getpwnam, "user"), (grp.getgrnam, "group")):
            try:
                lookup(iface)
                raise AssertionError("%s %s exists for detached interface" % (name, iface))
            except KeyError:
                pass
        assert not os.path.exists(STATE_BASE + "/" + iface), iface
        assert not os.path.exists("/etc/systemd/network/40-" + iface + ".network"), iface
        assert not os.path.exists("/etc/link-rate.d/" + iface + ".env"), iface


def test_manifest_values_match_recomputed():
    """Every manifest entry matches the values recomputed from raw registry bytes and shaping ops."""
    ref = _reference()
    manifest = _manifest()
    entries = {e["iface_id"]: e for e in manifest["interfaces"]}
    assert set(entries) == set(_active_ids(ref))
    for iface, vals in ref["values"].items():
        entry = entries[iface]
        assert entry["uid"] == ref["meta"][iface]["uid"], iface
        assert entry["tier"] == ref["meta"][iface]["tier"], iface
        for key, expected in vals.items():
            assert entry[key] == expected, (iface, key)


def test_values_not_from_naive_models():
    """The delivered values track the correct pipeline, not its naive misreadings."""
    ref = _reference()
    manifest = _manifest()
    entries = {e["iface_id"]: e for e in manifest["interfaces"]}
    for naive_key in ("naive_nocarry", "naive_revops"):
        diverged = 0
        for iface in _active_ids(ref):
            tier = ref["meta"][iface]["tier"]
            naive_smoothed = ref[naive_key][iface]
            naive_vals = _shaping_values(
                naive_smoothed, [_weight(s) for s in naive_smoothed], tier
            )
            if any(entries[iface][k] != naive_vals[k] for k in naive_vals):
                diverged += 1
        assert diverged >= 4, (naive_key, diverged)


def test_row_count_covers_registry():
    """row_count counts every ledger row of every registry interface, active and detached."""
    ref = _reference()
    manifest = _manifest()
    assert manifest["row_count"] == len(ref["rows"])
    detached_rows = sum(
        len(ref["smoothed"][iface]) for iface, d in ref["detached"].items() if d
    )
    assert detached_rows > 0
    assert manifest["row_count"] > detached_rows


def test_seal_matches():
    """The manifest seal equals the chain replayed over every recomputed ledger row."""
    ref = _reference()
    manifest = _manifest()
    assert manifest["seal"] == ref["seal"]


def test_seal_is_coupled_to_values():
    """The delivered seal tracks the full-chain reading and diverges from every naive variant of it."""
    ref = _reference()
    rows = ref["rows"]
    submitted = _manifest()["seal"]
    assert submitted == "%016x" % _seal_chain(rows, "pre")
    assert "%016x" % _seal_chain(rows, "mid") != submitted
    active_rows = [r for r in rows if not ref["detached"][ref["registry_order"][r[0]]]]
    assert "%016x" % _seal_chain(active_rows, "pre") != submitted
    perturbed = list(rows)
    pos, day, s_val, w_val = perturbed[len(perturbed) // 2]
    perturbed[len(perturbed) // 2] = (pos, day, s_val + 1, w_val)
    assert "%016x" % _seal_chain(perturbed, "pre") != submitted
    by_name = sorted(range(len(ref["registry_order"])), key=lambda i: ref["registry_order"][i])
    sorted_rows = []
    for i in by_name:
        iface = ref["registry_order"][i]
        for day, s_val in enumerate(ref["smoothed"][iface]):
            sorted_rows.append((i, day, s_val, ref["weights"][iface][day]))
    assert "%016x" % _seal_chain(sorted_rows, "pre") != submitted


def test_shaping_fetched_from_live_api():
    """The API access log shows a shaping fetch for every registry interface before verification began."""
    ref = _reference()
    with open(SNAPSHOT_PATH) as f:
        log = f.read()
    for iface in ref["registry_order"]:
        assert "GET /shaping/" + iface in log, iface


def test_reprovision_is_idempotent():
    """Running the provisioner again changes no account, file bytes, ownership or mode."""
    ref = _reference()

    def state():
        digest = hashlib.sha256()
        for iface in _active_ids(ref):
            for path in (
                "/etc/systemd/network/40-" + iface + ".network",
                "/etc/link-rate.d/" + iface + ".env",
            ):
                with open(path, "rb") as f:
                    digest.update(path.encode() + b"\0" + f.read() + b"\0")
            st = os.stat(STATE_BASE + "/" + iface)
            digest.update(
                ("%s %d %d %o" % (iface, st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode))).encode()
            )
            user = pwd.getpwnam(iface)
            digest.update(("%d %s %s" % (user.pw_uid, user.pw_shell, user.pw_dir)).encode())
        for path in (MANIFEST_PATH, SEAL_PATH):
            with open(path, "rb") as f:
                digest.update(f.read())
        return digest.hexdigest()

    before = state()
    result = subprocess.run(
        [TOOL_PATH], capture_output=True, text=True, timeout=300
    )
    assert result.returncode == 0, result.stderr
    assert state() == before
