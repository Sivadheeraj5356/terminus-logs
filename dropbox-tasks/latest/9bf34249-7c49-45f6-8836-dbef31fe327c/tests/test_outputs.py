import itertools
import subprocess
from pathlib import Path


ROOT = Path("/opt/cnfprep")
BIN = ROOT / "bin" / "cnfprep"


def parse_cnf(path):
    header = None
    nums = []
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("c"):
            continue
        parts = line.split()
        if parts[0] == "p":
            header = (int(parts[2]), int(parts[3]))
        else:
            nums.extend(int(x) for x in parts)
    clauses = []
    cur = []
    for x in nums:
        if x == 0:
            clauses.append(cur)
            cur = []
        else:
            cur.append(x)
    assert header is not None
    assert header[1] == len(clauses)
    return header[0], clauses


def write_cnf(path, nvars, clauses):
    body = [f"p cnf {nvars} {len(clauses)}"]
    body.extend(" ".join(map(str, clause + [0])) for clause in clauses)
    Path(path).write_text("\n".join(body) + "\n")


def sat_clause(model, clause):
    return any(model[abs(lit)] == (lit > 0) for lit in clause)


def sat_formula(model, clauses):
    return all(sat_clause(model, clause) for clause in clauses)


def assignments(vars_):
    vars_ = sorted(vars_)
    for values in itertools.product([False, True], repeat=len(vars_)):
        yield dict(zip(vars_, values))


def parse_model(path):
    out = {}
    for raw in Path(path).read_text().splitlines():
        if not raw.strip():
            continue
        left, right = raw.replace(" ", "").split("=", 1)
        out[int(left)] = right in {"1", "true", "True"}
    return out


