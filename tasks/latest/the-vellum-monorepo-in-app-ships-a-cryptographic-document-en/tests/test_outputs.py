"""Behavioral verification for the Vellum offline release.

These tests exercise the public contract in ``/app/docs/release-contract.md``:
they run ``/app/bin/release`` from independent source roots and assert that the
bundle is byte-for-byte reproducible, that the three surfaces (native library,
Python wheel, Node package) report one identity and agree on documented
operations, that the dependency inventory matches the closure actually
compiled, and that provenance binds the final shipped bytes with a verifying
signature.

The tests build from clean copies of ``/app`` so they depend only on the fixed
source, not on any pre-existing build output.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from argparse import Namespace
from pathlib import Path

import pytest

APP = Path("/app")
FIXTURES = APP / "fixtures" / "documents"
REQUIRED_FILES = [
    "native/libvellum.so",
    "metadata/dependency-inventory.json",
    "metadata/provenance.json",
    "metadata/provenance.sig",
    "metadata/release-public.pem",
    "SHA256SUMS",
]


def _copy_clean(dst: Path) -> Path:
    shutil.copytree(APP, dst, symlinks=True, dirs_exist_ok=True)
    build_dir = dst / "target"
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)
    for leftover in list(dst.rglob("native-target")):
        if leftover.is_dir():
            shutil.rmtree(leftover, ignore_errors=True)
    return dst


def _run_release(root: Path, out: Path, extra_env: dict | None = None) -> Path:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    subprocess.run(
        [str(root / "scripts" / "release"), "--source-root", str(root), "--output", str(out)],
        check=True,
        env=env,
        stdout=subprocess.DEVNULL,
    )
    return out


@pytest.fixture(scope="session")
def bundles(tmp_path_factory):
    # Two roots at distinct absolute paths of different depth so the
    # reproducibility assertion actually exercises path independence.
    root_a = _copy_clean(tmp_path_factory.mktemp("src"))
    root_b = _copy_clean(tmp_path_factory.mktemp("src") / "release")
    root_dev = _copy_clean(tmp_path_factory.mktemp("src"))
    out_a = _run_release(root_a, tmp_path_factory.mktemp("out"))
    out_b = _run_release(root_b, tmp_path_factory.mktemp("out"))
    # A developer capability override must not change release output.
    out_dev = _run_release(root_dev, tmp_path_factory.mktemp("out"),
                           {"VELLUM_DEV_CAPS": "strict"})
    return Namespace(root_a=root_a, out_a=out_a, out_b=out_b, out_dev=out_dev)


# ---- helpers ---------------------------------------------------------------

def _native_identity(so: Path) -> dict:
    lib = ctypes.CDLL(str(so))
    lib.vellum_identity_json.restype = ctypes.c_void_p
    lib.vellum_free.argtypes = [ctypes.c_void_p]
    ptr = lib.vellum_identity_json()
    text = ctypes.cast(ptr, ctypes.c_char_p).value.decode()
    lib.vellum_free(ptr)
    return json.loads(text)


def _native_call(so: Path, symbol: str, payload: str) -> str:
    lib = ctypes.CDLL(str(so))
    fn = getattr(lib, symbol)
    fn.restype = ctypes.c_void_p
    fn.argtypes = [ctypes.c_char_p]
    lib.vellum_free.argtypes = [ctypes.c_void_p]
    ptr = fn(payload.encode())
    out = ctypes.cast(ptr, ctypes.c_char_p).value.decode()
    lib.vellum_free(ptr)
    return out


def _extract_wheel_so(out: Path) -> Path:
    whl = next(out.glob("python/*.whl"))
    dest = Path(tempfile.mkdtemp())
    with zipfile.ZipFile(whl) as zf:
        zf.extractall(dest)
    return next(dest.rglob("libvellum.so"))


def _extract_node_cli(out: Path) -> Path:
    tgz = next(out.glob("node/*.tgz"))
    dest = Path(tempfile.mkdtemp())
    subprocess.run(["tar", "-xzf", str(tgz), "-C", str(dest)], check=True)
    return dest / "package" / "bin" / "vellum-cli"


def _node_identity(cli: Path) -> dict:
    return json.loads(subprocess.check_output([str(cli), "identity"]).decode())


# ---- tests -----------------------------------------------------------------

def test_bundle_structure(bundles):
    """The release writes the full bundle tree defined by the release contract."""
    out = bundles.out_a
    for rel in REQUIRED_FILES:
        assert (out / rel).is_file(), f"missing {rel}"
    assert list(out.glob("python/*.whl")), "wheel missing"
    assert list(out.glob("node/*.tgz")), "node tarball missing"


def test_reproducible_across_roots(bundles):
    """Two clean releases from differently named source roots are byte-identical."""
    o1, o2 = bundles.out_a, bundles.out_b
    sums1 = (o1 / "SHA256SUMS").read_text()
    sums2 = (o2 / "SHA256SUMS").read_text()
    assert sums1 == sums2, "release is not reproducible across source roots"
    for rel in ["native/libvellum.so"]:
        assert (o1 / rel).read_bytes() == (o2 / rel).read_bytes()
    assert next(o1.glob("python/*.whl")).read_bytes() == next(o2.glob("python/*.whl")).read_bytes()
    assert next(o1.glob("node/*.tgz")).read_bytes() == next(o2.glob("node/*.tgz")).read_bytes()


def test_sha256sums_are_correct(bundles):
    """Every digest listed in SHA256SUMS matches the shipped file bytes."""
    out = bundles.out_a
    for line in (out / "SHA256SUMS").read_text().splitlines():
        digest, rel = line.split("  ", 1)
        actual = hashlib.sha256((out / rel).read_bytes()).hexdigest()
        assert actual == digest, f"SHA256SUMS wrong for {rel}"


def test_provenance_binds_final_bytes(bundles):
    """Provenance subjects record the size and sha256 of the final shipped bytes."""
    out = bundles.out_a
    prov = json.loads((out / "metadata/provenance.json").read_text())
    subjects = {s["path"]: s for s in prov["subjects"]}
    for rel in ["native/libvellum.so", "metadata/dependency-inventory.json"]:
        assert rel in subjects, f"provenance missing subject {rel}"
    for rel, s in subjects.items():
        data = (out / rel).read_bytes()
        assert s["sha256"] == "sha256:" + hashlib.sha256(data).hexdigest(), f"stale subject {rel}"
        assert s["size"] == len(data), f"wrong size for subject {rel}"


def test_signature_verifies(bundles):
    """The detached Ed25519 signature verifies against the shipped public key."""
    out = bundles.out_a
    rc = subprocess.run(
        [
            "openssl", "pkeyutl", "-verify", "-pubin",
            "-inkey", str(out / "metadata/release-public.pem"),
            "-rawin", "-in", str(out / "metadata/provenance.json"),
            "-sigfile", str(out / "metadata/provenance.sig"),
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode
    assert rc == 0, "provenance signature does not verify"


def test_inventory_matches_compiled_closure(bundles):
    """The dependency inventory lists the compiled closure and no disabled crates."""
    out = bundles.out_a
    inv = json.loads((out / "metadata/dependency-inventory.json").read_text())
    comps = {(c["name"], c["version"]) for c in inv["components"]}
    names = {c["name"] for c in inv["components"]}
    # The legacy formatter is optional and is never compiled into the release.
    assert ("canonfmt", "0.3.1") not in comps, "inventory lists an uncompiled dependency"
    assert ("canonfmt", "0.4.0") in comps, "inventory missing the compiled canonfmt"
    for required in ["docmodel", "engine", "bridge", "rustc"]:
        assert required in names, f"inventory missing {required}"
    native = _native_identity(out / "native/libvellum.so")
    assert inv["closure_digest"] == native["dependency_closure_digest"]


def test_identity_quorum(bundles):
    """Native library, Python wheel, and Node package report one identical identity."""
    out = bundles.out_a
    native = _native_identity(out / "native/libvellum.so")
    py = _native_identity(_extract_wheel_so(out))
    node = _node_identity(_extract_node_cli(out))
    keys = ["release_id", "abi_fingerprint", "capabilities",
            "dependency_closure_digest", "version", "revision"]
    for k in keys:
        assert native[k] == py[k] == node[k], f"surfaces disagree on identity field {k}"


def test_operations_agree(bundles):
    """All surfaces agree on canonical and detached digests for every fixture."""
    out = bundles.out_a
    so = out / "native/libvellum.so"
    pyso = _extract_wheel_so(out)
    cli = _extract_node_cli(out)
    for name in ["basic", "unicode", "detached"]:
        payload = (FIXTURES / f"{name}.json").read_text()
        nd = _native_call(so, "vellum_canonical_digest", payload)
        pd = _native_call(pyso, "vellum_canonical_digest", payload)
        cd = subprocess.check_output([str(cli), "digest", payload]).decode().strip()
        assert nd == pd == cd, f"canonical_digest disagreement on {name}"
    payload = (FIXTURES / "detached.json").read_text()
    nd = _native_call(so, "vellum_detached_digest", payload)
    cd = subprocess.check_output([str(cli), "detached", payload]).decode().strip()
    assert nd == cd, "detached_digest disagreement between native and node"
    assert cd not in ("", "null"), "node package cannot perform its declared detached operation"


def test_abi_tracks_interface(bundles):
    """The ABI fingerprint and shipped declarations track the current interface."""
    out = bundles.out_a
    root = bundles.root_a
    gen = Path(tempfile.mkdtemp())
    idlgen = root / "target" / "release" / "idlgen"
    idl = root / "interface" / "document.idl"
    fresh = subprocess.check_output(
        [str(idlgen), "--idl", str(idl), "--out-dir", str(gen)]
    ).decode().strip()
    native = _native_identity(out / "native/libvellum.so")
    assert native["abi_fingerprint"] == fresh, "ABI fingerprint does not track the interface"
    # The generated node declarations must include the detached operation symbol.
    cli_dir = _extract_node_cli(out).parent.parent
    decl = (cli_dir / "decl" / "node_decl.txt").read_text()
    assert "vellum_detached_digest" in decl, "node declarations are stale"


def test_dev_overrides_do_not_change_release(bundles):
    """A developer capability override does not change the authoritative release."""
    o1, odev = bundles.out_a, bundles.out_dev
    assert (o1 / "SHA256SUMS").read_text() == (odev / "SHA256SUMS").read_text(), \
        "developer capability overrides changed the release output"
    native = _native_identity(odev / "native/libvellum.so")
    assert "strict" not in native["capabilities"]
    assert native["capabilities"] == ["core", "detached"]
