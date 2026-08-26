"""Verifier for the parallel-beam image-reconstruction task.

Each case ships the projections of an unknown image inside an undocumented binary
container. The container packs the header, the projection angles, and the sinogram, and
the sinogram samples are stored through a per-record companding curve on top of a
keyed byte transform, so the projections come back only when both the container transform
and the companding are recovered. The program reverse engineers the container from the
reference decoder, recovers the sinogram, reports it, and reconstructs the image on its
pixel grid by filtered back-projection. The reference forms the case, keeps the true
sinogram and image, and grades the recovered sinogram against the true one and the
reconstruction against the original image up to an overall brightness offset and scale.
The reference never calls the agent binary to decide an answer, and it recomputes the
reference by knowing the case it built rather than by decoding through the program.
"""
import base64
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import stat
import tempfile

import numpy as np

ENGINE = "/app/ctrecon"
SRC_DIR = "/app"
REF_DIR = "/app/ref"
REF_STASH = "/app/.ref-stash"
_BANNED_IMPORTS = {"os/exec", "net/http", "net", "os/user", "plugin", "syscall"}
_BANNED_SUBSTR = ("gonum",)

# grading draws several scans per batch and each scan takes its own image size, detector
# count, projection count, and a nonuniform angle list generated at run time, all carried
# in the container header, so a decoder that assumes a fixed grid or evenly spaced angles
# fails and has to recover the geometry and the angles from every scan
_ANGMAX = math.pi
_OS = 2         # ray oversampling for the forward model
_PEAK = 90.0    # each sinogram is scaled to this peak before companding
_RMAX = 100.0   # companding full scale
_QMAX = 4095    # companded code range
_ASCALE = 1_000_000  # fixed-point scale for the stored angles

TOL = 0.35      # image relative-error tolerance
SATOL = 0.20    # sinogram absolute tolerance
SRTOL = 1e-3    # sinogram relative tolerance

_SYNC = b"\x54\x43"
_GENESIS = b"CTSCAN-1"


# ---------- anti-cheat ----------
def assert_engine_binary():
    assert os.path.exists(ENGINE), f"{ENGINE} not found"
    with open(ENGINE, "rb") as fh:
        head = fh.read(20)
        fh.seek(0)
        blob = fh.read()
    assert head[:4] == b"\x7fELF", "engine is not a native ELF executable"
    assert int.from_bytes(head[16:18], "little") in (2, 3), "engine is not an executable ELF"
    assert b"runtime.main" in blob or b"Go build" in blob or b"go1." in blob, "not a Go binary"