def run_case(tmp_path, name, clauses, nvars):
    inp = tmp_path / f"{name}.cnf"
    out = tmp_path / f"{name}.out.cnf"
    log = tmp_path / f"{name}.audit"
    mapp = tmp_path / f"{name}.map"
    write_cnf(inp, nvars, clauses)
    subprocess.run(["make", "-C", str(ROOT), "clean", "all"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run([str(BIN), str(inp), "--out", str(out), "--log", str(log), "--map", str(mapp)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return inp, out, log, mapp


def vars_in(clauses):
    return {abs(lit) for clause in clauses for lit in clause}


def assert_structural_outputs(out, log, mapp, nvars):
    on, oclauses = parse_cnf(out)
    assert on == nvars
    for clause in oclauses:
        assert len(clause) == len(set(clause))
        assert not any(-lit in clause for lit in clause)
    lines = [line.strip() for line in Path(log).read_text().splitlines() if line.strip()]
    allowed = {"input", "assign", "drop", "derive", "emit"}
    assert lines
    assert all(line.split()[0] in allowed for line in lines)
    emitted = [tuple(int(x) for x in line.split()[1:-1]) for line in lines if line.startswith("emit ")]
    assert sorted(emitted) == sorted(tuple(c) for c in oclauses)
    mlines = [line.split() for line in Path(mapp).read_text().splitlines() if line.strip()]
    assert [row for row in mlines if row[:1] == ["n"]] == [["n", str(nvars)]]
    remaining = sorted(int(row[1]) for row in mlines if row[:1] == ["r"])
    assert remaining == sorted(vars_in(oclauses))
    return oclauses, remaining


def assert_no_more_simple_steps(clauses):
    if clauses == [[]]:
        return
    assert not any(len(clause) == 0 for clause in clauses)
    assert not any(len(clause) == 1 for clause in clauses)
    all_lits = {lit for clause in clauses for lit in clause}
    assert not any(-lit not in all_lits for lit in all_lits)
    sets = [set(clause) for clause in clauses]
    for i, left in enumerate(sets):
        for j, right in enumerate(sets):
            if i != j:
                assert not left < right
    for c in clauses:
        for d in clauses:
            for lit in c:
                if -lit in d and set(c) - {lit} <= set(d):
                    raise AssertionError("reducible clause pair remains")
    for var in sorted(vars_in(clauses)):
        pos = [c for c in clauses if var in c]
        neg = [c for c in clauses if -var in c]
        if pos and neg:
            resolvents = []
            for p in pos:
                for q in neg:
                    r = set(p) - {var}
                    r |= set(q) - {-var}
                    if any(-lit in r for lit in r):
                        continue
                    resolvents.append(tuple(sorted(r, key=lambda x: (abs(x), x < 0))))
            if len(set(resolvents)) <= len(pos) + len(neg):
                raise AssertionError("bounded reduction remains")


def assert_equivalence_and_extension(inp, out, mapp, original_clauses):
    nvars, out_clauses = parse_cnf(out)
    out_vars = sorted(vars_in(out_clauses))
    original_sat = []
    for partial in assignments(range(1, nvars + 1)):
        if sat_formula(partial, original_clauses):
            original_sat.append(partial)
            projected = {var: partial[var] for var in out_vars}
            assert sat_formula(projected, out_clauses)
    simplified_models = [m for m in assignments(out_vars) if sat_formula(m, out_clauses)]
    assert bool(original_sat) == bool(simplified_models)
    for idx, model in enumerate(simplified_models[:16]):
        partial_path = Path(out).with_suffix(f".{idx}.partial")
        full_path = Path(out).with_suffix(f".{idx}.full")
        partial_path.write_text("".join(f"{v}={1 if model[v] else 0}\n" for v in out_vars))
        subprocess.run([str(BIN), "--extend", str(inp), "--map", str(mapp), "--model", str(partial_path), "--model-out", str(full_path)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        full = parse_model(full_path)
        assert sorted(full) == list(range(1, nvars + 1))
        for var in out_vars:
            assert full[var] == model[var]
        assert sat_formula(full, original_clauses)


def test_reduction_outputs_are_canonical_enough(tmp_path):
    """The generated files are syntactically consistent and fully reduced for a mixed satisfiable instance."""
    clauses = [
        [1, 2], [-1, 3], [-2, -3], [2, 4], [-4, 3],
        [5, -5, 2], [1, 2, 2], [-1, 2, 4], [-3, 4, 6], [-6, -2]
    ]
    inp, out, log, mapp = run_case(tmp_path, "case_a", clauses, 6)
    reduced, _ = assert_structural_outputs(out, log, mapp, 6)
    assert_no_more_simple_steps(reduced)
    assert_equivalence_and_extension(inp, out, mapp, clauses)


def test_extension_handles_a_dense_projection(tmp_path):
    """A model of the reduced formula can be lifted back while preserving visible assignments."""
    clauses = [
        [1, 2, 3], [-1, 2], [1, -2], [-1, -2, 4], [-4, 3],
        [-3, 5], [-5, 6], [5, -6], [-6, -2], [4, -5, 7], [-7, 3]
    ]
    inp, out, log, mapp = run_case(tmp_path, "case_b", clauses, 7)
    reduced, _ = assert_structural_outputs(out, log, mapp, 7)
    assert_no_more_simple_steps(reduced)
    assert_equivalence_and_extension(inp, out, mapp, clauses)


def test_conflicting_instance_has_a_consistent_certificate(tmp_path):
    """An inconsistent input is represented by a single empty clause and a matching audit record."""
    clauses = [[1], [-1, 2], [-2, 3], [-3, 4], [-4, 5], [-5, 6], [-6]]
    inp, out, log, mapp = run_case(tmp_path, "case_c", clauses, 6)
    reduced, _ = assert_structural_outputs(out, log, mapp, 6)
    assert reduced == [[]]
    assert_equivalence_and_extension(inp, out, mapp, clauses)


def test_comments_and_irregular_clause_text_do_not_change_semantics(tmp_path):
    """The parser accepts ordinary DIMACS spacing while preserving the required behavior."""
    inp = tmp_path / "case_d.cnf"
    clauses = [[1, -2], [-1, 2], [2, 3], [-3, 4], [-4, -2], [5, -5, 1], [1, -2, 4]]
    inp.write_text("c generated fixture\np cnf 5 7\n1 -2 0\n-1 2 0\n2 3 0\n-3 4 0\n-4 -2 0\n5 -5 1 0\n1 -2 4 0\n")
    out = tmp_path / "case_d.out.cnf"
    log = tmp_path / "case_d.audit"
    mapp = tmp_path / "case_d.map"
    subprocess.run(["make", "-C", str(ROOT), "clean", "all"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run([str(BIN), str(inp), "--out", str(out), "--log", str(log), "--map", str(mapp)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    reduced, _ = assert_structural_outputs(out, log, mapp, 5)
    assert_no_more_simple_steps(reduced)
    assert_equivalence_and_extension(inp, out, mapp, clauses)
