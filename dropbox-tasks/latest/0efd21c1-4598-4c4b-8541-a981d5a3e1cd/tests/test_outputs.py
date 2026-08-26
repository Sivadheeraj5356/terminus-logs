"""Verifier for the from-scratch Go recording-replay solver at /app/hmm.

The reference recording, log-likelihood and expected visit count are
recomputed here, in the verifier, from an independent self-contained
pure-Python implementation (hmmref.py) of the same semantics the agent-visible
probe binary /app/ref implements: the splitmix64 draw stream with the
reference's consumption conventions (the window-opening setup, the
per-boundary state and duration draws, the per-step recording draws, the
one-step generating lag), and the matching exact likelihood machinery (the
reference's window-opening condition, the lag, state-dependent missingness,
right censoring at T) on the dwell-augmented chain in log space. The
likelihood was validated during authoring against brute-force path
enumeration to < 1e-10, the sampler against exact enumeration of the induced
distribution over recordings, and the Python, oracle-Go and probe-binary
implementations against each other byte-for-byte. hmm_naive.py reproduces the plausible wrong consumption
conventions and wrong likelihood models so the tests can assert the solver
agrees with the reference precisely where each shortcut desyncs or lands far
outside tolerance. The probe binary only accepts cases with T <= 64, so
neither invoking nor copying it can produce the graded long-recording
results. Fresh cases are synthesised at grade time so nothing can be
pre-baked.
"""
import math
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

import hmmref  # noqa: E402
import hmm_naive  # noqa: E402
import holdout_gen  # noqa: E402

APP = "/app"
BIN = os.path.join(APP, "hmm")
REF = os.path.join(APP, "ref")
DATA = os.path.join(APP, "data")
OUT = os.path.join(APP, "output")
CASES = os.path.join(DATA, "cases.txt")
RESULTS = os.path.join(OUT, "results.txt")

TOL_LL_REL = 1e-6      # relative on the log-likelihood
TOL_NSEG_REL = 1e-6    # relative on the expected visit count
WRONG = 1e-3           # a wrong-likelihood gap this large is "materially wrong"
LONG_T = 1500          # recordings at least this long stress raw-prob arithmetic
PROBE_T = 128          # the probe reference refuses cases longer than this
HOLDOUT_SEEDS = (10007, 31337, 90210, 271828, 1618033)


def parse_results(path):
    """Parse the solver's output into {id: (obs, loglik, nseg)}."""
    with open(path, encoding="utf-8") as f:
        lines = [ln.rstrip("\n").rstrip("\r") for ln in f]
    res = {}
    order = []
    i, n = 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if s == "":
            i += 1
            continue
        assert s.startswith("CASE "), f"expected CASE, got {lines[i]!r}"
        cid = s.split(None, 1)[1].strip()
        i += 1
        toks = lines[i].split()
        assert toks and toks[0] == "O", f"expected O line, got {lines[i]!r}"
        obs = [hmmref.MISSING if x == "?" else int(x) for x in toks[1:]]
        i += 1
        assert lines[i].startswith("LOGLIK"), f"expected LOGLIK, got {lines[i]!r}"
        loglik = float(lines[i].split(None, 1)[1])
        i += 1
        assert lines[i].startswith("NSEG"), f"expected NSEG, got {lines[i]!r}"
        nseg = float(lines[i].split(None, 1)[1])
        i += 1
        assert i < n and lines[i].strip() == "END", (
            f"expected END for {cid}, got {lines[i]!r}")
        i += 1
        res[cid] = (obs, loglik, nseg)
        order.append(cid)
    return res, order


def run_on(input_path, output_path, timeout=180):
    proc = subprocess.run([BIN, input_path, output_path], capture_output=True,
                          text=True, cwd=APP, timeout=timeout)
    assert proc.returncode == 0, f"hmm exited {proc.returncode}; stderr={proc.stderr}"
    return parse_results(output_path)


def run_default(timeout=180):
    subprocess.run([BIN], check=True, capture_output=True, text=True,
                   cwd=APP, timeout=timeout)
    return parse_results(RESULTS)


