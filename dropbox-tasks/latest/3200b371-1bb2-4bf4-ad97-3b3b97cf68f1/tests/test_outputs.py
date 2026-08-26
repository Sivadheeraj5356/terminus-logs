"""Domain checks for offline annex policy-pack closure."""

import json
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
OUT = Path("/app/output/policy_pack")
ROT = ENV / "data" / "rot_tbl.toml"
SUM = ENV / "data" / "fix_stash" / "sum_tbl.tsv"
CORPUS = ENV / "data" / "corpus"


def sha16_stream(data: bytes) -> str:
    tool = "sha256" + "sum"
    proc = subprocess.run(
        [tool],
        input=data,
        capture_output=True,
        check=True,
    )
    return proc.stdout.decode().split()[0][:16]


def sha8_text(s: str) -> str:
    return sha16_stream(bytes(s, "utf-8"))[:8]


def load_sums() -> dict[str, int]:
    out: dict[str, int] = {}
    for ln in SUM.read_text(encoding="utf-8").splitlines()[1:]:
        if not ln.strip():
            continue
        sid, val, _ = ln.split("\t")
        out[sid] = int(val)
    return out


def load_rot_rows() -> list[dict]:
    rows: list[dict] = []
    cur: dict | None = None
    for ln in ROT.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln == "[[row]]":
            if cur:
                rows.append(cur)
            cur = {}
            continue
        if cur is None or not ln or ln.startswith("#"):
            continue
        if ln.startswith("id = "):
            cur["id"] = ln.split("=", 1)[1].strip().strip('"')
        elif ln.startswith("corpus = "):
            cur["corpus"] = ln.split("=", 1)[1].strip().strip('"')
        elif ln.startswith("lane = "):
            cur["lane"] = ln.split("=", 1)[1].strip().strip('"')
        elif ln.startswith("step = "):
            cur["step"] = int(ln.split("=", 1)[1].strip())
    if cur:
        rows.append(cur)
    return rows


def preamble_peers(sid: str) -> list[str]:
    """Only PEER lines before the first ';' comment are lock peers."""
    path = CORPUS / f"{sid}_blob.dbc"
    found: list[str] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if ln.startswith(";"):
            break
        if ln.startswith("PEER "):
            found.append(ln.split()[1])
    return found


def all_peers(sid: str) -> list[str]:
    path = CORPUS / f"{sid}_blob.dbc"
    found: list[str] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if ln.startswith("PEER "):
            found.append(ln.split()[1])
    return found


def expected_edges(corpus: str) -> list[tuple[str, str]]:
    active = corpus.split(",")
    aset = set(active)
    edges: list[tuple[str, str]] = []
    for src in active:
        for dst in preamble_peers(src):
            if dst in aset:
                edges.append((src, dst))
    return edges


def polluted_edges(corpus: str) -> list[tuple[str, str]]:
    """Wrong reading: honor every PEER line in the blob."""
    active = corpus.split(",")
    aset = set(active)
    edges: list[tuple[str, str]] = []
    for src in active:
        for dst in all_peers(src):
            if dst in aset:
                edges.append((src, dst))
    return edges


def band_for(S: int, step: int) -> tuple[int, int]:
    lo = (S + step) % 13
    hi = lo + (S % 17) + 3
    return lo, hi


def byte_sum(s: str) -> int:
    return sum(s.encode("utf-8"))


def pin_seed_for(corpus: str, step: int, sums: dict[str, int]) -> str:
    lines = []
    for sid in sorted(corpus.split(",")):
        lo, _ = band_for(sums[sid], step)
        lines.append(f"{sid}|{lo}\n")
    return sha8_text("".join(lines))


def expected_rows() -> list[dict]:
    sums = load_sums()
    rows: list[dict] = []
    for rot in load_rot_rows():
        pin = pin_seed_for(rot["corpus"], rot["step"], sums)
        for src, dst in expected_edges(rot["corpus"]):
            lo, hi = band_for(sums[src], rot["step"])
            tok = sha8_text(f"t|{src}|{dst}|{lo}|{pin}")
            asv = (byte_sum(src) + lo) % 64
            rows.append(
                {
                    "rotation_id": rot["id"],
                    "slice_id": src,
                    "peer": dst,
                    "tok": tok,
                    "asv": asv,
                    "band_lo": lo,
                    "band_hi": hi,
                }
            )
    return rows


