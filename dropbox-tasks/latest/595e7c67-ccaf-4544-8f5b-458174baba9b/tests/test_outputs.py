import glob
import importlib.util
import os
import shutil
import subprocess
import tempfile

APP = "/app"
GOLDEN = "/tests/golden"
NAIVE_SRC = os.path.join(GOLDEN, "naive_ref", "src")
VARIANTS = os.path.join(GOLDEN, "variants")

_spec = importlib.util.spec_from_file_location(
    "reference", os.path.join(GOLDEN, "reference.py")
)
reference = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reference)


def _gcc_build(src_dir, out_name):
    sources = sorted(glob.glob(os.path.join(src_dir, "*.cpp")))
    assert sources, f"no C++ sources found under {src_dir}"
    binary = os.path.join(tempfile.mkdtemp(prefix="bin_"), out_name)
    cmd = ["g++", "-std=c++17", "-O2", "-o", binary] + sources
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"build failed in {src_dir}:\n{proc.stderr}"
    assert os.path.isfile(binary), f"binary missing after build in {src_dir}"
    return binary


def _build_agent():
    src = os.path.join(APP, "src")
    assert os.path.isdir(src), "agent source tree /app/src is missing"
    return _gcc_build(src, "foldc_agent")


def _build_naive():
    work = tempfile.mkdtemp(prefix="naive_")
    dst = os.path.join(work, "src")
    shutil.copytree(NAIVE_SRC, dst)
    return _gcc_build(dst, "foldc_naive")


_VARIANT_CACHE = {}


def _build_variant(cpp_name):
    if cpp_name in _VARIANT_CACHE:
        return _VARIANT_CACHE[cpp_name]
    src = os.path.join(VARIANTS, cpp_name)
    assert os.path.isfile(src), f"variant source {src} is missing"
    work = tempfile.mkdtemp(prefix="variant_")
    dst = os.path.join(work, "src")
    shutil.copytree(NAIVE_SRC, dst)
    shutil.copyfile(src, os.path.join(dst, "folder.cpp"))
    binary = _gcc_build(dst, "foldc_variant")
    _VARIANT_CACHE[cpp_name] = binary
    return binary


AGENT = _build_agent()
NAIVE = _build_naive()


def _run(binary, program):
    proc = subprocess.run(
        [binary], input=program, capture_output=True, text=True, timeout=30
    )
    return proc.stdout, proc.returncode


def _agent_ast(program):
    out, rc = _run(AGENT, program)
    assert rc == 0, f"agent exit {rc} on {program!r}: {out!r}"
    return reference.canon_of_output(out)


def check(program):
    got = _agent_ast(program)
    want = reference.expected(program)
    assert got == want, f"{program!r}: got {got} want {want}"


def check_top(program, kind):
    got = _agent_ast(program)
    want = reference.expected(program)
    assert got == want, f"{program!r}: got {got} want {want}"
    assert got[0] == kind, f"{program!r}: top {got[0]} want {kind}"


def check_naive_differs(program):
    out, _ = _run(NAIVE, program)
    naive = reference.canon_of_output(out)
    want = reference.expected(program)
    assert naive != want, f"{program!r}: naive matched the intended fold {want}"


def check_variant_rejected(cpp_name, program):
    binary = _build_variant(cpp_name)
    out, rc = _run(binary, program)
    assert rc == 0, f"{cpp_name} exit {rc} on {program!r}: {out!r}"
    variant = reference.canon_of_output(out)
    want = reference.expected(program)
    assert variant != want, (
        f"{cpp_name} matched the intended fold on {program!r}: {want}"
    )
    agent = _agent_ast(program)
    assert agent == want, f"{program!r}: agent {agent} want {want}"


def test_cf_precedence():
    """multiplication binds tighter than addition when folding constants"""
    check("2.0 + 3.0 * 4.0")


def test_cf_parentheses():
    """parentheses override precedence in constant folding"""
    check("(1.0 + 2.0) * (3.0 + 4.0)")


def test_cf_sub_left_assoc():
    """subtraction folds left associatively"""
    check("10.0 - 3.0 - 2.0")


