"""Conformance tests for the RFC 6570 URI Template expansion tool in /app.

The tool reads a JSON object ``{"template": ..., "variables": ...}`` on stdin
and prints the expanded string on stdout, or prints ``ERROR`` and exits
non-zero for a malformed template. These tests build the binary once and drive
it as a subprocess over the official uritemplate-test vectors plus focused
discriminators for the divergent Level 4 tail cases.
"""

import json
import os
import subprocess

APP = "/app"
VECTORS = os.path.join(os.path.dirname(__file__), "vectors.jsonl")


def _build():
    """Compile the release binary once and return its path."""
    subprocess.run(
        ["make"],
        cwd=APP,
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )
    path = os.path.join(APP, "uritmpl")
    assert os.path.exists(path), "release binary was not produced"
    return path


BIN = _build()


def run_tool(template, variables):
    """Invoke the tool with a template and variables; return (rc, stdout)."""
    payload = json.dumps({"template": template, "variables": variables})
    proc = subprocess.run(
        [BIN],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return proc.returncode, proc.stdout.rstrip("\n")


def load_vectors():
    """Yield every official (set, template, variables, expected) record."""
    with open(VECTORS, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def test_full_official_suite():
    """Every official uritemplate-test vector must expand exactly (or be rejected).

    Expansion vectors must match one of the accepted strings; vectors whose
    expected value is ``false`` must be reported as malformed with a non-zero
    exit and the literal ``ERROR`` token.
    """
    failures = []
    total = 0
    for rec in load_vectors():
        total += 1
        expected = rec["expected"]
        rc, out = run_tool(rec["template"], rec["variables"])
        if expected is False:
            if rc == 0 or out != "ERROR":
                failures.append((rec["set"], rec["template"], "expected rejection", out, rc))
        else:
            accepted = expected if isinstance(expected, list) else [expected]
            if rc != 0 or out not in accepted:
                failures.append((rec["set"], rec["template"], accepted, out, rc))
    assert total >= 250, f"expected the full baked suite, only saw {total} vectors"
    assert not failures, "official-suite mismatches: " + "; ".join(
        f"[{s}] {t!r} -> {o!r} (rc={rc}), want {exp!r}" for s, t, exp, o, rc in failures[:20]
    )


def test_explode_on_associative_object():
    """The ``*`` modifier on an object expands name=value pairs, not just values.

    Without explode the object flattens to ``key,val,key,val``; with explode
    each pair becomes ``key=val`` joined by the operator separator, and the
    ``?``/``&`` form emits ``name=value`` query segments.
    """
    obj = {"one": "1", "two": "2"}
    _, no_explode = run_tool("{?params}", {"params": obj})
    assert no_explode == "?params=one,1,two,2"
    _, explode = run_tool("{?params*}", {"params": obj})
    assert explode == "?one=1&two=2"
    # path-style explode uses the '/' separator between pairs
    _, path = run_tool("{/params*}", {"params": obj})
    assert path == "/one=1/two=2"


def test_prefix_counts_unicode_characters_not_bytes():
    """The ``:N`` prefix truncates by Unicode characters, then percent-encodes.

    A multibyte character must count as one character: ``{v:1}`` over a string
    beginning with a 3-byte character keeps exactly that one character and
    percent-encodes its UTF-8 bytes, rather than slicing raw bytes.
    """
    # U+20AC EURO SIGN is 3 bytes (E2 82 AC); one character kept -> %E2%82%AC
    rc, out = run_tool("{v:1}", {"v": "€abc"})
    assert rc == 0
    assert out == "%E2%82%AC"
    # two characters kept -> euro + 'a'
    _, out2 = run_tool("{v:2}", {"v": "€abc"})
    assert out2 == "%E2%82%ACa"
    # ASCII truncation still counts characters
    _, out3 = run_tool("{v:3}", {"v": "value"})
    assert out3 == "val"


def test_reserved_vs_unreserved_encoding_per_operator():
    """Reserved characters are preserved only under the ``+`` and ``#`` operators.

    The default and other operators percent-encode reserved characters, while
    reserved expansion leaves gen-delims/sub-delims and existing pct-triplets
    intact.
    """
    v = {"p": "/foo/bar", "half": "50%25"}
    _, default = run_tool("{p}", v)
    assert default == "%2Ffoo%2Fbar"
    _, reserved = run_tool("{+p}", v)
    assert reserved == "/foo/bar"
    _, frag = run_tool("{#p}", v)
    assert frag == "#/foo/bar"
    # existing percent-encoded triplets pass through under reserved expansion
    _, keep = run_tool("{+half}", v)
    assert keep == "50%25"
    # but are re-encoded under the default operator (the '%' becomes %25)
    _, reenc = run_tool("{half}", v)
    assert reenc == "50%2525"


def test_empty_undefined_and_empty_list_handling():
    """Empty strings, undefined variables, and empty lists expand differently.

    A defined empty string yields a bare ``name`` (or ``name=`` in query form),
    an undefined variable contributes nothing, and an empty list is treated as
    undefined so its operator prefix is suppressed.
    """
    v = {"empty": "", "list": []}
    _, semi_empty = run_tool("{;x}", v)  # x undefined
    assert semi_empty == ""
    _, semi_defined = run_tool("{;empty}", v)
    assert semi_defined == ";empty"
    _, query_empty = run_tool("{?empty}", v)
    assert query_empty == "?empty="
    _, empty_list = run_tool("{/list}", v)
    assert empty_list == ""
    # a mix: undefined then defined empty keeps only the defined one
    _, mixed = run_tool("{?undef,empty}", v)
    assert mixed == "?empty="


def test_malformed_templates_are_rejected():
    """Syntactically invalid templates must be rejected, not silently echoed.

    An unterminated expression, a stray operator, a space inside a name, and a
    prefix modifier on a composite value each violate the grammar and must
    produce ``ERROR`` with a non-zero exit.
    """
    variables = {"list": ["a", "b"], "keys": {"a": "1"}, "var": "x"}
    for bad in ["{/id*", "/id*}", "{with space}", "{!var}", "{keys:1}", "{var:prefix}"]:
        rc, out = run_tool(bad, variables)
        assert rc != 0, f"template {bad!r} should have been rejected"
        assert out == "ERROR", f"template {bad!r} should print ERROR, got {out!r}"


def test_preserves_literals_and_normal_expansion():
    """Literal characters pass through unchanged around normal substitutions.

    A template with surrounding literal path segments and a simple variable
    must reproduce the literals verbatim and substitute the variable in place,
    matching the Level 1 baseline behavior.
    """
    v = {"who": "fred", "dom": "example.com"}
    _, out = run_tool("http://{dom}/~{who}/", v)
    assert out == "http://example.com/~fred/"
    _, out2 = run_tool("{who}", v)
    assert out2 == "fred"


def test_anti_shortcut_generated_inputs():
    """Freshly generated inputs (not in the suite) still expand per the algorithm.

    Uses novel variable names and values computed here so a lookup table keyed
    on the official vectors cannot satisfy them; the query explode, prefix
    truncation, and reserved-set rules are recomputed independently.
    """
    variables = {
        "user_id": "Zeta Q?",
        "tags": ["alpha", "beta gamma", "d/e"],
        "coords": {"lat": "1.5", "lon": "-2.5"},
        "token": "café",
    }
    # query explode over a list encodes each member and repeats the name
    _, q = run_tool("{?tags*}", variables)
    assert q == "?tags=alpha&tags=beta%20gamma&tags=d%2Fe"
    # reserved expansion of a list keeps '/' but still encodes spaces
    _, r = run_tool("{+tags}", variables)
    assert r == "alpha,beta%20gamma,d/e"
    # prefix on a unicode string counts characters (café -> caf, 3 chars)
    _, p = run_tool("{user_id:4}", variables)
    assert p == "Zeta"
    _, cafe = run_tool("{token:3}", variables)
    assert cafe == "caf"
    # associative explode in a path segment
    _, c = run_tool("{/coords*}", variables)
    assert c == "/lat=1.5/lon=-2.5"
    # default operator encodes the space and '?' in a scalar
    _, u = run_tool("{user_id}", variables)
    assert u == "Zeta%20Q%3F"