def expected_prov(rows: list[dict]) -> str:
    ordered = sorted(
        rows, key=lambda r: (r["rotation_id"], r["slice_id"], r["peer"])
    )
    blob = "".join(f"{r['tok']}|{r['asv']}\n" for r in ordered)
    return sha16_stream(blob.encode())


def expected_ledger() -> list[dict]:
    sums = load_sums()
    out = []
    for rot in load_rot_rows():
        tot = sum(sums[s] for s in rot["corpus"].split(","))
        out.append({"rotation_id": rot["id"], "tot": tot})
    return out


def rebuild() -> None:
    last = None
    for _ in range(3):
        last = subprocess.run(
            ["/app/environment/h7p/pp_run", "rebuild"],
            capture_output=True,
            text=True,
        )
        if last.returncode == 0:
            return
        if last.returncode != 141:
            break
    assert last is not None
    raise subprocess.CalledProcessError(
        last.returncode, last.args, output=last.stdout, stderr=last.stderr
    )


def read_pack() -> dict:
    return json.loads((OUT / "pack.json").read_text(encoding="utf-8"))


def read_rows_tsv() -> list[dict]:
    lines = (OUT / "rows.tsv").read_text(encoding="utf-8").splitlines()
    assert lines and lines[0].startswith("rotation_id")
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        p = ln.split("\t")
        rows.append(
            {
                "rotation_id": p[0],
                "slice_id": p[1],
                "peer": p[2],
                "tok": p[3],
                "asv": int(p[4]),
                "band_lo": int(p[5]),
                "band_hi": int(p[6]),
            }
        )
    return rows


@pytest.fixture(scope="module", autouse=True)
def _module_rebuild():
    rebuild()
    yield


def test_a7_rx_grid():
    """Pack row schema/layout after rebuild (bands + pins + edges coupled)."""
    pack = read_pack()
    assert pack["schema"] == "row_v3"
    assert (OUT / "rows.tsv").exists()
    assert (OUT / "lock.tsv").exists()
    assert (OUT / "prov.sha").exists()
    assert (OUT / "ledger.sum").exists()
    exp = expected_rows()
    got = pack["rows"]
    assert len(got) == len(exp)

    def key(r):
        return (r["rotation_id"], r["slice_id"], r["peer"])

    assert sorted(got, key=key) == sorted(exp, key=key)
    for r in got:
        assert len(r["tok"]) == 8
        for c in r["tok"]:
            o = ord(c)
            assert (48 <= o <= 57) or (97 <= o <= 102)
        assert 0 <= r["asv"] <= 63


def test_b3_kv_fold():
    """Idempotent consecutive rebuild digest equality."""
    rebuild()
    a = (OUT / "prov.sha").read_text(encoding="utf-8")
    a_rows = (OUT / "rows.tsv").read_bytes()
    rebuild()
    b = (OUT / "prov.sha").read_text(encoding="utf-8")
    b_rows = (OUT / "rows.tsv").read_bytes()
    assert a == b
    assert a_rows == b_rows
    assert a.strip() == expected_prov(expected_rows())


def test_c9_mx_knit():
    """Preamble mux join is closed; calibration-body PEER must not pollute."""
    pack = read_pack()
    by_rot: dict[str, set[tuple[str, str]]] = {}
    for r in pack["rows"]:
        rid = r["rotation_id"]
        bucket = by_rot.get(rid)
        if bucket is None:
            bucket = set()
            by_rot[rid] = bucket
        bucket.add((r["slice_id"], r["peer"]))
    for rot in load_rot_rows():
        want = set(expected_edges(rot["corpus"]))
        polluted = set(polluted_edges(rot["corpus"]))
        got = by_rot.get(rot["id"], set())
        assert got == want
        # partial fix that keeps all PEER lines fails here when pollution exists
        if polluted != want:
            assert got != polluted


def test_d2_nl_span():
    """Aggregate totals cannot mask missing or polluted row pins."""
    pack = read_pack()
    led = {e["rotation_id"]: e["tot"] for e in pack["ledger"]}
    for e in expected_ledger():
        assert led[e["rotation_id"]] == e["tot"]
    assert len(pack["rows"]) == len(expected_rows())
    assert len(pack["rows"]) > len(pack["ledger"])
    # polluted cardinality must differ on at least one base rotation
    base = next(r for r in load_rot_rows() if r["lane"] == "base")
    assert len(expected_edges(base["corpus"])) < len(polluted_edges(base["corpus"]))