def test_cf_div_left_assoc():
    """division folds left associatively"""
    check("100.0 / 4.0 / 5.0")


def test_cf_unary_literal():
    """a unary minus on a literal folds into a negative constant"""
    check("-5.0 + 2.0")


def test_cf_mul_negative_literal():
    """multiplying by a negative literal folds to a negative constant"""
    check("2.0 * -3.0")


def test_cf_fraction():
    """exact halving folds to a fractional constant"""
    check("1.0 / 2.0")


def test_cf_deep_nest():
    """deeply nested constant additions fold to one constant"""
    check("((1.0 + 2.0) + 3.0) + 4.0")


def test_cf_mixed_ops():
    """a mix of the four operators folds to one constant"""
    check("3.0 * 4.0 - 2.0 / 4.0")


def test_cf_exponent_literal():
    """scientific-notation literals participate in folding"""
    check("1e3 + 1.0")


def test_sp_div_zero_pos():
    """dividing a positive constant by zero folds to positive infinity"""
    check("1.0 / 0.0")


def test_sp_div_zero_neg():
    """dividing a negative constant by zero folds to negative infinity"""
    check("-1.0 / 0.0")


def test_sp_zero_over_zero():
    """zero over zero folds to nan"""
    check("0.0 / 0.0")


def test_sp_div_by_neg_zero():
    """dividing by negative zero flips the infinity sign"""
    check("1.0 / -0.0")


def test_sp_neg_zero_product():
    """a negative times positive zero folds to negative zero"""
    check("-3.0 * 0.0")


def test_sp_pos_zero_product():
    """a positive times positive zero folds to positive zero"""
    check("3.0 * 0.0")


def test_sp_overflow_to_inf():
    """an overflowing sum folds to infinity"""
    check("1e308 + 1e308")


def test_sp_inf_minus_inf():
    """infinity minus infinity folds to nan"""
    check("inf - inf")


def test_sp_inf_times_zero():
    """infinity times zero folds to nan"""
    check("inf * 0.0")


def test_sp_self_subtraction_const():
    """subtracting equal finite constants folds to positive zero"""
    check("3.0 - 3.0")


def test_sf_mul_one_right():
    """multiplying a variable by one on the right drops the one"""
    check("x * 1.0")


def test_sf_mul_one_left():
    """multiplying a variable by one on the left drops the one"""
    check("1.0 * x")


def test_sf_div_one():
    """dividing a variable by one drops the one"""
    check("x / 1.0")


def test_sf_sub_pos_zero():
    """subtracting positive zero from a variable drops the zero"""
    check("x - 0.0")


def test_sf_add_neg_zero_right():
    """adding negative zero on the right drops the zero"""
    check("x + -0.0")


def test_sf_add_neg_zero_left():
    """adding negative zero on the left drops the zero"""
    check("-0.0 + x")


def test_sf_double_negation():
    """a double negation of a variable collapses"""
    check("-(-x)")


def test_sf_nested_units():
    """chained multiplicative units all drop"""
    check("(a * 1.0) / 1.0")


def test_sf_units_over_sum():
    """unit multipliers drop under an addition"""
    check("x * 1.0 + y * 1.0")


def test_sf_double_neg_in_sum():
    """a double negation drops inside a larger sum"""
    check("-(-a) + b")


def test_uf_add_pos_zero_right():
    """adding positive zero on the right must not be folded away"""
    check_top("x + 0.0", "add")


def test_uf_add_pos_zero_left():
    """adding positive zero on the left must not be folded away"""
    check_top("0.0 + x", "add")


def test_uf_sub_neg_zero():
    """subtracting negative zero must not be folded away"""
    check_top("x - -0.0", "sub")


def test_uf_mul_zero_right():
    """multiplying a variable by zero must not collapse to zero"""
    check_top("x * 0.0", "mul")


def test_uf_mul_zero_left():
    """zero times a variable must not collapse to zero"""
    check_top("0.0 * x", "mul")


def test_uf_mul_neg_zero():
    """multiplying a variable by negative zero must not collapse"""
    check_top("x * -0.0", "mul")


