"""Behavioral checks for the Asterism Color deterministic release forge."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont

APP = Path("/app")
DIST = APP / "out" / "colr-crate"
BUILD = APP / "forgectl"
PROFILE = APP / "asterism-ledger" / "release.toml"
FONTSRC = APP / "foundry-sources"
SPEC = APP / "asterism-spec" / "RELEASE_CONTRACT.md"
PROOF = APP / "proof-strings"
LEDGER_DIR = APP / "asterism-ledger"


def _run(exe: str | list[str], *args: str, **kwargs) -> subprocess.CompletedProcess[str]:
    if isinstance(exe, list):
        argv_list = [str(x) for x in exe]
    else:
        argv_list = [exe, *args]
    proc = subprocess.Popen(
        argv_list,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **{k: v for k, v in kwargs.items() if k in {"cwd", "env"}},
    )
    stdout, stderr = proc.communicate()
    return subprocess.CompletedProcess(argv_list, proc.returncode, stdout or "", stderr or "")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _source_tree_sha256(root: Path) -> str:
    h = hashlib.sha256()
    files = sorted(p for p in root.rglob("*") if p.is_file())
    for p in files:
        if any(part in {".git", "__pycache__", ".cache"} for part in p.parts):
            continue
        rel = p.relative_to(root).as_posix()
        h.update(rel.encode())
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _parse_release_toml(text: str) -> dict:
    """Lightweight parser for the release.toml schema used by this task."""
    data: dict = {"instances": [], "subsets": []}
    section = None
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[[") and line.endswith("]]"):
            name = line[2:-2].strip()
            current = {}
            data.setdefault(name, []).append(current)
            section = name
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            data[section] = {}
            current = data[section]
            continue
        if "=" not in line:
            continue
        key, val = [x.strip() for x in line.split("=", 1)]
        if val in {"true", "false"}:
            parsed: object = val == "true"
        elif val.startswith('"') and val.endswith('"'):
            parsed = val[1:-1]
        elif "." in val:
            parsed = float(val)
        else:
            try:
                parsed = int(val)
            except ValueError:
                parsed = val
        if current is not None and section in {"instances", "subsets", "variable", "archive"}:
            current[key] = parsed
        elif section is None or section in data and isinstance(data.get(section), dict) and section not in {
            "instances",
            "subsets",
        }:
            if section and isinstance(data.get(section), dict):
                data[section][key] = parsed
            else:
                data[key] = parsed
        else:
            data[key] = parsed
    return data


def _load_profile(path: Path = PROFILE) -> dict:
    return _parse_release_toml(path.read_text(encoding="utf-8"))


def _expected_inventory(profile: dict) -> set[str]:
    names = {
        profile["variable"]["ttf"],
        profile["variable"]["woff2"],
        "release-manifest.json",
        profile["archive_name"],
    }
    for inst in profile["instances"]:
        names.add("static/" + inst["filename"])
    for sub in profile["subsets"]:
        names.add("subsets/" + sub["filename"])
    return names


def _dist_files(root: Path) -> set[str]:
    out: set[str] = set()
    for p in root.rglob("*"):
        if p.is_file():
            out.add(p.relative_to(root).as_posix())
    return out


@pytest.fixture(scope="module")
def default_build():
    """Run a clean default release build once for shared assertions."""
    assert BUILD.is_file(), "missing forgectl entry"
    assert os.access(BUILD, os.X_OK), "forgectl entry must be executable"
    if DIST.exists():
        shutil.rmtree(DIST)
    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = "1767225600"
    proc = _run(str(BUILD), env=env, cwd="/tmp")
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert DIST.is_dir()
    return DIST


def test_crate_inventory_exact(default_build):
    """Default crate contains exactly the ledger-declared inventory."""
    assert BUILD.is_file()
    assert os.access(BUILD, os.X_OK)
    profile = _load_profile()
    expected = _expected_inventory(profile)
    actual = _dist_files(default_build)
    assert expected <= actual
    assert actual == expected


def test_source_immutability_and_idempotent_rebuild(default_build):
    """One rebuild: masters stay byte-identical and the crate digests do not drift."""
    before_sources = {p: _sha256_file(p) for p in FONTSRC.rglob("*") if p.is_file()}
    before_sources[PROFILE] = _sha256_file(PROFILE)
    before_sources[SPEC] = _sha256_file(SPEC)
    before_crate = {
        p.relative_to(default_build).as_posix(): _sha256_file(p)
        for p in default_build.rglob("*")
        if p.is_file()
    }
    proc = _run(str(BUILD), cwd="/tmp")
    assert proc.returncode == 0, proc.stderr
    after_sources = {p: _sha256_file(p) for p in FONTSRC.rglob("*") if p.is_file()}
    after_sources[PROFILE] = _sha256_file(PROFILE)
    after_sources[SPEC] = _sha256_file(SPEC)
    after_crate = {
        p.relative_to(default_build).as_posix(): _sha256_file(p)
        for p in default_build.rglob("*")
        if p.is_file()
    }
    assert before_sources == after_sources
    assert before_crate == after_crate


def test_variable_font_ots_and_axes(default_build):
    """Variable TTF passes ots and exposes declared fvar axis bounds."""
    profile = _load_profile()
    ttf_path = default_build / profile["variable"]["ttf"]
    proc = _run("ots-sanitize", str(ttf_path))
    assert proc.returncode == 0, proc.stderr

    font = TTFont(ttf_path)
    assert "fvar" in font
    axes = {a.axisTag: a for a in font["fvar"].axes}
    assert set(axes) == {"wght", "wdth", "ROND"}
    assert axes["wght"].minValue == 300 and axes["wght"].defaultValue == 400 and axes["wght"].maxValue == 800
    assert axes["wdth"].minValue == 75 and axes["wdth"].defaultValue == 100 and axes["wdth"].maxValue == 125
    assert axes["ROND"].minValue == 0 and axes["ROND"].defaultValue == 0 and axes["ROND"].maxValue == 100


def test_variable_woff2_roundtrip(default_build):
    """WOFF2 twin decompresses and retains core variable/color name tables."""
    profile = _load_profile()
    ttf_path = default_build / profile["variable"]["ttf"]
    woff2_path = default_build / profile["variable"]["woff2"]
    assert woff2_path.is_file()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "in.woff2"
        shutil.copy2(woff2_path, tmp)
        proc = _run("woff2_decompress", str(tmp))
        assert proc.returncode == 0, proc.stderr
        produced = tmp.with_suffix(".ttf")
        assert produced.is_file()
        f1 = TTFont(ttf_path)
        f2 = TTFont(produced)
        for tag in ("fvar", "COLR", "CPAL", "name"):
            assert tag in f1 and tag in f2
        assert f1["name"].getDebugName(1) == f2["name"].getDebugName(1)


def test_named_instances_colr_cpal_and_glyphs(default_build):
    """Named instances, COLRv1/CPAL palettes, and color glyphs are present."""
    profile = _load_profile()
    ttf_path = default_build / profile["variable"]["ttf"]
    font = TTFont(ttf_path)

    names = set()
    for inst in font["fvar"].instances:
        ps = None
        for rec in font["name"].names:
            if rec.nameID == inst.subfamilyNameID:
                ps = rec.toUnicode()
                break
        names.add(ps)
    for inst in profile["instances"]:
        assert inst["name"] in names

    assert "COLR" in font and "CPAL" in font
    assert font["COLR"].version == 1
    palette_count = len(font["CPAL"].palettes)
    assert palette_count >= 2
    assert len(font["CPAL"].palettes[0]) >= 1

    man = json.loads((default_build / "release-manifest.json").read_text(encoding="utf-8"))
    assert man["palettes"] == ["Night", "Dawn"]

    glyph_order = set(font.getGlyphOrder())
    for g in ("comet", "eclipse", "orbit", "signal"):
        assert g in glyph_order
    colr = font["COLR"].table
    records = {r.BaseGlyph: r for r in colr.BaseGlyphList.BaseGlyphPaintRecord}
    for g in ("comet", "eclipse", "orbit", "signal"):
        assert g in records


def test_shaping_proof_corpora(default_build):
    """HarfBuzz shapes proof corpora and feature samples without .notdef."""
    profile = _load_profile()
    ttf = default_build / profile["variable"]["ttf"]
    samples = {
        "latin": (PROOF / "latin.txt").read_text(encoding="utf-8").strip(),
        "greek": (PROOF / "greek.txt").read_text(encoding="utf-8").strip(),
        "liga": (PROOF / "ligatures.txt").read_text(encoding="utf-8").strip(),
        "figs": (PROOF / "figures.txt").read_text(encoding="utf-8").strip(),
    }
    for _label, text in samples.items():
        if not text:
            continue
        proc = _run("hb-shape", str(ttf), text)
        assert proc.returncode == 0, proc.stderr
        assert ".notdef" not in proc.stdout

    extra = ["A\u0300", "fi", "Αα", "AV", "012"]
    for text in extra:
        proc = _run("hb-shape", "--features=+liga,+tnum,+ss01", str(ttf), text)
        assert proc.returncode == 0, proc.stderr
        assert ".notdef" not in proc.stdout


def test_static_instances_hmtx_and_nameid2(default_build):
    """Static instances match varLib advances; nameID 2 equals ledger instance name."""
    from fontTools.varLib.instancer import instantiateVariableFont

    profile = _load_profile()
    vf = TTFont(default_build / profile["variable"]["ttf"])
    for inst in profile["instances"]:
        coords = {"wght": float(inst["wght"]), "wdth": float(inst["wdth"]), "ROND": float(inst["ROND"])}
        independent = instantiateVariableFont(vf, coords, inplace=False)
        static = TTFont(default_build / "static" / inst["filename"])
        g1 = independent.getGlyphOrder()
        g2 = static.getGlyphOrder()
        assert set(g1) == set(g2)
        for g in ("A", "space", ".notdef"):
            if g in g1:
                assert independent["hmtx"][g][0] == static["hmtx"][g][0]
        assert static["name"].getDebugName(1) == profile["family"]
        assert static["name"].getDebugName(2) == inst["name"]


def test_subset_packages_coverage_and_tables(default_build):
    """Subset WOFF2 packages retain declared codepoints and optional tables."""
    profile = _load_profile()
    for sub in profile["subsets"]:
        woff2 = default_build / "subsets" / sub["filename"]
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "s.woff2"
            shutil.copy2(woff2, tmp)
            assert _run("woff2_decompress", str(tmp)).returncode == 0
            font = TTFont(tmp.with_suffix(".ttf"))
            cmap = font.getBestCmap() or {}
            cps_file = Path(sub["codepoints_file"])
            wanted = set()
            for line in cps_file.read_text(encoding="utf-8").splitlines():
                t = line.strip()
                if t.startswith("U+"):
                    wanted.add(int(t[2:], 16))
            for cp in wanted:
                assert cp in cmap, f"missing U+{cp:04X} in {sub['name']}"
            if sub["name"] == "latin-greek":
                assert 0x0041 in cmap
            if sub.get("retain_color"):
                assert "COLR" in font and "CPAL" in font
            if sub.get("retain_layout"):
                assert "GSUB" in font or "GPOS" in font


def test_manifest_schema_digests_and_canonical_json(default_build):
    """Manifest schema, digests, artifact records, and canonical JSON encoding."""
    man = json.loads((default_build / "release-manifest.json").read_text(encoding="utf-8"))
    assert man["schema_version"] == 1
    assert man["family"] == "Asterism Color"
    assert man["version"] == "1.0.0"
    assert man["source_date_epoch"] == 1767225600
    assert len(man["profile_sha256"]) == 64
    assert len(man["source_tree_sha256"]) == 64
    assert man["source_tree_sha256"] == _source_tree_sha256(FONTSRC)
    assert man["profile_sha256"] == _sha256_file(PROFILE)
    paths = [a["path"] for a in man["artifacts"]]
    assert paths == sorted(paths)
    for art in man["artifacts"]:
        assert art["path"].endswith(".zip") is False
        abs_path = default_build / art["path"]
        assert abs_path.is_file()
        assert art["size"] == abs_path.stat().st_size
        assert art["sha256"] == _sha256_file(abs_path)

    raw = (default_build / "release-manifest.json").read_bytes()
    assert raw.endswith(b"\n")
    assert raw.endswith(b"\n\n") is False
    assert list(man.keys()) == sorted(man.keys())
    assert [a["path"] for a in man["artifacts"]] == sorted(a["path"] for a in man["artifacts"])


def test_archive_membership_and_timestamps(default_build):
    """Release ZIP lists finished fonts only with stable epoch timestamps."""
    profile = _load_profile()
    zpath = default_build / profile["archive_name"]
    with zipfile.ZipFile(zpath) as zf:
        names = zf.namelist()
        assert names == sorted(names)
        assert all("/" != n[:1] and ".." not in n for n in names)
        assert "release-manifest.json" in names
        assert profile["variable"]["ttf"] in names
        assert any(n.endswith(".ufo") or n.startswith("foundry-sources/") for n in names) is False
        for info in zf.infolist():
            assert info.date_time == (2026, 1, 1, 0, 0, 0) or info.date_time[0] >= 2025


def test_no_host_path_leaks_in_artifacts(default_build):
    """Finished fonts and archives do not embed host absolute paths."""
    banned = [b"/app/foundry-sources", b"/tmp/", b"/home/", b"asterism-build"]
    for p in default_build.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix in {".ttf", ".woff2", ".zip"}:
            data = p.read_bytes()
            for b in banned:
                assert b not in data, f"{b!r} leaked into {p}"


def test_dual_root_byte_identical_outputs(default_build):
    """Two clean builds under different absolute roots yield identical digests."""
    assert default_build.is_dir()
    with tempfile.TemporaryDirectory(prefix="rootA_") as a, tempfile.TemporaryDirectory(prefix="rootB_xx_") as b:
        roots: list[tuple[str, Path]] = []
        for root in (a, b):
            src = Path(root) / "foundry-sources"
            rel = Path(root) / "asterism-ledger"
            out = Path(root) / "colr-crate"
            shutil.copytree(FONTSRC, src)
            shutil.copytree(LEDGER_DIR, rel)
            proc = _run(
                [
                    str(BUILD),
                    "--source-root",
                    str(src),
                    "--profile",
                    str(rel / "release.toml"),
                    "--output",
                    str(out),
                ],
                cwd="/var/tmp" if Path("/var/tmp").exists() else "/tmp",
            )
            assert proc.returncode == 0, proc.stderr
            roots.append((root, out))

        files_a = {
            p.relative_to(roots[0][1]).as_posix(): _sha256_file(p)
            for p in roots[0][1].rglob("*")
            if p.is_file()
        }
        files_b = {
            p.relative_to(roots[1][1]).as_posix(): _sha256_file(p)
            for p in roots[1][1].rglob("*")
            if p.is_file()
        }
        assert files_a == files_b


def test_relative_cli_paths_rejected(default_build):
    """Relative --source-root fails without writing a success pair."""
    assert default_build.is_dir()
    before = _dist_files(DIST) if DIST.exists() else set()
    proc = _run(str(BUILD), "--source-root", "foundry-sources", "--profile", str(PROFILE), "--output", str(DIST))
    assert proc.returncode != 0
    # Default crate from the module fixture must remain intact after the rejected call.
    assert _dist_files(DIST) == before


def test_ledger_mutations_and_invalid_abort(default_build):
    """One mutated pack retargets archive/instance/subset/palette; invalid ledger aborts."""
    assert default_build.is_dir()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src = root / "foundry-sources"
        rel = root / "asterism-ledger"
        out = root / "colr-crate"
        shutil.copytree(FONTSRC, src)
        shutil.copytree(LEDGER_DIR, rel)
        text = (rel / "release.toml").read_text(encoding="utf-8")
        text = text.replace('archive_name = "AsterismColor-1.0.0.zip"', 'archive_name = "AsterismColor-HIDDEN.zip"')
        text = text.replace("wght = 400\nwdth = 100\nROND = 0", "wght = 500\nwdth = 100\nROND = 0", 1)
        text = text.replace(
            'filename = "AsterismColor-Text.ttf"',
            'filename = "AsterismColor-HiddenText.ttf"',
            1,
        )
        (rel / "release.toml").write_text(text, encoding="utf-8")
        (rel / "subset-latin-greek.txt").write_text("U+0041\nU+0042\n", encoding="utf-8")
        pal = (src / "color" / "palettes.toml").read_text(encoding="utf-8")
        pal = pal.replace('name = "Night"', 'name = "Midnight"', 1)
        (src / "color" / "palettes.toml").write_text(pal, encoding="utf-8")
        proc = _run(
            [str(BUILD), "--source-root", str(src), "--profile", str(rel / "release.toml"), "--output", str(out)],
            cwd=td,
        )
        assert proc.returncode == 0, proc.stderr
        assert (out / "AsterismColor-HIDDEN.zip").is_file()
        assert (out / "static" / "AsterismColor-HiddenText.ttf").is_file()
        man = json.loads((out / "release-manifest.json").read_text(encoding="utf-8"))
        assert any(i["name"] == "Text" and i["coordinates"]["wght"] == 500.0 for i in man["named_instances"])
        assert "Midnight" in man["palettes"]
        woff2 = out / "subsets" / "AsterismColor-LatinGreek.woff2"
        with tempfile.TemporaryDirectory() as td2:
            tmp = Path(td2) / "s.woff2"
            shutil.copy2(woff2, tmp)
            assert _run("woff2_decompress", str(tmp)).returncode == 0
            cmap = TTFont(tmp.with_suffix(".ttf")).getBestCmap() or {}
            assert 0x0041 in cmap and 0x0042 in cmap

    profile = _load_profile()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src = root / "foundry-sources"
        rel = root / "asterism-ledger"
        out = root / "colr-crate"
        shutil.copytree(FONTSRC, src)
        shutil.copytree(LEDGER_DIR, rel)
        (rel / "release.toml").write_text("schema_version = 1\nfamily = \"X\"\n", encoding="utf-8")
        proc = _run(
            [str(BUILD), "--source-root", str(src), "--profile", str(rel / "release.toml"), "--output", str(out)],
            cwd=td,
        )
        assert proc.returncode != 0
        if out.exists():
            man = out / "release-manifest.json"
            success_pair = man.is_file() and (out / profile["variable"]["ttf"]).is_file()
            assert success_pair is False