def test_e5_qp_held():
    """Threshold band span contracts with step fold (held-sensitive)."""
    sums = load_sums()
    rot_by_id = {r["id"]: r for r in load_rot_rows()}
    for r in read_rows_tsv():
        rot = rot_by_id[r["rotation_id"]]
        lo, hi = band_for(sums[r["slice_id"]], rot["step"])
        assert r["band_lo"] == lo
        assert r["band_hi"] == hi
        assert (r["band_hi"] - r["band_lo"]) == (sums[r["slice_id"]] % 17) + 3
    # near-miss without step must disagree on a held rotation
    held = next(r for r in load_rot_rows() if r["lane"] == "held" and r["step"] > 0)
    sid = held["corpus"].split(",")[0]
    naive_lo = sums[sid] % 13
    closed_lo = band_for(sums[sid], held["step"])[0]
    assert naive_lo != closed_lo
    matched = [
        r
        for r in read_rows_tsv()
        if r["rotation_id"] == held["id"] and r["slice_id"] == sid
    ]
    assert matched
    assert matched[0]["band_lo"] == closed_lo


def test_f1_hr_pin():
    """Held-out rotations: bands, preamble edges, and pin-coupled toks agree."""
    pack = read_pack()
    sums = load_sums()
    held = [r for r in load_rot_rows() if r["lane"] == "held"]
    assert held
    for rot in held:
        pin = pin_seed_for(rot["corpus"], rot["step"], sums)
        want = expected_edges(rot["corpus"])
        assert want, rot["id"]
        got = [
            r for r in pack["rows"] if r["rotation_id"] == rot["id"]
        ]
        assert sorted((r["slice_id"], r["peer"]) for r in got) == sorted(want)
        for r in got:
            lo, hi = band_for(sums[r["slice_id"]], rot["step"])
            assert r["band_lo"] == lo
            assert r["band_hi"] == hi
            assert r["tok"] == sha8_text(
                f"t|{r['slice_id']}|{r['peer']}|{lo}|{pin}"
            )
            assert r["asv"] == (byte_sum(r["slice_id"]) + lo) % 64


def test_g8_mw_seal():
    """Provenance seal derives from pin-coupled rows, not aggregate alone."""
    pack = read_pack()
    prov_file = (OUT / "prov.sha").read_text(encoding="utf-8").strip()
    assert pack["prov"] == prov_file
    assert prov_file == expected_prov(expected_rows())
    assert pack["rows"]
    led_input = "\n".join((OUT / "ledger.sum").read_text().splitlines()[1:]) + "\n"
    led_only = sha16_stream(bytes(led_input, "utf-8"))
    assert prov_file != led_only
    assert prov_file == expected_prov(read_rows_tsv())


def test_h4_xt_sum():
    """Sum perturbation updates bands, pin_seed, and toks together."""
    backup = SUM.read_text(encoding="utf-8")
    probe = next(iter(load_sums()))
    try:
        lines = backup.splitlines()
        out_lines = []
        for ln in lines:
            if ln.startswith(probe + "\t"):
                parts = ln.split("\t")
                parts[1] = str(int(parts[1]) + 13)
                out_lines.append("\t".join(parts))
            else:
                out_lines.append(ln)
        SUM.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        rebuild()
        sums = load_sums()
        rot = next(r for r in load_rot_rows() if probe in r["corpus"].split(","))
        lo, hi = band_for(sums[probe], rot["step"])
        pin = pin_seed_for(rot["corpus"], rot["step"], sums)
        matched = [
            r
            for r in read_rows_tsv()
            if r["rotation_id"] == rot["id"] and r["slice_id"] == probe
        ]
        assert matched
        for r in matched:
            assert r["band_lo"] == lo
            assert r["band_hi"] == hi
            assert r["tok"] == sha8_text(
                f"t|{r['slice_id']}|{r['peer']}|{lo}|{pin}"
            )
            assert r["asv"] == (byte_sum(r["slice_id"]) + lo) % 64
    finally:
        SUM.write_text(backup, encoding="utf-8")
        rebuild()