def test_uf_self_subtraction():
    """subtracting a variable from itself must not collapse to zero"""
    check_top("x - x", "sub")


def test_uf_self_division():
    """dividing a variable by itself must not collapse to one"""
    check_top("x / x", "div")


def test_uf_zero_minus_var():
    """positive zero minus a variable must not become a negation"""
    check_top("0.0 - x", "sub")


def test_uf_add_pos_zero_naive_differs():
    """the naive reading folds positive-zero addition and diverges"""
    check_naive_differs("x + 0.0")


def test_uf_sub_neg_zero_naive_differs():
    """the naive reading folds negative-zero subtraction and diverges"""
    check_naive_differs("x - -0.0")


def test_uf_mul_zero_naive_differs():
    """the naive reading collapses a zero product and diverges"""
    check_naive_differs("x * 0.0")


def test_uf_self_sub_naive_differs():
    """the naive reading collapses self subtraction and diverges"""
    check_naive_differs("x - x")


def test_uf_zero_minus_var_naive_differs():
    """the naive reading rewrites zero-minus-variable and diverges"""
    check_naive_differs("0.0 - x")


def test_ix_safe_then_unsafe():
    """a unit fold that exposes a positive-zero addition leaves it intact"""
    check("(x * 1.0) + 0.0")


def test_ix_unsafe_then_unit():
    """a surviving positive-zero addition keeps its shape under a unit drop"""
    check("(x + 0.0) * 1.0")


def test_ix_const_zero_feeds_mul():
    """a folded positive zero under a product is not collapsed"""
    check("x * (3.0 - 3.0)")


def test_ix_const_neg_zero_feeds_sub():
    """a folded negative zero under a subtraction stays unfolded"""
    check("x - (-2.0 * 0.0)")


def test_ix_const_pos_zero_feeds_sub():
    """a folded positive zero subtracted from a variable drops"""
    check("x - (2.0 * 0.0)")


def test_ix_const_pos_zero_feeds_add():
    """a folded positive zero added to a variable stays"""
    check("y + (0.0 - 0.0)")


def test_ix_mul_one_reveals_zero_product():
    """mixed unit and zero folds keep only the value-preserving parts"""
    check("(a + 0.0) * 1.0 + b * 0.0")


def test_ix_double_neg_over_kept_add():
    """a double negation over a kept addition collapses only the negation"""
    check("-(-(x + 0.0))")


def test_ix_naive_differs_compound():
    """the naive reading over-folds the compound program"""
    check_naive_differs("(a + 0.0) * 1.0 + b * 0.0")


def test_gen_add_pos_zero_names():
    """positive-zero addition stays unfolded across many variable names"""
    for name in ["q0", "foo", "bar_baz", "alpha", "z9", "long_variable_name"]:
        check(f"{name} + 0.0")


def test_gen_sub_neg_zero_names():
    """negative-zero subtraction stays unfolded across many names"""
    for name in ["p", "w2", "input_val", "gamma", "k_9"]:
        check(f"{name} - -0.0")


def test_gen_safe_units_names():
    """value-preserving unit drops apply across many names"""
    for name in ["p", "w2", "input_val", "gamma", "k_9"]:
        check(f"{name} * 1.0")
        check(f"{name} / 1.0")
        check(f"{name} - 0.0")
        check(f"{name} + -0.0")


def test_gen_zero_products_names():
    """zero products stay unfolded across many names"""
    for name in ["m", "n3", "rate", "delta_t"]:
        check(f"{name} * 0.0")
        check(f"0.0 * {name}")


def test_gen_composed_programs():
    """a fixed sweep of composed programs matches the reference exactly"""
    lefts = ["u", "v", "w"]
    tails = ["+ 0.0", "+ -0.0", "- 0.0", "- -0.0", "* 1.0", "* 0.0", "/ 1.0"]
    for lft in lefts:
        for tail in tails:
            check(f"({lft} * 1.0) {tail}")


def test_gen_nested_zero_from_constants():
    """zeros produced by constant folding keep their sign in later folds"""
    check("k + (5.0 - 5.0)")
    check("k + (0.0 * -1.0)")
    check("k - (0.0 * -1.0)")
    check("k - (5.0 - 5.0)")