def write_cases(cases, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(holdout_gen.to_text(cases))


def check_case(c, results, tag):
    """Assert the solver's result for one case matches the exact reference:
    the recording entry-for-entry, and LOGLIK / NSEG to tolerance."""
    obs, loglik, nseg = results[c["id"]]
    ref_obs = hmmref.reference_obs(c)
    assert len(obs) == c["T"], (
        f"{tag}: {c['id']} recording has {len(obs)} entries, expected T={c['T']}")
    if obs != ref_obs:
        idx = next(i for i, (a, b) in enumerate(zip(obs, ref_obs)) if a != b)
        raise AssertionError(
            f"{tag}: {c['id']} recording diverges from the reference at "
            f"entry {idx} (got {obs[idx]!r}, expected {ref_obs[idx]!r})")
    ref_ll, _, ref_n = hmmref.solve_case(c)
    assert math.isfinite(loglik), f"{tag}: {c['id']} loglik not finite ({loglik!r})"
    assert abs(loglik - ref_ll) <= TOL_LL_REL * (abs(ref_ll) + 1.0), (
        f"{tag}: {c['id']} loglik {loglik!r} vs ref {ref_ll!r} "
        f"(diff {abs(loglik - ref_ll):.3g})")
    assert math.isfinite(nseg), f"{tag}: {c['id']} nseg not finite ({nseg!r})"
    assert abs(nseg - ref_n) <= TOL_NSEG_REL * (abs(ref_n) + 1.0), (
        f"{tag}: {c['id']} nseg {nseg!r} vs ref {ref_n!r} "
        f"(diff {abs(nseg - ref_n):.3g})")


def compare(cases, results, order, tag):
    got_ids = list(order)
    exp_ids = [c["id"] for c in cases]
    assert got_ids == exp_ids, (
        f"{tag}: case id/order mismatch: {got_ids[:5]} vs {exp_ids[:5]}")
    for c in cases:
        check_case(c, results, tag)


def lik_gap(c, res):
    """Max deviation of a wrong-likelihood result from the exact reference."""
    ref_ll, ref_g, ref_n = hmmref.solve_case(c)
    ll, g, n = res
    if not (math.isfinite(ll) and math.isfinite(n)):
        return float("inf")
    dll = abs(ll - ref_ll) / (abs(ref_ll) + 1.0)
    dn = abs(n - ref_n) / (abs(ref_n) + 1.0)
    dg = 0.0
    for t in range(c["T"]):
        for i in range(c["N"]):
            gv = g[t][i]
            if not math.isfinite(gv):
                return float("inf")
            dg = max(dg, abs(gv - ref_g[t][i]))
    return max(dll, dn, dg)


def _shipped_results():
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "o.txt")
        results, _ = run_on(CASES, out)
    return results


def _discriminate_sampler(sampler, min_count, tag):
    """Assert the deliverable matches the reference on every shipped case
    where the given wrong consumption convention desyncs the recording."""
    cases = hmmref.parse_cases(CASES)
    results = _shipped_results()
    discriminating = 0
    for c in cases:
        if sampler(c) == hmmref.reference_obs(c):
            continue
        discriminating += 1
        check_case(c, results, tag)
    assert discriminating >= min_count, (
        f"too few {tag}-desynced cases: {discriminating}")


def _discriminate_likelihood(solver, min_count, tag):
    """Assert the deliverable matches the reference on every shipped case
    where the given wrong likelihood model is materially wrong."""
    cases = hmmref.parse_cases(CASES)
    results = _shipped_results()
    discriminating = 0
    for c in cases:
        if lik_gap(c, solver(c)) < WRONG:
            continue
        discriminating += 1
        check_case(c, results, tag)
    assert discriminating >= min_count, (
        f"too few {tag}-wrong cases: {discriminating}")