def test_i6_yz_peer():
    """New preamble PEER appears; body-only PEER must stay excluded."""
    blob = CORPUS / "j1_blob.dbc"
    backup = blob.read_text(encoding="utf-8")
    peer_line = "PEER " + "j4" + "\n"
    try:
        # insert preamble peer before first ';'
        if peer_line not in backup.split(";")[0]:
            blob.write_text(
                backup.replace("PEER " + "j2" + "\n", "PEER " + "j2" + "\n" + peer_line, 1),
                encoding="utf-8",
            )
        rebuild()
        pack = read_pack()
        base_id = next(r["id"] for r in load_rot_rows() if r["lane"] == "base")
        edges = {
            (r["slice_id"], r["peer"])
            for r in pack["rows"]
            if r["rotation_id"] == base_id
        }
        assert ("j1", "j4") in edges
        # ensure a known body pollution peer is still absent if only in body
        body_only = set(all_peers("j1")) - set(preamble_peers("j1"))
        for dst in body_only:
            if dst in {"j1", "j2", "j3", "j4"}:
                # after our insert, j4 may be preamble; skip those now preamble
                if dst in preamble_peers("j1"):
                    continue
                assert ("j1", dst) not in edges
    finally:
        blob.write_text(backup, encoding="utf-8")
        rebuild()


def test_j0_zv_dual():
    """tok includes pin_seed; asv must not (dual-key partial-fix catch)."""
    rows = read_rows_tsv()
    assert rows
    sums = load_sums()
    rot_by_id = {r["id"]: r for r in load_rot_rows()}
    diverse = False
    by_rot: dict[str, list] = {}
    for r in rows:
        rid = r["rotation_id"]
        grp = by_rot.get(rid)
        if grp is None:
            grp = []
            by_rot[rid] = grp
        grp.append(r)
    for grp in by_rot.values():
        toks = {r["tok"] for r in grp}
        if len(grp) >= 2 and len(toks) >= 2:
            diverse = True
            break
    assert diverse
    for r in rows:
        rot = rot_by_id[r["rotation_id"]]
        pin = pin_seed_for(rot["corpus"], rot["step"], sums)
        lo = r["band_lo"]
        assert r["tok"] == sha8_text(
            f"t|{r['slice_id']}|{r['peer']}|{lo}|{pin}"
        )
        assert r["asv"] == (byte_sum(r["slice_id"]) + lo) % 64
        # near-miss: folding pin into asv
        wrong_asv = (byte_sum(r["slice_id"]) + lo + len(pin)) % 64
        if wrong_asv != r["asv"]:
            assert r["asv"] != wrong_asv


def test_k3_vw_prov():
    """Provenance moves when preamble edges change; ledger hand-edit is ignored."""
    rebuild()
    base = (OUT / "prov.sha").read_text(encoding="utf-8").strip()
    led_backup = (OUT / "ledger.sum").read_text(encoding="utf-8")
    junk = "ex" + "tra" + "\t" + "0" + "\n"
    (OUT / "ledger.sum").write_text(led_backup + junk, encoding="utf-8")
    assert (OUT / "prov.sha").read_text(encoding="utf-8").strip() == base
    assert base == expected_prov(read_rows_tsv())
    (OUT / "ledger.sum").write_text(led_backup, encoding="utf-8")

    blob = CORPUS / "j2_blob.dbc"
    backup = blob.read_text(encoding="utf-8")
    try:
        blob.write_text(
            backup.replace(
                "PEER " + "j1" + "\n",
                "PEER " + "j1" + "\n" + "PEER " + "j3" + "\n",
                1,
            ),
            encoding="utf-8",
        )
        rebuild()
        nxt = (OUT / "prov.sha").read_text(encoding="utf-8").strip()
        assert nxt != base
        assert nxt == expected_prov(read_rows_tsv())
        # toks must reflect new pin_seed if bands unchanged but edge set grew
        assert nxt == expected_prov(expected_rows())
    finally:
        blob.write_text(backup, encoding="utf-8")
        rebuild()


def test_l7_tp_smoke():
    """Smoke health green while seal, preamble edges, and step bands must hold."""
    health = subprocess.run(
        ["/app/h7p/pp_run", "health"], capture_output=True, text=True
    )
    assert health.returncode == 0
    assert "ok" in health.stdout
    pack = read_pack()
    assert pack["prov"] == expected_prov(pack["rows"])
    assert len(pack["rows"]) == len(expected_rows())
    # compound: at least one held row disagrees with step-naive bands
    sums = load_sums()
    held = next(r for r in load_rot_rows() if r["step"] > 0)
    sid = held["corpus"].split(",")[0]
    row = next(
        r
        for r in pack["rows"]
        if r["rotation_id"] == held["id"] and r["slice_id"] == sid
    )
    closed_lo = band_for(sums[sid], held["step"])[0]
    naive_lo = sums[sid] % 13
    assert row["band_lo"] == closed_lo
    assert closed_lo != naive_lo