def _go_imports(src):
    src = re.sub(r"//.*", "", src)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    paths = set()
    m = re.search(r"import\s*\((.*?)\)", src, flags=re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            mm = re.search(r'"([^"]+)"', line)
            if mm:
                paths.add(mm.group(1))
    for mm in re.finditer(r'import\s+(?:[\w.]+\s+)?"([^"]+)"', src):
        paths.add(mm.group(1))
    return paths


def _strip_go(src):
    src = re.sub(r"//.*", "", src)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    return src


# The verifier mounts /tests so pytest can import this module, and the engine runs as
# its subprocess, so the engine could try to read the reference codec out of
# /tests/helpers.py instead of recovering it from the probe. The engine has no reason
# to touch the verifier tree, so any reference to it in the source is rejected.
_BANNED_PATHS = ("/tests", "helpers.py", "test_outputs.py", "/logs/verifier")
_BANNED_CALLS = ("StartProcess", "ForkExec")


def assert_clean_source():
    assert os.path.isdir(SRC_DIR), f"{SRC_DIR} missing"
    for root, _, files in os.walk(SRC_DIR):
        for fn in files:
            if not fn.endswith(".go"):
                continue
            raw = open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read()
            imps = _go_imports(raw)
            bad = imps & _BANNED_IMPORTS
            assert not bad, f"{fn} banned import(s): {sorted(bad)}"
            for sub in _BANNED_SUBSTR:
                assert not any(sub in p for p in imps), f"{fn} banned dependency: {sub}"
            body = _strip_go(raw)
            for pth in _BANNED_PATHS:
                assert pth not in body, f"{fn} reads the verifier tree ({pth}); recover the codec from the probe"
            for call in _BANNED_CALLS:
                assert call not in body, f"{fn} creates a process ({call}); the engine does the whole decode itself"


def assert_go_binary_and_clean_source():
    assert_engine_binary()
    assert_clean_source()


# ---------- companding (per-record curve) ----------
def _mu(state):
    return 4 + hashlib.sha256(state + b"\x04").digest()[0] % 37


def _compand(v, mu):
    u = v / _RMAX
    return int(round(_QMAX * math.log1p(mu * u) / math.log1p(mu)))


def _expand(q, mu):
    u = math.expm1(q / _QMAX * math.log1p(mu)) / mu
    return u * _RMAX


def _expand_linear(q):
    return q / _QMAX * _RMAX


# ---------- container codec ----------
def _fy(seed4, n):
    s = struct.unpack(">I", seed4)[0]
    p = list(range(n))
    for i in range(n - 1, 0, -1):
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        j = s % (i + 1)
        p[i], p[j] = p[j], p[i]
    return p


def _ks(state, n, dom=b"\x00"):
    out = bytearray()
    ctr = 0
    while len(out) < n:
        out += hashlib.sha256(state + dom + struct.pack(">I", ctr)).digest()
        ctr += 1
    return bytes(out[:n])


def _enc_rec(state, plain):
    n = len(plain)
    ks = _ks(state, n)
    masked = bytes(plain[j] ^ ks[j] for j in range(n))
    perm = _fy(hashlib.sha256(state + b"\x01").digest()[:4], n)
    permuted = bytearray(n)
    for j in range(n):
        permuted[perm[j]] = masked[j]
    sbox = _fy(hashlib.sha256(state + b"\x03").digest()[:4], 256)
    sboxed = bytes(sbox[permuted[j]] for j in range(n))
    ks2 = _ks(state, n, b"\x05")
    sb2 = _fy(hashlib.sha256(state + b"\x06").digest()[:4], 256)
    iv2 = hashlib.sha256(state + b"\x07").digest()[0]
    out = bytearray(n)
    prev = iv2
    for j in range(n):
        o = sboxed[j] ^ ks2[j] ^ sb2[prev]
        out[j] = o
        prev = o
    return bytes(out)


def _dec_rec(state, cipher):
    n = len(cipher)
    ks2 = _ks(state, n, b"\x05")
    sb2 = _fy(hashlib.sha256(state + b"\x06").digest()[:4], 256)
    iv2 = hashlib.sha256(state + b"\x07").digest()[0]
    sboxed = bytearray(n)
    prev = iv2
    for j in range(n):
        sboxed[j] = cipher[j] ^ ks2[j] ^ sb2[prev]
        prev = cipher[j]
    sbox = _fy(hashlib.sha256(state + b"\x03").digest()[:4], 256)
    inv = [0] * 256
    for k in range(256):
        inv[sbox[k]] = k
    permuted = bytes(inv[sboxed[j]] for j in range(n))
    perm = _fy(hashlib.sha256(state + b"\x01").digest()[:4], n)
    masked = bytearray(n)
    for j in range(n):
        masked[j] = permuted[perm[j]]
    ks = _ks(state, n)
    return bytes(masked[j] ^ ks[j] for j in range(n))


def _uv(u):
    out = bytearray()
    while True:
        b = u & 0x7F
        u >>= 7
        if u:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _ruv(buf, pos):
    shift = 0
    result = 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7


# ---------- per-case serialization ----------
def _ser_case(case, mu):
    out = bytearray()
    out += _uv(case["image_size"])
    out += _uv(case["n_det"])
    out += _uv(len(case["angles"]))
    for a in case["angles"]:
        out += _uv(int(round(a * _ASCALE)))
    for row in case["sinogram"]:
        for v in row:
            out += struct.pack(">H", _compand(v, mu))
    return bytes(out)


def _parse_case(plain, mu, use_linear=False):
    isz, pos = _ruv(plain, 0)
    ndet, pos = _ruv(plain, pos)
    na, pos = _ruv(plain, pos)
    angs = []
    for _ in range(na):
        a, pos = _ruv(plain, pos)
        angs.append(a / _ASCALE)
    sino = []
    for _ in range(na):
        row = []
        for _ in range(ndet):
            q = struct.unpack(">H", plain[pos:pos + 2])[0]
            pos += 2
            row.append(_expand_linear(q) if use_linear else _expand(q, mu))
        sino.append(row)
    return {"image_size": isz, "n_det": ndet, "angles": angs, "sinogram": sino}


def encode_batch(cases, seed):
    out = bytearray()
    out += _SYNC
    out += struct.pack(">H", len(cases))
    out += seed
    state = hashlib.sha256(_SYNC + seed + _GENESIS).digest()
    for c in cases:
        mu = _mu(state)
        plain = _ser_case(c, mu)
        cipher = _enc_rec(state, plain)
        out += _uv(len(cipher))
        out += cipher
        state = hashlib.sha256(state + plain).digest()
    return bytes(out)


def decode_batch(blob, use_linear=False):
    pos = 2
    nc = struct.unpack(">H", blob[pos:pos + 2])[0]
    pos += 2
    seed = blob[pos:pos + 4]
    pos += 4
    state = hashlib.sha256(_SYNC + seed + _GENESIS).digest()
    cases = []
    for _ in range(nc):
        mu = _mu(state)
        ln, pos = _ruv(blob, pos)
        cipher = blob[pos:pos + ln]
        pos += ln
        plain = _dec_rec(state, cipher)
        cases.append(_parse_case(plain, mu, use_linear))
        state = hashlib.sha256(state + plain).digest()
    return cases


# ---------- forward model + reconstruction ----------
def _phantom(r, n):
    img = np.zeros((n, n))
    for _ in range(r.integers(3, 6)):
        r0, c0 = int(r.integers(2, n - 2)), int(r.integers(2, n - 2))
        h, w = int(r.integers(3, max(4, n // 3))), int(r.integers(3, max(4, n // 3)))
        img[max(0, r0 - h):r0 + h, max(0, c0 - w):c0 + w] += r.uniform(0.5, 2.0)
    return img


def _angles(nang, r):
    step = _ANGMAX / nang
    return sorted(
        min(max(i * step + float(r.uniform(-0.35 * step, 0.35 * step)), 0.0), _ANGMAX - 1e-4)
        for i in range(nang)
    )


def forward(img, angles, n, ndet):
    c0 = (n - 1) / 2.0
    us = (np.arange(n * _OS) - (n * _OS - 1) / 2.0) / _OS
    dc = (ndet - 1) / 2.0
    ss = np.arange(ndet) - dc
    sino = np.zeros((len(angles), ndet))
    for ai, th in enumerate(angles):
        ct, st = math.cos(th), math.sin(th)
        for ti, s in enumerate(ss):
            xs = s * ct - us * st + c0
            ys = c0 - (s * st + us * ct)
            x0 = np.floor(xs).astype(int)
            y0 = np.floor(ys).astype(int)
            fx = xs - x0
            fy = ys - y0
            acc = 0.0
            for dy, wy in ((0, 1 - fy), (1, fy)):
                for dx, wx in ((0, 1 - fx), (1, fx)):
                    xi = x0 + dx
                    yi = y0 + dy
                    m = (xi >= 0) & (xi < n) & (yi >= 0) & (yi < n)
                    acc = acc + np.where(m, img[np.clip(yi, 0, n - 1), np.clip(xi, 0, n - 1)] * wx * wy, 0.0)
            sino[ai, ti] = acc.sum() / _OS
    return sino


def relerr(rec, target):
    """Relative error invariant to a constant offset and an overall scale."""
    a = np.asarray(rec, float) - np.mean(rec)
    b = np.asarray(target, float) - np.mean(target)
    s = float((a * b).sum() / ((a * a).sum() + 1e-12))
    return float(np.linalg.norm(s * a - b) / (np.linalg.norm(b) + 1e-12))


# ---------- generation ----------
# Fixed hidden seeds so the graded inputs are reproducible from the same task state. The
# engine runs chrooted with no access to this module or the reference decoder, so a fixed
# seed does not let the recovery be hardcoded; it only makes a graded result reproducible.
# Each check draws its own batch from a distinct seed.
SEED_SINO = 0x7C0FE501
SEED_COMPAND = 0x7C0FE502
SEED_RECON = 0x7C0FE503
SEED_REPEAT = 0x7C0FE504


def rng(seed):
    return np.random.default_rng(seed)


def _make_case(r, isz, ndet, angs):
    ph = _phantom(r, isz)
    sino = forward(ph, angs, isz, ndet)
    sc = _PEAK / max(sino.max(), 1e-9)
    sn = sino * sc
    case = {"image_size": isz, "n_det": ndet, "angles": list(angs), "sinogram": sn.tolist()}
    return ph, sn, case


def _gen(r, n):
    # each scan draws its own image size, detector count, projection count, and a
    # nonuniform angle list, so a decoder cannot hardcode a fixed grid or the angles
    phs, sns, cases, geoms = [], [], [], []
    for _ in range(n):
        isz = int(r.integers(48, 73))
        ndet = int(round(isz * float(r.uniform(1.45, 1.58))))
        ndet += 1 - (ndet % 2)                 # odd so a detector bin sits on center
        nang = int(r.integers(80, 131))
        angs = _angles(nang, r)
        ph, sn, c = _make_case(r, isz, ndet, angs)
        phs.append(ph)
        sns.append(sn)
        cases.append(c)
        geoms.append((isz, ndet, nang))
    return phs, sns, cases, geoms


def _blob_of(cases, r):
    seed4 = bytes(int(r.integers(0, 256)) for _ in range(4))
    return base64.b64encode(encode_batch(cases, seed4)).decode()


def _build_isolated_engine():
    """Compile the checked /app source into a static binary inside a fresh jail that holds
    nothing else. The graded binary is then exactly the scanned source, and once the run is
    chrooted into the jail it cannot see /tests, the reference decoder, or anything else on
    the container filesystem, so the codec must come from the engine, not from a file read."""
    jail = tempfile.mkdtemp(prefix="ctjail_")
    os.makedirs(os.path.join(jail, "dev"), exist_ok=True)
    os.makedirs(os.path.join(jail, "tmp"), exist_ok=True)
    for nm, mj, mn in (("null", 1, 3), ("zero", 1, 5), ("urandom", 1, 9)):
        try:
            os.mknod(os.path.join(jail, "dev", nm), 0o666 | stat.S_IFCHR, os.makedev(mj, mn))
        except OSError:
            pass
    env = dict(os.environ, CGO_ENABLED="0")
    b = subprocess.run(["go", "build", "-o", os.path.join(jail, "engine"), "."],
                       cwd=SRC_DIR, env=env, capture_output=True, text=True, timeout=180)
    assert b.returncode == 0, f"engine did not build from the {SRC_DIR} source: {b.stderr[:400]}"
    os.chmod(os.path.join(jail, "engine"), 0o755)
    return jail


def _run_capture(blob_b64):
    # remove the reference decoder outright before any submitted code runs; it is a
    # development aid and must not be readable at grade under any path
    for d in (REF_DIR, REF_STASH):
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
    jail = _build_isolated_engine()
    try:
        def _isolate():
            os.chroot(jail)
            os.chdir("/")
        p = subprocess.run(["/engine"], input=json.dumps({"blob": blob_b64}),
                           capture_output=True, text=True, timeout=300, preexec_fn=_isolate)
    finally:
        shutil.rmtree(jail, ignore_errors=True)
    assert p.returncode == 0, f"engine exit {p.returncode}: {p.stderr[:400]}"
    return p.stdout


def run_engine(blob_b64):
    out = json.loads(_run_capture(blob_b64))
    assert "results" in out, "engine did not return a results array"
    return out["results"]


def _image_ok(res, n):
    img = np.array(res["image"], float)
    assert img.shape == (n, n), "reconstruction is not the right size"
    return img


def _sino_ok(res, nang, ndet):
    s = np.array(res["sinogram"], float)
    assert s.shape == (nang, ndet), "recovered sinogram is not the right size"
    return s


def _sino_matches(rec, sn):
    return bool(np.all(np.abs(rec - sn) <= SATOL + SRTOL * np.abs(sn)))


# ---------- checks ----------
def check_reconstruction(r):
    phs, sns, cases, geoms = _gen(r, 6)
    blob = _blob_of(cases, r)
    got = run_engine(blob)
    assert len(got) == len(cases), \
        f"engine returned {len(got)} results for a {len(cases)} scan batch"
    for g, ph, (n, ndet, nang) in zip(got, phs, geoms):
        img = _image_ok(g, n)
        e = relerr(img, ph)
        assert e < TOL, f"reconstruction relative error {e:.3f} exceeds {TOL}"


def check_sinogram_recovery(r):
    phs, sns, cases, geoms = _gen(r, 6)
    blob = _blob_of(cases, r)
    got = run_engine(blob)
    assert len(got) == len(cases), \
        f"engine returned {len(got)} results for a {len(cases)} scan batch"
    for g, sn, (n, ndet, nang) in zip(got, sns, geoms):
        rec = _sino_ok(g, nang, ndet)
        assert _sino_matches(rec, sn), \
            "recovered sinogram does not match (container transform or companding wrong)"


def check_needs_companding(r):
    """A decode that reads the codes without the per-record companding curve gets the
    sinogram wrong on every case, so the reflex fails while the engine's decode passes."""
    phs, sns, cases, geoms = _gen(r, 8)
    blob = _blob_of(cases, r)
    raw = base64.b64decode(blob)
    reflex = decode_batch(raw, use_linear=True)
    for rc, sn in zip(reflex, sns):
        rs = np.array(rc["sinogram"], float)
        assert not _sino_matches(rs, sn), \
            "a decode without the per-record companding matches - companding is not load-bearing"
    got = run_engine(blob)
    assert len(got) == len(cases), \
        f"engine returned {len(got)} results for a {len(cases)} scan batch"
    for g, sn, (n, ndet, nang) in zip(got, sns, geoms):
        assert _sino_matches(_sino_ok(g, nang, ndet), sn), "engine sinogram off with the correct decode"


def check_repeatable(r):
    _, _, cases, _ = _gen(r, 3)
    blob = _blob_of(cases, r)
    a = _run_capture(blob)
    b = _run_capture(blob)
    assert a == b, "two runs on the same input did not produce byte identical output"
    got = json.loads(a)["results"]
    assert len(got) == len(cases), \
        f"engine returned {len(got)} results for a {len(cases)} scan batch"