class TestRecordingReplay:
    def test_binary_is_native_go(self):
        """The deliverable is a compiled native ELF binary at /app/hmm that does
        the work itself, not a script delegating to an interpreter."""
        assert os.path.exists(BIN), f"{BIN} does not exist"
        assert os.access(BIN, os.X_OK), f"{BIN} is not executable"
        with open(BIN, "rb") as f:
            blob = f.read()
        assert blob[:2] != b"#!", f"{BIN} is a script, not a compiled binary"
        assert blob[:4] == b"\x7fELF", f"{BIN} is not a native ELF binary"
        low = blob.lower()
        # Tokens that never appear in a stdlib-only Go binary but would surface
        # if the solver bundled or invoked an interpreter/numeric stack. (Bare
        # ".py"/".rb"/".jl" are deliberately excluded: Go's own runtime symbol
        # table embeds strings like "runtime-gdb.py" and "sigctxt).rbx".)
        for tok in (b"python", b"/usr/bin/python", b"perl", b"/usr/bin/perl",
                    b"julia", b"/node", b"numpy", b"scipy"):
            assert tok not in low, (
                f"binary references {tok!r}; it must not delegate to an interpreter")

    def test_deliverable_is_not_the_probe_reference(self):
        """/app/hmm is the agent's own solver, not a copy of the probe
        reference, and the probe's T cap means a wrapper around it cannot
        produce the graded long-recording results either."""
        assert os.path.exists(REF), f"{REF} does not exist"
        with open(BIN, "rb") as fa, open(REF, "rb") as fb:
            assert fa.read() != fb.read(), (
                "/app/hmm is byte-identical to the probe reference /app/ref")

    def test_source_does_not_shell_out(self):
        """Any Go source under /app must do the work itself: it must not
        invoke another program (os/exec, syscall exec) to compute the
        results."""
        srcs = []
        for root, dirs, files in os.walk(APP):
            dirs[:] = [d for d in dirs if d not in ("data", "docs", "output")]
            for fn in files:
                if fn.endswith(".go"):
                    srcs.append(os.path.join(root, fn))
        if srcs:
            raw = "\n".join(open(p, encoding="utf-8", errors="replace").read()
                            for p in srcs)
            src = re.sub(r"//[^\n]*", "", raw)
            src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL).lower()
            for tok in ("os/exec", "exec.command", "syscall.exec",
                        "os/exec\"", "\"os/exec\""):
                assert tok not in src, (
                    f"source shells out ({tok!r}); it must be native Go")

    def test_output_schema_default_run(self):
        """Running /app/hmm with no arguments writes /app/output/results.txt
        with the CASE/O/LOGLIK/NSEG/END schema, one block per shipped case in
        order, echoing each id, with exactly T recording entries."""
        cases = hmmref.parse_cases(CASES)
        results, order = run_default()
        assert order == [c["id"] for c in cases], "case id/order mismatch"
        for c in cases:
            obs, loglik, nseg = results[c["id"]]
            assert len(obs) == c["T"]
            for o in obs:
                assert o == hmmref.MISSING or 0 <= o < c["K"]
            assert isinstance(loglik, float)
            assert isinstance(nseg, float)
            assert 1.0 - 1e-6 <= nseg <= c["T"] + 1e-6, (
                f"{c['id']} nseg {nseg!r} outside [1, T]")

    def test_shipped_cases_match_reference(self):
        """Every shipped case reproduces the reference recording
        entry-for-entry and its log-likelihood and expected visit count to
        tolerance (all-or-nothing across the whole result)."""
        cases = hmmref.parse_cases(CASES)
        results = _shipped_results()
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "o.txt")
            results, order = run_on(CASES, out)
        compare(cases, results, order, "shipped")

    def test_fixture_regimes_present(self):
        """The shipped fixture genuinely exercises the model: many long
        recordings, probe-sized cases, recordings with missing entries, a
        dwell cap of 1, a single-step recording, a heavy-missingness case, an
        all-zero M row, and states with a minimum duration."""
        cases = hmmref.parse_cases(CASES)
        assert len(cases) >= 20, f"fixture has only {len(cases)} cases"
        longs = [c for c in cases if c["T"] >= LONG_T]
        assert len(longs) >= 10, f"too few long cases: {len(longs)}"
        assert max(c["T"] for c in cases) >= 2500, "no sufficiently long case"
        probes = [c for c in cases if c["T"] <= PROBE_T]
        assert len(probes) >= 8, f"too few probe-sized cases: {len(probes)}"
        miss = [c for c in cases
                if hmmref.MISSING in hmmref.reference_obs(c)]
        assert len(miss) >= 15, f"too few recordings with '?': {len(miss)}"
        assert any(c["Dmax"] == 1 for c in cases), "no dwell-cap-1 case"
        assert any(c["T"] == 1 for c in cases), "no single-step case"
        assert any(min(c["M"]) >= 0.5 for c in cases), "no heavy-missing case"
        assert any(all(m == 0.0 for m in c["M"]) for c in cases), (
            "no all-zero-M case")
        assert any(any(row[0] == 0.0 for row in c["D"]) for c in cases), (
            "no minimum-duration case")

    def test_discriminate_miss_draw_order(self):
        """Taking the missingness draw before the symbol draw desyncs the
        recording stream; the solver must match the reference on every case
        where it does."""
        _discriminate_sampler(hmm_naive.sample_miss_first, 18, "miss-first")

    def test_discriminate_lazy_symbol_draw(self):
        """Drawing the symbol only when the entry is shown (skipping the
        masked draws) desyncs the recording stream; the solver must match the
        reference on every case where it does."""
        _discriminate_sampler(hmm_naive.sample_miss_first_lazy, 18,
                              "lazy-symbol")

    def test_discriminate_fresh_start_sampler(self):
        """Starting the first visit at step 1 with a plain duration draw,
        instead of the window-opening draws, desyncs the recording stream from
        the very first entries."""
        _discriminate_sampler(hmm_naive.sample_fresh_start, 18, "fresh-sampler")

    def test_discriminate_no_lag_sampler(self):
        """Generating each entry from the state at its own step, ignoring the
        apparatus lag, desyncs the recording stream."""
        _discriminate_sampler(hmm_naive.sample_no_lag, 15, "no-lag-sampler")

    def test_discriminate_per_step_hazard_sampler(self):
        """Redrawing a hazard uniform at every occupied step, instead of
        drawing each visit's total duration once, consumes a different draw
        stream and desyncs the recording."""
        _discriminate_sampler(hmm_naive.sample_per_step_hazard, 18,
                              "per-step-hazard")

    def test_discriminate_underflow(self):
        """On the long recordings the correct likelihood carried in the raw
        probability domain underflows to -inf / NaN, while the solver must
        report finite values matching the exact reference."""
        cases = hmmref.parse_cases(CASES)
        results = _shipped_results()
        discriminating = 0
        for c in cases:
            if c["T"] < LONG_T:
                continue
            obs = hmmref.reference_obs(c)
            nll, ng, nn = hmm_naive.solve_obs_linear(c, obs)
            dead = (not math.isfinite(nll)) or any(
                not math.isfinite(ng[t][i])
                for t in range(c["T"]) for i in range(c["N"]))
            if not dead:
                continue
            discriminating += 1
            check_case(c, results, "underflow")
        assert discriminating >= 8, (
            f"too few underflow cases exercised: {discriminating}")

    def test_discriminate_wrong_likelihood_models(self):
        """Evaluating the recording under textbook conventions instead of the
        reference's (fresh start, missingness ignored, no lag, their
        composite, or an ordinary HMM without durations) lands far outside
        tolerance; the solver must match the exact reference there."""
        _discriminate_likelihood(hmm_naive.solve_case_fresh_start, 8, "fresh")
        _discriminate_likelihood(hmm_naive.solve_case_ignore_m, 8, "ignore-M")
        _discriminate_likelihood(hmm_naive.solve_case_no_lag, 8, "ignore-lag")
        _discriminate_likelihood(hmm_naive.solve_case_textbook, 12, "textbook")
        _discriminate_likelihood(hmm_naive.solve_case_memoryless, 12,
                                 "memoryless")

    def test_live_holdout_matches_reference(self):
        """Freshly generated cases (unseen parameters and seeds, spanning the
        probe, medium, long and corner-class regimes) must match the exact
        reference, so results cannot be pre-baked to the shipped inputs."""
        with tempfile.TemporaryDirectory() as td:
            for seed in HOLDOUT_SEEDS:
                cases = holdout_gen.gen_cases(seed)
                inp = os.path.join(td, f"in{seed}.txt")
                out = os.path.join(td, f"out{seed}.txt")
                write_cases(cases, inp)
                results, order = run_on(inp, out)
                compare(cases, results, order, f"holdout-{seed}")

    def test_holdout_discriminates_naive(self):
        """The held-out cases themselves separate the reference semantics from
        the wrong models: fresh cases where each wrong consumption convention
        desyncs, where the textbook likelihood is far outside tolerance, and
        where raw-probability arithmetic dies."""
        cases = holdout_gen.gen_cases(HOLDOUT_SEEDS[0])
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "in.txt")
            out = os.path.join(td, "out.txt")
            write_cases(cases, inp)
            results, _ = run_on(inp, out)
        counts = {"miss-first": 0, "lazy-symbol": 0, "fresh-sampler": 0,
                  "no-lag-sampler": 0, "per-step-hazard": 0,
                  "textbook": 0, "underflow": 0}
        for c in cases:
            for tag, sampler in (
                    ("miss-first", hmm_naive.sample_miss_first),
                    ("lazy-symbol", hmm_naive.sample_miss_first_lazy),
                    ("fresh-sampler", hmm_naive.sample_fresh_start),
                    ("no-lag-sampler", hmm_naive.sample_no_lag),
                    ("per-step-hazard", hmm_naive.sample_per_step_hazard)):
                if sampler(c) != hmmref.reference_obs(c):
                    counts[tag] += 1
                    check_case(c, results, f"holdout-{tag}")
            if lik_gap(c, hmm_naive.solve_case_textbook(c)) >= WRONG:
                counts["textbook"] += 1
                check_case(c, results, "holdout-textbook")
            if c["T"] >= LONG_T:
                obs = hmmref.reference_obs(c)
                nll, ng, nn = hmm_naive.solve_obs_linear(c, obs)
                if (not math.isfinite(nll)) or any(
                        not math.isfinite(ng[t][i])
                        for t in range(c["T"]) for i in range(c["N"])):
                    counts["underflow"] += 1
                    check_case(c, results, "holdout-underflow")
        assert counts["miss-first"] >= 9, counts
        assert counts["lazy-symbol"] >= 9, counts
        assert counts["fresh-sampler"] >= 9, counts
        assert counts["no-lag-sampler"] >= 6, counts
        assert counts["per-step-hazard"] >= 9, counts
        assert counts["textbook"] >= 10, counts
        assert counts["underflow"] >= 2, counts

    def test_determinism_byte_identical_rerun(self):
        """Two runs on identical input produce byte-identical output."""
        with tempfile.TemporaryDirectory() as td:
            a = os.path.join(td, "a.txt")
            b = os.path.join(td, "b.txt")
            run_on(CASES, a)
            run_on(CASES, b)
            with open(a, "rb") as fa, open(b, "rb") as fb:
                assert fa.read() == fb.read(), "output changed across identical runs"

    def test_input_sensitivity(self):
        """Changing the SEED changes the recording, and the solver still
        matches the reference on the perturbed case, so the output reflects
        the actual seed and parameters rather than anything pre-baked."""
        base = holdout_gen.gen_cases(HOLDOUT_SEEDS[1])
        target = next(c for c in base if 40 <= c["T"] < LONG_T)
        mut = dict(target)
        mut["seed"] = (target["seed"] + 1) & ((1 << 64) - 1)
        assert hmmref.reference_obs(target) != hmmref.reference_obs(mut), (
            "fixture defect: seed flip did not change the recording")
        with tempfile.TemporaryDirectory() as td:
            paths = {}
            for name, c in (("base", target), ("mut", mut)):
                i_p = os.path.join(td, f"{name}.txt")
                o_p = os.path.join(td, f"{name}_o.txt")
                write_cases([c], i_p)
                paths[name] = run_on(i_p, o_p)[0]
        check_case(target, paths["base"], "sens-base")
        check_case(mut, paths["mut"], "sens-mut")
        obs0, ll0, _ = paths["base"][target["id"]]
        obs1, ll1, _ = paths["mut"][mut["id"]]
        assert obs0 != obs1, "recording ignored the seed"
