"""Verifier checks for published launch artifacts."""

import json
import shutil
import subprocess
from pathlib import Path


OUT = Path("/app/output")


def leaf(label, raw, unit, lo, hi, orient, weight):
    return (label, raw, unit, lo, hi, orient, weight)


def request(
    tmp_path,
    name,
    entries,
    *,
    aliases=(),
    base="base-r1",
    revision="r1",
    parts=("north", "south"),
    limit=20,
    state=None,
    replay=False,
):
    root = Path(state or (tmp_path / f"state-{name}"))
    lines = [
        f"request_id={name}",
        f"base={base}",
        f"revision={revision}",
        f"parts={','.join(parts)}",
        f"limit={limit}",
        f"state_dir={root}",
        f"replay={'latest' if replay else 'exact'}",
    ]
    lines.extend(f"alias={a}|{b}" for a, b in aliases)
    lines.extend("leaf=" + "|".join(map(str, item)) for item in entries)
    path = tmp_path / f"{name}.req"
    path.write_text("\n".join(lines) + "\n")
    return path, root


def invoke(path):
    shutil.rmtree(OUT, ignore_errors=True)
    result = subprocess.run(
        ["/app/lora-gate", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((OUT / "lora_merge_conflict_gate.json").read_text())
    rows = [
        json.loads(line)
        for line in (OUT / "adapter_findings.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert rows
    return report, rows


def assert_types(report, rows):
    assert isinstance(report["request_id"], str)
    assert isinstance(report["model_view"], str)
    assert isinstance(report["ready"], bool)
    assert isinstance(report["score"], int)
    assert isinstance(report["targets"], list)
    assert all(isinstance(item, str) for item in report["targets"])
    for row in rows:
        assert isinstance(row["request_id"], str)
        assert isinstance(row["model_view"], str)
        assert isinstance(row["adapter"], str)
        assert isinstance(row["ready"], bool)
        assert isinstance(row["score"], int)


def assert_artifact_agreement(report, rows):
    assert_types(report, rows)
    for row in rows:
        assert row["request_id"] == report["request_id"]
        assert row["model_view"] == report["model_view"]
        assert row["ready"] == report["ready"]
        assert row["score"] == report["score"]


def cold(path, root):
    shutil.rmtree(root, ignore_errors=True)
    return invoke(path)


def state_root(tmp_path, token):
    return tmp_path.joinpath(f"state-{token}")


def single_score(tmp_path, name, item, **kwargs):
    path, root = request(tmp_path, name, [item], **kwargs)
    report, _ = cold(path, root)
    return report["score"]


def test_case_01(tmp_path):
    """Published outcomes agree for matched request pairs."""
    one = [leaf("member-a", "attn.q", "encoder.block0.q", 0, 8, 1, 2)]
    two = [leaf("member-a", "query_proj", "encoder.block0.q", 0, 8, 1, 2)]
    a, ar = request(tmp_path, "s01a", one)
    b, br = request(
        tmp_path,
        "s01b",
        two,
        aliases=(("query_proj", "encoder.block0.q"),),
    )
    left, left_rows = cold(a, ar)
    right, right_rows = cold(b, br)
    assert_artifact_agreement(left, left_rows)
    assert_artifact_agreement(right, right_rows)
    assert left["targets"] == right["targets"]
    assert left["ready"] == right["ready"]
    assert left["score"] == right["score"]


def test_case_02(tmp_path):
    """Matched request pairs keep the same published targets and score."""
    forward = [leaf("member-a", "q", "encoder.block0.q", 0, 8, 1, 2)]
    reverse = [leaf("member-a", "q", "encoder.block0.q", 8, 0, -1, 2)]
    a, ar = request(tmp_path, "s02a", forward)
    b, br = request(tmp_path, "s02b", reverse)
    left, _ = cold(a, ar)
    right, _ = cold(b, br)
    assert left["targets"] == right["targets"]
    assert left["score"] == right["score"]


def test_case_03(tmp_path):
    """Multi-member requests remain ready with stable scores."""
    entries = [
        leaf("member-a", "alpha", "encoder.block0.q", 0, 8, 1, 3),
        leaf("member-b", "atom", "decoder.block0.o", 0, 8, 1, 3),
    ]
    path, root = request(tmp_path, "s03", entries)
    report, rows = cold(path, root)
    assert_artifact_agreement(report, rows)
    assert report["ready"]
    assert len(report["targets"]) == len(entries)
    expected = max(
        single_score(tmp_path, f"s03-ref-{i}", item)
        for i, item in enumerate(entries)
    )
    assert report["score"] == expected


def test_case_04(tmp_path):
    """Some multi-member requests are marked not ready."""
    limit = 20
    entries = [
        leaf(f"member-{i}", "v", "encoder.block0.v", 0, 8, 1, 2) for i in range(3)
    ]
    path, root = request(tmp_path, "s04", entries, limit=limit)
    report, rows = cold(path, root)
    assert_artifact_agreement(report, rows)
    stacked = leaf("member-stack", "v", "encoder.block0.v", 0, 8, 1, 6)
    expected = single_score(tmp_path, "s04-ref", stacked, limit=limit)
    assert report["score"] == expected
    assert report["score"] > limit
    assert not report["ready"]


def test_case_05(tmp_path):
    """Reordered members keep the same published fields."""
    entries = [
        leaf("member-a", "v", "encoder.block0.v", 0, 8, 1, 10),
        leaf("member-b", "v", "encoder.block0.v", 0, 8, 1, 5),
        leaf("member-c", "v", "encoder.block0.v", 0, 8, 1, 1),
    ]
    a, ar = request(tmp_path, "s05a", entries, limit=300)
    b, br = request(
        tmp_path, "s05b", [entries[0], entries[2], entries[1]], limit=300
    )
    left, _ = cold(a, ar)
    right, _ = cold(b, br)
    assert left["score"] == right["score"]
    assert left["model_view"] == right["model_view"]
    assert left["targets"] == right["targets"]


def test_case_06(tmp_path):
    """Separate members stay ready with a stable score."""
    entries = [
        leaf("member-a", "q", "encoder.block0.q", 0, 8, 1, 3),
        leaf("member-b", "v", "encoder.block0.v", 0, 8, 1, 3),
        leaf("member-c", "o", "decoder.block0.o", 0, 8, 1, 3),
    ]
    path, root = request(tmp_path, "s06", entries)
    report, rows = cold(path, root)
    assert_artifact_agreement(report, rows)
    expected = max(
        single_score(tmp_path, f"s06-ref-{i}", item)
        for i, item in enumerate(entries)
    )
    assert report["score"] == expected
    assert report["ready"]


def test_case_07(tmp_path):
    """Later requests match a cold run with the same inputs."""
    state = state_root(tmp_path, "case07")
    first = [
        leaf("member-a", "v", "encoder.block0.v", 0, 8, 1, 2),
        leaf("member-b", "v", "encoder.block0.v", 0, 8, 1, 2),
    ]
    second = [
        leaf("member-a", "v", "encoder.block0.v", 0, 8, 1, 1),
        leaf("member-b", "v", "encoder.block0.v", 0, 8, 1, 1),
    ]
    a, _ = request(tmp_path, "s07a", first, state=state)
    b, _ = request(tmp_path, "s07b", second, state=state)
    cold(a, state)
    warm, _ = invoke(b)
    fresh_path, fresh_root = request(tmp_path, "s07b", second)
    fresh, _ = cold(fresh_path, fresh_root)
    assert warm == fresh


def test_case_08(tmp_path):
    """Requests with different bases keep distinct model views."""
    state = state_root(tmp_path, "case08")
    entries = [leaf("member-a", "q", "encoder.block0.q", 0, 8, 1, 2)]
    a, _ = request(tmp_path, "s08a", entries, base="base-r1", state=state)
    b, _ = request(
        tmp_path, "s08b", entries, base="base-r2", revision="r2", state=state
    )
    first, _ = cold(a, state)
    warm, _ = invoke(b)
    fresh_path, fresh_root = request(
        tmp_path, "s08b", entries, base="base-r2", revision="r2"
    )
    fresh, _ = cold(fresh_path, fresh_root)
    assert warm == fresh
    assert first["model_view"] != warm["model_view"]


def test_case_09(tmp_path):
    """Requests with different parts keep distinct model views."""
    state = state_root(tmp_path, "case09")
    entries = [leaf("member-a", "q", "encoder.block0.q", 0, 8, 1, 2)]
    a, _ = request(tmp_path, "s09a", entries, parts=("north",), state=state)
    b, _ = request(
        tmp_path, "s09b", entries, parts=("north", "west"), state=state
    )
    first, _ = cold(a, state)
    second, _ = invoke(b)
    assert first["model_view"] != second["model_view"]


def test_case_10(tmp_path):
    """Follow-up requests match a cold run with the same inputs."""
    state = state_root(tmp_path, "case10")
    heavy = [leaf("member-a", "v", "encoder.block0.v", 0, 8, 1, 6)]
    light = [leaf("member-b", "q", "encoder.block0.q", 0, 8, 1, 1)]
    a, _ = request(tmp_path, "s10a", heavy, limit=20, state=state)
    b, _ = request(tmp_path, "s10b", light, limit=20, state=state, replay=True)
    cold(a, state)
    replayed, _ = invoke(b)
    fresh_path, fresh_root = request(tmp_path, "s10b", light, limit=20)
    fresh, _ = cold(fresh_path, fresh_root)
    assert replayed == fresh


def test_case_11(tmp_path):
    """Report and findings rows agree on shared fields."""
    state = state_root(tmp_path, "case11")
    old = [leaf("former", "v", "encoder.block0.v", 0, 8, 1, 6)]
    new = [
        leaf("current-a", "q", "encoder.block0.q", 0, 8, 1, 1),
        leaf("current-b", "o", "decoder.block0.o", 0, 8, 1, 1),
    ]
    a, _ = request(tmp_path, "s11a", old, state=state)
    b, _ = request(tmp_path, "s11b", new, state=state, replay=True)
    cold(a, state)
    report, rows = invoke(b)
    assert [row["adapter"] for row in rows] == [item[0] for item in new]
    assert_artifact_agreement(report, rows)


def test_case_12(tmp_path):
    """Repeated requests stay consistent across orderings."""
    state = state_root(tmp_path, "case12")
    first = [leaf("former", "v", "encoder.block0.v", 0, 8, 1, 5)]
    final = [
        leaf("final-b", "o", "decoder.block0.o", 0, 8, 1, 2),
        leaf("final-a", "q", "encoder.block0.q", 0, 8, 1, 2),
    ]
    a, _ = request(tmp_path, "s12a", first, state=state)
    b, _ = request(tmp_path, "s12b", final, state=state, replay=True)
    cold(a, state)
    observed, _ = invoke(b)
    clean_path, clean_root = request(
        tmp_path, "s12b", list(reversed(final)), replay=True
    )
    clean, _ = cold(clean_path, clean_root)
    assert observed == clean


def test_case_13(tmp_path):
    """Target arrays stay ordered without duplicates."""
    entries = [
        leaf("member-b", "v", "encoder.block0.v", 0, 8, 1, 1),
        leaf("member-a", "q", "encoder.block0.q", 0, 8, 1, 1),
        leaf("member-c", "q2", "encoder.block0.q", 0, 8, 1, 1),
        leaf("member-d", "o", "decoder.block0.o", 0, 8, 1, 1),
    ]
    path, root = request(
        tmp_path,
        "s13",
        entries,
        aliases=(("q2", "encoder.block0.q"),),
    )
    report, rows = cold(path, root)
    assert_artifact_agreement(report, rows)
    assert report["targets"] == sorted(set(report["targets"]))
    assert len(report["targets"]) == 3
    assert [row["adapter"] for row in rows] == [item[0] for item in entries]


def test_case_14(tmp_path):
    """Aliased members on one target withhold when their combined score exceeds limit."""
    limit = 30
    entries = [
        leaf("member-a", "attn.q", "encoder.block0.q", 0, 8, 1, 4),
        leaf("member-b", "query_proj", "encoder.block0.q", 8, 0, -1, 2),
        leaf("member-c", "v", "encoder.block0.v", 0, 8, 1, 3),
    ]
    path, root = request(
        tmp_path,
        "s14",
        entries,
        aliases=(("query_proj", "encoder.block0.q"),),
        limit=limit,
    )
    report, rows = cold(path, root)
    assert_artifact_agreement(report, rows)
    stacked = leaf("member-stack", "q", "encoder.block0.q", 0, 8, 1, 6)
    other = leaf("member-other", "v", "encoder.block0.v", 0, 8, 1, 3)
    expected = max(
        single_score(tmp_path, "s14-ref-a", stacked, limit=limit),
        single_score(tmp_path, "s14-ref-b", other, limit=limit),
    )
    assert report["score"] == expected
    assert report["score"] > limit
    assert not report["ready"]
    assert len(report["targets"]) == 2
