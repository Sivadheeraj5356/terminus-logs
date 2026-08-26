"""Milestone 1 verifier: the version total order and the manifest parser.

The version tests run the modverse version subcommand on held out version strings
and check the ordering of pseudo versions against tagged releases against
incompatible releases, plus the prerelease and pseudo version internal ordering.
They also assert the order is a genuine total order over a fixture set by
checking antisymmetry, transitivity, and consistency with sorting. The manifest
tests run the manifest subcommand and check the parsed model round trips the
require, replace, exclude, and lang directives in both single line and block
forms, including versionless replace directives and the multi entry replace and
exclude block bodies, so a parser that only handles single line directives fails
here rather than slipping through to a later milestone.
"""

import itertools
import json
import os
import subprocess
import tempfile

import modref as M

CLI = "/usr/local/bin/modverse"


def cli_compare(a, b):
    out = os.path.join(tempfile.mkdtemp(), "r.json")
    proc = subprocess.run(
        [CLI, "version", "--compare", a, b, "--out", out],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"compare failed: {proc.stderr}"
    with open(out) as f:
        return json.load(f)["compare"]


def cli_sort(versions):
    out = os.path.join(tempfile.mkdtemp(), "r.json")
    proc = subprocess.run(
        [CLI, "version", "--sort", ",".join(versions), "--out", out],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"sort failed: {proc.stderr}"
    with open(out) as f:
        return json.load(f)["sorted"]


def cli_manifest(text):
    d = tempfile.mkdtemp()
    path = os.path.join(d, "module.mod")
    with open(path, "w") as f:
        f.write(text)
    out = os.path.join(d, "r.json")
    proc = subprocess.run(
        [CLI, "manifest", "--file", path, "--out", out],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"manifest failed: {proc.stderr}"
    with open(out) as f:
        return json.load(f)


PSEUDO = "0.0.0-20240118091500-9fceb02d0ae5"
PSEUDO_EARLIER = "0.0.0-20240118091400-aaaaaaaaaaaa"
PSEUDO_SAME_TS_HI_HASH = "0.0.0-20240118091500-aaaaaaaaaaaa"

POOL = [
    "v1.0.0-alpha",
    "v1.0.0-rc",
    "v1.0.0-rc.0",
    "v1.0.0-rc.2",
    "v1.0.0-rc.10",
    "v1.0.0",
    "v1.0.0+incompatible",
    "v1.2.3",
    "v2.0.0",
    "v2.0.0+incompatible",
    "v" + PSEUDO_EARLIER,
    "v" + PSEUDO,
    "v" + PSEUDO_SAME_TS_HI_HASH,
    "v1.5.1-0.20240220140000-c1d2e3f4a5b6",
    "v1.5.1",
]


class TestMilestone1:
    def test_prerelease_below_release(self):
        """A prerelease version ranks below the same numeric core with no
        suffix."""
        assert cli_compare("v1.4.0-rc.2", "v1.4.0") == -1
        assert cli_compare("v1.4.0", "v1.4.0-rc.2") == 1

    def test_incompatible_above_core(self):
        """An incompatible release ranks above the identical numeric core, but
        below the next higher core."""
        assert cli_compare("v2.0.0+incompatible", "v2.0.0") == 1
        assert cli_compare("v2.0.0+incompatible", "v2.0.1") == -1

    def test_pseudo_below_tagged_same_base(self):
        """A pseudo version ranks below a tagged release that shares its base
        core and below the bare base core itself."""
        assert cli_compare("v" + PSEUDO, "v0.0.0") == -1
        assert cli_compare("v1.5.1-0.20240220140000-c1d2e3f4a5b6", "v1.5.1") == -1

    def test_pseudo_ordered_by_timestamp(self):
        """Two pseudo versions on the same base core order by their timestamp."""
        assert cli_compare("v" + PSEUDO, "v" + PSEUDO_EARLIER) == 1
        assert cli_compare("v" + PSEUDO_EARLIER, "v" + PSEUDO) == -1

    def test_pseudo_hash_breaks_timestamp_tie(self):
        """Two pseudo versions that share a base core and an identical 14 digit
        timestamp order by their short hash in ASCII string order, and a pseudo
        version compares equal to itself."""
        lo = "v" + PSEUDO
        hi = "v" + PSEUDO_SAME_TS_HI_HASH
        assert cli_compare(lo, hi) == -1
        assert cli_compare(hi, lo) == 1
        assert cli_compare(lo, lo) == 0

    def test_prerelease_identifier_ordering(self):
        """Numeric prerelease identifiers compare as integers, a shorter
        prerelease ranks below a longer otherwise equal one, and an alphabetic
        identifier outranks a numeric one."""
        assert cli_compare("v1.0.0-rc.2", "v1.0.0-rc.10") == -1
        assert cli_compare("v1.0.0-rc", "v1.0.0-rc.0") == -1
        assert cli_compare("v1.0.0-alpha", "v1.0.0-rc") == -1

    def test_equal_versions(self):
        """Versions equal after dropping a leading v compare equal."""
        assert cli_compare("v1.2.3", "1.2.3") == 0
        assert cli_compare("v2.0.0", "v2.0.0") == 0

    def test_compare_matches_reference_over_pool(self):
        """Every ordered pair from the version pool agrees with the reference."""
        for a, b in itertools.product(POOL, repeat=2):
            got = cli_compare(a, b)
            want = M.compare(M.parse_version(a), M.parse_version(b))
            want = (want > 0) - (want < 0)
            assert got == want, f"{a} vs {b}: got {got} want {want}"

    def test_total_order_antisymmetry(self):
        """For all pairs, compare(a,b) is the negation of compare(b,a)."""
        for a, b in itertools.combinations(POOL, 2):
            assert cli_compare(a, b) == -cli_compare(b, a)

    def test_total_order_transitivity(self):
        """The order is transitive across the pool."""
        ordered = cli_sort(POOL)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                assert cli_compare(ordered[i], ordered[j]) <= 0

    def test_sort_matches_reference(self):
        """Sorting the pool agrees with sorting under the reference order."""
        got = cli_sort(POOL)
        import functools

        want = sorted(
            POOL,
            key=functools.cmp_to_key(
                lambda x, y: M.compare(M.parse_version(x), M.parse_version(y))
            ),
        )
        want = [M.parse_version(v).display for v in want]
        assert got == want

    def test_manifest_single_line_directives(self):
        """A manifest with single line require, replace, exclude, and a lang line
        parses into the typed model with the right fields."""
        text = (
            "module sample/web\n"
            "lang 1.21\n"
            "require sample/json v1.2.0\n"
            "replace sample/json v1.2.0 => sample/json v1.1.0\n"
            "exclude sample/json v1.0.5\n"
        )
        m = cli_manifest(text)
        assert m["module"] == "sample/web"
        assert m["lang"] == "1.21"
        assert m["require"] == [
            {"path": "sample/json", "version": "v1.2.0", "indirect": False}
        ]
        assert m["replace"][0]["oldPath"] == "sample/json"
        assert m["replace"][0]["oldVersion"] == "v1.2.0"
        assert m["replace"][0]["newVersion"] == "v1.1.0"
        assert m["replace"][0]["newIsLocal"] is False
        assert m["exclude"] == [{"path": "sample/json", "version": "v1.0.5"}]

    def test_manifest_block_and_indirect(self):
        """A require block parses every entry in order and honours the trailing
        indirect marker."""
        text = (
            "module sample/app\n"
            "lang 1.18\n"
            "require (\n"
            "\tsample/json v1.2.0\n"
            "\tsample/text v1.4.0 // indirect\n"
            ")\n"
        )
        m = cli_manifest(text)
        assert [r["path"] for r in m["require"]] == ["sample/json", "sample/text"]
        assert m["require"][0]["indirect"] is False
        assert m["require"][1]["indirect"] is True

    def test_manifest_local_replace(self):
        """A replace whose target is a filesystem path is marked local with an
        empty target version, and a left side with no version reports an empty
        old version."""
        text = "module sample/app\nlang 1.20\nreplace sample/json => ../local/json\n"
        m = cli_manifest(text)
        r = m["replace"][0]
        assert r["newIsLocal"] is True
        assert r["newPath"] == "../local/json"
        assert r["newVersion"] == ""
        assert r["oldPath"] == "sample/json"
        assert r["oldVersion"] == ""

    def test_manifest_replace_block_and_versionless(self):
        """A replace block parses every entry in order, and a versionless left
        side reports an empty old version while still rewriting to a versioned
        registry target."""
        text = (
            "module sample/app\n"
            "lang 1.20\n"
            "replace (\n"
            "\tsample/json v1.2.0 => sample/json v1.1.0\n"
            "\tsample/text => sample/text v1.0.0\n"
            ")\n"
        )
        m = cli_manifest(text)
        assert [r["oldPath"] for r in m["replace"]] == ["sample/json", "sample/text"]
        first = m["replace"][0]
        assert first["oldVersion"] == "v1.2.0"
        assert first["newPath"] == "sample/json"
        assert first["newVersion"] == "v1.1.0"
        assert first["newIsLocal"] is False
        second = m["replace"][1]
        assert second["oldVersion"] == ""
        assert second["newPath"] == "sample/text"
        assert second["newVersion"] == "v1.0.0"
        assert second["newIsLocal"] is False

    def test_manifest_exclude_block(self):
        """An exclude block parses every entry in the order written."""
        text = (
            "module sample/app\n"
            "lang 1.20\n"
            "exclude (\n"
            "\tsample/json v1.0.5\n"
            "\tsample/text v1.4.0\n"
            ")\n"
        )
        m = cli_manifest(text)
        assert m["exclude"] == [
            {"path": "sample/json", "version": "v1.0.5"},
            {"path": "sample/text", "version": "v1.4.0"},
        ]

    def test_manifest_missing_lang_defaults(self):
        """A manifest with no lang line reports lang 0.0."""
        text = "module sample/bare\nrequire sample/json v1.0.0\n"
        m = cli_manifest(text)
        assert m["lang"] == "0.0"

    def test_manifest_comments_and_blanks_ignored(self):
        """Blank lines and comment lines carry no meaning."""
        text = (
            "// top comment\n"
            "module sample/c\n"
            "\n"
            "lang 1.19\n"
            "// a note\n"
            "require sample/json v1.0.0\n"
        )
        m = cli_manifest(text)
        assert m["module"] == "sample/c"
        assert len(m["require"]) == 1