def test_schema_variable_passthrough():
    """a lone variable folds to itself"""
    check("solo")


def test_schema_kept_binary_reparses():
    """a kept binary node round-trips through the canonical printer"""
    got = _agent_ast("aa * bb + cc")
    want = reference.expected("aa * bb + cc")
    assert got == want


def test_ra_adjacent_constants_fold():
    """two adjacent constant operands still fold to one constant"""
    check("1.0 + 2.0 + x")


def test_ra_adjacent_product_folds():
    """two adjacent constant factors still fold to one constant"""
    check("2.0 * 3.0 * x")


def test_ra_nonadjacent_add_kept():
    """a variable between the constants blocks combining them across a sum"""
    check_top("(x + 1.0) + 2.0", "add")


def test_ra_nonadjacent_mul_kept():
    """a variable between the constants blocks combining them across a product"""
    check_top("(x * 2.0) * 3.0", "mul")


def test_ra_add_chain_kept():
    """a left-associated additive chain keeps its trailing constant separate"""
    check_top("x + 1.0 + 2.0", "add")


def test_ra_mul_chain_kept():
    """a left-associated multiplicative chain keeps its trailing factor separate"""
    check_top("a * 2.0 * 4.0", "mul")


def test_ra_add_naive_differs():
    """the naive reading reassociates the additive constants and diverges"""
    check_naive_differs("(x + 1.0) + 2.0")


def test_ra_mul_naive_differs():
    """the naive reading reassociates the multiplicative constants and diverges"""
    check_naive_differs("(x * 2.0) * 3.0")


def test_ra_gen_names():
    """constant reassociation stays blocked across many variable names"""
    for name in ["p", "w2", "input_val", "gamma", "k_9"]:
        check(f"({name} + 1.0) + 2.0")
        check(f"({name} * 2.0) * 3.0")


def test_ra_overflow_boundary():
    """combining large additive constants around a variable is refused"""
    check_top("(x + 1e308) + 1e308", "add")


def test_anti_cheat_no_test_paths_in_source():
    """the agent source does not read the hidden battery or golden tree"""
    for path in glob.glob(os.path.join(APP, "src", "*")):
        with open(path, encoding="utf-8", errors="ignore") as f:
            text = f.read()
        assert "/tests" not in text, f"{path} references the tests tree"
        assert "golden" not in text, f"{path} references the golden tree"


def test_anti_cheat_fresh_program():
    """a freshly composed program with unseen names matches the reference"""
    prog = "((zeta + 0.0) * 1.0) - (theta - theta) + (mu * -0.0)"
    check(prog)
    check_naive_differs(prog)


def test_variant_signzero_rejects_zero_product():
    """fixing signed-zero identities alone still wrongly collapses a zero product"""
    check_variant_rejected("partial_signzero.cpp", "x * 0.0")


def test_variant_signzero_rejects_self_subtraction():
    """fixing signed-zero identities alone still wrongly collapses self subtraction"""
    check_variant_rejected("partial_signzero.cpp", "x - x")


def test_variant_signzero_rejects_self_division():
    """fixing signed-zero identities alone still wrongly collapses self division"""
    check_variant_rejected("partial_signzero.cpp", "x / x")


def test_variant_signzero_rejects_reassociation():
    """fixing signed-zero identities alone still wrongly reassociates constants"""
    check_variant_rejected("partial_signzero.cpp", "(x + 1.0) + 2.0")


def test_variant_zeroprod_rejects_pos_zero_add():
    """keeping zero products alone still wrongly drops a positive-zero addition"""
    check_variant_rejected("partial_zeroprod.cpp", "x + 0.0")


def test_variant_zeroprod_rejects_neg_zero_sub():
    """keeping zero products alone still wrongly drops a negative-zero subtraction"""
    check_variant_rejected("partial_zeroprod.cpp", "x - -0.0")


def test_variant_zeroprod_rejects_compound():
    """the zero-product-only fix still diverges on a compound program"""
    check_variant_rejected("partial_zeroprod.cpp", "(a + 0.0) * b - (c - -0.0)")
