import csv
import math
import shutil
import subprocess
import tempfile
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 80

ROOT = Path("/app/environment")
OUT = ROOT / "outputs"
FIXT = Path(__file__).resolve().parent / "fixtures"

REL_TOL = Decimal("1e-9")

# The verifier owns the graded executable. It is compiled here, from the two
# required C sources with a fixed command, into a directory the task cannot
# write to, so the graded value always comes from executing compiled C and never
# from the agent's Makefile, run_all.sh, or a pre-placed binary.
VDIR = Path(tempfile.mkdtemp(prefix="theta_verifier_"))
GRADED_BIN = VDIR / "theta_graded"
CC = "gcc"
CFLAGS = ["-std=c11", "-O2", "-Wall", "-Wextra", "-pedantic", "-ffp-contract=off"]
KERNEL = "src/theta.c"
DRIVER = "src/main.c"


def load_refs(name):
    with open(FIXT / name) as f:
        return {r["name"]: Decimal(r["reference"]) for r in csv.DictReader(f)}


PUB_REF = load_refs("pub_ref.csv")
HID_REF = load_refs("hid_ref.csv")


def manifest_rows(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def read_terms(path):
    toks = Path(path).read_text().split()
    n = int(toks[0])
    terms = []
    idx = 1
    for _ in range(n):
        terms.append((toks[idx], toks[idx + 1], toks[idx + 2]))
        idx += 3
    return terms


def compile_kernel(driver, kernel, outbin):
    """Compile the driver and kernel into outbin with the fixed command."""
    cmd = (
        [CC]
        + CFLAGS
        + [
            "-I",
            str(ROOT / "include"),
            str(driver),
            str(kernel),
            "-o",
            str(outbin),
            "-lm",
        ]
    )
    return subprocess.run(cmd, text=True, capture_output=True)


_COMPILED = {}


def graded_binary():
    """Compile the required sources once and return the verifier-owned binary."""
    if "bin" not in _COMPILED:
        proc = compile_kernel(ROOT / DRIVER, ROOT / KERNEL, GRADED_BIN)
        assert proc.returncode == 0, (
            f"the required C sources did not compile with the fixed command:\n{proc.stderr}"
        )
        assert GRADED_BIN.exists(), "fixed compile produced no binary"
        _COMPILED["bin"] = GRADED_BIN
    return _COMPILED["bin"]


def run_case(binary, case_path, out_path):
    subprocess.run(
        [str(binary), str(case_path), str(out_path)], check=True, capture_output=True
    )


def one_finite_token(text, name):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 1, f"{name}: expected one line"
    toks = lines[0].split()
    assert len(toks) == 1, f"{name}: expected one token"
    assert math.isfinite(float(toks[0])), f"{name}: non-finite value"
    return toks[0]


def assert_close(name, got, ref):
    got = Decimal(got)
    assert got.is_finite(), f"{name}: non-finite output"
    rel = abs(got - ref) / abs(ref)
    assert rel <= REL_TOL, f"{name}: relative error {rel:.3e} exceeds 1e-9"


def grade_manifest(manifest, base, refs, workdir):
    binary = graded_binary()
    rows = manifest_rows(manifest)
    assert rows
    for row in rows:
        name = row["name"]
        out_path = workdir / f"{name}.out"
        run_case(binary, base / row["case_path"], out_path)
        tok = one_finite_token(out_path.read_text(), name)
        assert_close(name, tok, refs[name])


def test_a_public_cases_match_reference(tmp_path):
    """The verifier-compiled binary is run on every public case and each value
    matches the independent reference."""
    grade_manifest(ROOT / "data" / "cases.csv", ROOT, PUB_REF, tmp_path)


def test_b_hidden_cases_match_reference(tmp_path):
    """The same verifier-compiled binary is run on the held-back cases, which
    reach the worst-case coefficient length and cancellation, and each value
    matches the reference. This is the graded check and it depends only on the
    compiled C, not on the agent's build script."""
    grade_manifest(FIXT / "hidden_cases.csv", FIXT, HID_REF, tmp_path)


def test_c_script_cannot_masquerade_as_the_kernel(tmp_path):
    """A shell script placed where src/theta.c belongs is rejected by the fixed
    compile, so the graded binary can only come from real C compiled by the
    verifier, never from a script the agent's Makefile drops at the binary path."""
    binary = graded_binary()
    assert ROOT not in binary.parents, "graded binary is not verifier-owned"
    fake = tmp_path / "theta.c"
    fake.write_text("#!/bin/sh\necho 0\n")
    out = tmp_path / "masquerade"
    proc = compile_kernel(ROOT / DRIVER, fake, out)
    assert proc.returncode != 0, "a shell script compiled as the C kernel"
    assert not out.exists(), "a non-C kernel produced a graded binary"


def test_d_build_script_produces_every_output():
    """The agent build script rebuilds the program and writes one finite output
    file per case, including after a stale outputs directory is removed."""
    shutil.rmtree(OUT, ignore_errors=True)
    subprocess.run(
        ["bash", "scripts/run_all.sh"], cwd=ROOT, check=True, capture_output=True
    )
    assert OUT.is_dir()
    for row in manifest_rows(ROOT / "data" / "cases.csv"):
        name = row["name"]
        path = OUT / f"{name}.txt"
        assert path.exists(), f"missing output for {name}"
        one_finite_token(path.read_text(), name)


def test_e_interface_is_preserved():
    """The declared theta3 interface in the public header stays unchanged."""
    header = (ROOT / "include" / "theta.h").read_text()
    normalized = " ".join(header.split())
    expected = (
        "void theta3(int n, const char *const *c, const char *const *z, "
        "const char *const *q, double *out);"
    )
    assert expected in normalized, "theta3 declaration was altered"


def test_f_case_set_is_large_enough():
    """Enough distinct cases and terms exist that grading cannot vacuously pass."""
    pub = manifest_rows(ROOT / "data" / "cases.csv")
    hid = manifest_rows(FIXT / "hidden_cases.csv")
    assert len(pub) >= 12
    assert len(hid) >= 20
    total_terms = 0
    for row in pub:
        total_terms += len(read_terms(ROOT / row["case_path"]))
    for row in hid:
        total_terms += len(read_terms(FIXT / row["case_path"]))
    assert total_terms >= 60, f"only {total_terms} terms"


def _naive_double_sum(terms):
    """Textbook double-precision evaluation of S = sum c_i theta3(z_i, q_i)."""
    acc = 0.0
    for c, z, q in terms:
        cf, zf, qf = float(c), float(z), float(q)
        s = 1.0
        for k in range(1, 401):
            t = 2.0 * (qf ** (k * k)) * math.cos(2.0 * k * zf)
            s += t
            if abs(t) < 1e-18 and k > 4:
                break
        acc += cf * s
    return acc


def test_g_naive_double_fails_several():
    """The textbook double-precision evaluation misses the accuracy contract on
    many cases, so passing requires genuine extended-precision work."""
    failures = 0
    for base, manifest, refs in (
        (ROOT, ROOT / "data" / "cases.csv", PUB_REF),
        (FIXT, FIXT / "hidden_cases.csv", HID_REF),
    ):
        for row in manifest_rows(manifest):
            terms = read_terms(base / row["case_path"])
            ref = refs[row["name"]]
            try:
                got = _naive_double_sum(terms)
            except (ValueError, OverflowError):
                failures += 1
                continue
            if not math.isfinite(got):
                failures += 1
                continue
            rel = abs(Decimal(repr(got)) - ref) / abs(ref)
            if rel > REL_TOL:
                failures += 1
    assert failures >= 20, (
        f"expected the naive double sum to fail many cases, got {failures}"
    )


def _agent_source():
    """De-commented text of every C source and header under the agent-editable tree."""

    def strip(text):
        out = []
        i, n = 0, len(text)
        while i < n:
            two = text[i : i + 2]
            if two == "/*":
                j = text.find("*/", i + 2)
                i = n if j == -1 else j + 2
            elif two == "//":
                j = text.find("\n", i + 2)
                i = n if j == -1 else j
            else:
                out.append(text[i])
                i += 1
        return "".join(out)

    parts = []
    for base in (ROOT / "src", ROOT / "include"):
        for p in sorted(base.rglob("*")):
            if p.suffix in (".c", ".h", ".cc", ".cpp", ".cxx", ".hpp"):
                parts.append(strip(p.read_text(errors="ignore")))
    return "\n".join(parts)


def test_h_no_shelling_out():
    """The kernel must be self-contained C, not delegate arithmetic to another process."""
    src = _agent_source()
    for tok in (
        "system",
        "popen",
        "execl",
        "execv",
        "execle",
        "execlp",
        "execvp",
        "posix_spawn",
        "fork",
        "syscall",
    ):
        assert tok not in src, f"forbidden process/shell primitive '{tok}' in source"


def test_i_no_forbidden_types_or_libraries():
    """No wider built-in type and no external extended-precision or special-function library."""
    src = _agent_source().lower()
    for tok in (
        "long double",
        "__float128",
        "_float128",
        "__int128",
        "quadmath",
        "gmp.h",
        "mpfr.h",
        "mpir",
    ):
        assert tok not in src, f"forbidden type/library token '{tok}' in source"


def test_j_build_is_native():
    """The Makefile and run_all.sh do not link a banned library or invoke an interpreter."""
    make = (ROOT / "Makefile").read_text().lower()
    for tok in ("-lgmp", "-lmpfr", "-lquadmath", "libquadmath"):
        assert tok not in make, f"Makefile links forbidden library '{tok}'"
    run = (ROOT / "scripts" / "run_all.sh").read_text().lower()
    for tok in ("python", "perl", "ruby", "node", "mpmath", "sage", "octave"):
        assert tok not in run, f"run_all.sh invokes forbidden interpreter '{tok}'"


def test_k_results_are_deterministic():
    """Running the build twice yields identical reported values."""
    subprocess.run(
        ["bash", "scripts/run_all.sh"], cwd=ROOT, check=True, capture_output=True
    )
    first = (
        OUT / f"{manifest_rows(ROOT / 'data' / 'cases.csv')[0]['name']}.txt"
    ).read_text()
    subprocess.run(
        ["bash", "scripts/run_all.sh"], cwd=ROOT, check=True, capture_output=True
    )
    second = (
        OUT / f"{manifest_rows(ROOT / 'data' / 'cases.csv')[0]['name']}.txt"
    ).read_text()
    assert first == second
