import csv
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

import mpmath as mp

ROOT = Path("/app/environment")
OUT = ROOT / "outputs"
FIXT = Path("/tests/fixtures")

mp.mp.dps = 1900

REL_TOL = mp.mpf("1e-9")
ABS_TOL = mp.mpf("1e-300")


def read_case(path):
    """Parse a case file into a list of (coef_string, arg_string) pairs, keeping
    both fields as their full-precision decimal strings."""
    toks = Path(path).read_text().split()
    n = int(toks[0])
    pairs = []
    p = 1
    for _ in range(n):
        pairs.append((toks[p], toks[p + 1]))
        p += 2
    return pairs


_REF_CACHE = {}


def reference(path):
    """Return (S, terms): the reference weighted sum for a case and its list of
    signed terms c_i * erf(x_i), computed at high precision and cached."""
    key = str(path)
    if key not in _REF_CACHE:
        terms = [mp.mpf(c) * mp.erf(mp.mpf(x)) for (c, x) in read_case(path)]
        _REF_CACHE[key] = (mp.fsum(terms), terms)
    return _REF_CACHE[key]


def run_all(cases=None, data_dir=None):
    env = os.environ.copy()
    if cases is not None:
        env["ERFSUM_CASES"] = str(cases)
    if data_dir is not None:
        env["ERFSUM_DATA_DIR"] = str(data_dir)
    subprocess.run(
        ["bash", "scripts/run_all.sh"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def read_output(name):
    return mp.mpf((OUT / f"{name}.txt").read_text().split()[0])


def assert_case(name, path):
    ref, _ = reference(path)
    got = read_output(name)
    assert mp.isfinite(got), f"{name}: non-finite output {got}"
    tol = max(ABS_TOL, REL_TOL * abs(ref))
    assert abs(got - ref) <= tol, f"{name}: got {got}, ref {ref}"


def check_manifest(manifest_path, data_dir):
    with open(manifest_path) as f:
        rows = list(csv.DictReader(f))
    assert rows
    for row in rows:
        name = row["name"]
        assert (OUT / f"{name}.txt").exists(), f"missing output for {name}"
        assert_case(name, Path(data_dir) / row["input_path"])


def test_a_public_outputs_match_reference():
    """Build and run on the public cases, then check every reported sum against the
    independent high-precision reference recomputed from the same terms."""
    run_all()
    with open(ROOT / "data" / "cases.csv") as f:
        names = [row["name"] for row in csv.DictReader(f)]
    assert names
    check_manifest(ROOT / "data" / "cases.csv", ROOT)


def test_b_hidden_outputs_match_reference():
    """Re-run the same executable on held-back cases and apply the same accuracy
    check, so a solution tuned to the public names cannot pass."""
    run_all(cases=FIXT / "hidden_cases.csv", data_dir=FIXT)
    check_manifest(FIXT / "hidden_cases.csv", FIXT)


def strip_comments(text):
    """Drop // and /* */ comments while keeping string literals intact."""
    out = []
    i, n = 0, len(text)
    quote = None
    while i < n:
        c = text[i]
        if quote is not None:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "/":
            i += 2
            while i < n and text[i] != "\n":
                i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
        elif c == '"' or c == "'":
            quote = c
            out.append(c)
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def blank_strings(text):
    """Replace string and char literal contents with empty quotes."""
    return re.sub(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", '""', text)


FORBIDDEN_CALL_RE = re.compile(
    r"\b(?:"
    r"system|popen|"
    r"execl|execlp|execle|execv|execvp|execvpe|execve|"
    r"posix_spawn|posix_spawnp|fork|vfork|"
    r"dlopen|dlsym|dlmopen|"
    r"Py_Initialize|PyRun_\w+|"
    r"mpfr_\w+|mpf_\w+|mpz_\w+|mpq_\w+|__gmp\w+|"
    r"arb_\w+|arf_\w+|acb_\w+|gsl_\w+|"
    r"__float128|_Float128|__floattitf|quadmath_\w+"
    r")_?\s*\(",
    re.IGNORECASE,
)

FORBIDDEN_ASM_RE = re.compile(r"\b(?:__asm__|__asm|asm)\b\s*(?:volatile\s*)?\(")

FORBIDDEN_TYPE_RE = re.compile(r"\b(?:long\s+double|__float128|_Float128|__float80)\b")

FORBIDDEN_INCLUDE_TOKENS = (
    "gmp.h",
    "gmpxx",
    "mpfr.h",
    "mpf2mpfr",
    "mpir",
    "quadmath.h",
    "mpc.h",
    "arb.h",
    "arf.h",
    "acb.h",
    "flint",
    "gsl/",
    "boost/multiprecision",
    "ttmath",
    "dlfcn",
    "python",
)

FORBIDDEN_LINK_RE = re.compile(
    r"-l\s*(?:gmp|gmpxx|mpfr|mpir|quadmath|mpc|arb|arf|acb|flint|gsl\w*|ttmath|python\S*)\b",
    re.IGNORECASE,
)

INTERP_RE = re.compile(
    r"(?<![\w./-])(?:python3?|perl|ruby|node|nodejs|julia|octave|Rscript|"
    r"gawk|mawk|awk|php|lua|bc|dc)\b"
)

SOURCE_EXTS = (".c", ".h", ".cc", ".cpp", ".cxx", ".c++", ".hpp", ".hh", ".hxx")
INTERP_SOURCE_EXTS = (".py", ".pl", ".rb", ".js", ".mjs", ".jl", ".lua", ".php", ".r")

MAKEFILE_SOURCE_RE = re.compile(
    r"[\w./+-]+\.(?:c|cc|cpp|cxx|c\+\+|h|hpp|hh|hxx)\b", re.IGNORECASE
)


def compiled_source_files():
    """Every C/C++ unit and header shipped in the environment, discovered both by
    a recursive tree walk and by the source tokens named in the Makefile build
    command, so a forbidden call cannot be hidden in a nested or oddly named unit."""
    found = set()
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in SOURCE_EXTS:
            found.add(path.resolve())
    makefile = ROOT / "Makefile"
    if makefile.exists():
        for tok in MAKEFILE_SOURCE_RE.findall(makefile.read_text()):
            cand = (ROOT / tok).resolve()
            if cand.is_file():
                found.add(cand)
    return sorted(found)


def build_scripts():
    """The Makefile plus every shell script under the environment."""
    scripts = []
    mk = ROOT / "Makefile"
    if mk.exists():
        scripts.append(mk)
    scripts.extend(sorted(ROOT.rglob("*.sh")))
    return scripts


def test_c_source_is_from_scratch():
    """Confirm the kernel is solved from scratch in C with only ordinary doubles.
    Every C unit and header in the compiled tree is scanned for shell-outs, runtime
    code loading, inline assembly, embedded interpreters, wider-than-double built-in
    types, and calls into an external arbitrary-precision or special-function
    library; the Makefile must not link one and the build and run path must not
    route the computation through an interpreter or ship an interpreter source file,
    so the extended precision must be built by hand from doubles rather than
    borrowed, and the work cannot be done in Python while cosmetic C is left in
    place."""
    sources = compiled_source_files()
    assert sources
    for src_file in sources:
        no_comments = strip_comments(src_file.read_text())
        code = blank_strings(no_comments)
        call = FORBIDDEN_CALL_RE.search(code)
        assert call is None, f"forbidden call {call.group(0)!r} in {src_file}"
        assert FORBIDDEN_ASM_RE.search(code) is None, f"inline asm in {src_file}"
        wider = FORBIDDEN_TYPE_RE.search(code)
        assert wider is None, f"wider-than-double type {wider.group(0)!r} in {src_file}"
        for inc in re.findall(r"#\s*include\s*[<\"]([^>\"]+)[>\"]", no_comments):
            low = inc.lower()
            bad = next((t for t in FORBIDDEN_INCLUDE_TOKENS if t in low), None)
            assert bad is None, f"forbidden include {inc!r} in {src_file}"

    makefile = ROOT / "Makefile"
    if makefile.exists():
        link = FORBIDDEN_LINK_RE.search(makefile.read_text())
        assert link is None, f"forbidden library link {link.group(0)!r} in Makefile"

    for script in build_scripts():
        code = blank_strings(strip_comments(script.read_text()))
        hit = INTERP_RE.search(code)
        assert hit is None, f"interpreter {hit.group(0)!r} invoked in {script}"

    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in INTERP_SOURCE_EXTS:
            raise AssertionError(f"interpreter source file shipped: {path}")

    run_all_text = blank_strings(
        strip_comments((ROOT / "scripts" / "run_all.sh").read_text())
    )
    assert "./erfsum" in run_all_text, (
        "run_all.sh must run the compiled ./erfsum binary"
    )

    main_code = blank_strings(strip_comments((ROOT / "src" / "main.c").read_text()))
    assert re.search(r"\berfsum_weighted_sum\s*\(", main_code), (
        "main.c must call erfsum_weighted_sum"
    )


def naive_float64(path):
    """The plain-double baseline the starter uses: evaluate erf by its series in
    double and accumulate the weighted sum in double. The double erf error, tiny on
    its own, is amplified by the cancellation, so this is destroyed on every case."""
    two_over_sqrt_pi = 2.0 / math.sqrt(math.pi)
    s = 0.0
    for c, x in read_case(path):
        xf = float(x)
        x2 = xf * xf
        b = xf
        acc = xf
        for k in range(1, 600):
            b *= -x2 / k
            acc += b / (2.0 * k + 1.0)
            if abs(b) < abs(acc) * 1e-18:
                break
        s += float(c) * two_over_sqrt_pi * acc
    return s


def sum_at_precision(path, dps):
    """Recompute the weighted sum at a fixed working precision of dps digits, a
    proxy for a fixed-width software float of that precision."""
    old = mp.mp.dps
    mp.mp.dps = dps
    acc = mp.mpf(0)
    for c, x in read_case(path):
        acc += mp.mpf(c) * mp.erf(mp.mpf(x))
    mp.mp.dps = old
    return +acc


def relerr(approx, ref):
    return abs(mp.mpf(approx) - ref) / abs(ref)


def cancellation_depth(path):
    ref, terms = reference(path)
    return mp.fsum([abs(t) for t in terms]) / abs(ref)


def significant_digits(dec_str):
    """Count significant decimal digits in a plain decimal literal."""
    s = dec_str.lstrip("+-").replace(".", "")
    s = s.lstrip("0")
    return len(s)


def test_d_cancellation_defeats_double_and_fixed_precision():
    """Document and pin the regime that makes the cases hard, two obstacles at once,
    and pin the depth so the task cannot drift back to being solvable by an
    off-the-shelf fixed multi-double.

    On every public case the weighted terms cancel so deeply (cond > 1e200) that no
    hardware-adjacent significand survives and a plain double is destroyed, while
    each argument carries far more digits than a double can hold. On the held-back
    hid_g the cancellation is far deeper still (cond > 1e1400), and a fixed 4096-bit
    (~1233 digit) significand, comfortably wide for the public cases, is overwhelmed:
    the working precision has to scale to the data, not be fixed to what the public
    cases reveal."""
    with open(ROOT / "data" / "cases.csv") as f:
        prows = list(csv.DictReader(f))
    with open(FIXT / "hidden_cases.csv") as f:
        hrows = list(csv.DictReader(f))

    double_failures = 0
    for row in prows:
        path = ROOT / row["input_path"]
        pairs = read_case(path)
        for _, x in pairs:
            assert significant_digits(x) > 40, (
                f"{row['name']}: argument not high precision"
            )
        ref, _ = reference(path)
        assert abs(ref) > mp.mpf("1e-3"), f"{row['name']}: reference too near zero"
        depth = cancellation_depth(path)
        assert depth > mp.mpf("1e200"), (
            f"{row['name']}: cancellation too mild ({float(depth):.2e})"
        )
        # the plain-double baseline must miss by a wide margin, not merely by the
        # grading tolerance: at least 1000000 * REL_TOL (~1e-3) relative error.
        naive = naive_float64(path)
        if math.isfinite(naive) and relerr(naive, ref) > 1000000 * REL_TOL:
            double_failures += 1
        elif not math.isfinite(naive):
            double_failures += 1
    assert double_failures == len(prows), (
        f"only {double_failures}/{len(prows)} public cases destroy a plain double"
    )

    max_pub_depth = max(cancellation_depth(ROOT / r["input_path"]) for r in prows)
    max_hid_depth = max(cancellation_depth(FIXT / r["input_path"]) for r in hrows)
    assert max_hid_depth > max_pub_depth, (
        "held-back cancellation must reach deeper than public"
    )

    # hid_g cancels far more deeply than any public case, so a solution whose
    # precision is sized to the visible cases is not enough. Pin that a 4096-bit
    # (~1233 digit) significand, ample for the public cancellation, still misses the
    # grade on the deeper held-back case.
    hidden_path = FIXT / "hid_g.txt"
    href, _ = reference(hidden_path)
    hdepth = cancellation_depth(hidden_path)
    assert hdepth > mp.mpf("1e1400"), (
        f"hidden cancellation too mild ({float(hdepth):.2e})"
    )
    approx1233 = sum_at_precision(hidden_path, 1233)
    assert relerr(approx1233, href) > REL_TOL, (
        "a 4096-bit (1233-digit) precision must miss the hidden grade"
    )


def test_e_outputs_directory_is_rebuilt():
    """A stale outputs directory must be regenerated from source by the build
    script, not left over from a previous run."""
    shutil.rmtree(OUT, ignore_errors=True)
    run_all()
    assert OUT.is_dir()
    with open(ROOT / "data" / "cases.csv") as f:
        names = [row["name"] for row in csv.DictReader(f)]
    for name in names:
        assert (OUT / f"{name}.txt").exists()


def test_f_interface_is_preserved():
    """The declared erfsum_weighted_sum interface in the public header must stay
    unchanged, so the kernel is still invoked with the original contract."""
    header = (ROOT / "include" / "erfsum.h").read_text()
    normalized = " ".join(header.split())
    expected = (
        "void erfsum_weighted_sum(int n, const char *const *c, const char *const *x, "
        "double *out);"
    )
    assert expected in normalized, "erfsum_weighted_sum declaration was altered"
