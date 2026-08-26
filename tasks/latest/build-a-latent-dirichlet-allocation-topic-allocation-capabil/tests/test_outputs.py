"""Behavioral verifier for the LDA collapsed-Gibbs topic allocation CLI.

Every test shells out to the compiled /usr/local/bin/ldactl binary and compares
its on-disk artifacts against an independent Python reference implementation.
"""
from __future__ import annotations

import json
import os
import pwd
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

PRIV = Path("/opt/verifier-private")
if str(PRIV) not in sys.path:
    sys.path.insert(0, str(PRIV))
import reference_lda as ref  # noqa: E402

BIN = "/usr/local/bin/ldactl"
APP = Path("/app")
CORPUS = APP / "state/lda-corpus-staging.json"
COUNTS = APP / "state/lda-count-staging.json"
OUT = APP / "output/lda-topic-rollup.json"
INBOX = APP / "fixtures/patent-inbox"
HIDDEN = Path("/opt/verifier-fixtures/lda")
SNAP = Path("/tmp/lda-agent-snapshot")
MODULES = ["corpus", "vocab", "rng", "sampler", "ledger", "retention", "ranking", "publication"]
MODULE_PATHS = {m: f"{m}/mod.rs" for m in MODULES}

_NOBODY = pwd.getpwnam("nobody")
_BLOCKED_ENV = {
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
    "PYTHONEXECUTABLE",
    "LD_PRELOAD",
    "LD_LIBRARY_PATH",
}


def _cli_env(extra=None):
    """Environment for ldactl: no verifier PYTHONPATH or loader overrides."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in _BLOCKED_ENV and not k.startswith("PYTHON")
    }
    if extra:
        env.update(extra)
    return env


def _demote():
    os.setgid(_NOBODY.pw_gid)
    os.setuid(_NOBODY.pw_uid)


def _chown_tree(path: Path):
    if not path.exists():
        return
    for root, dirs, files in os.walk(path):
        os.chown(root, _NOBODY.pw_uid, _NOBODY.pw_gid)
        for name in dirs + files:
            os.chown(os.path.join(root, name), _NOBODY.pw_uid, _NOBODY.pw_gid)


def handoff():
    """Submitted CLI runs as nobody; hand writable artifacts to that account."""
    _chown_tree(APP / "state")
    _chown_tree(APP / "output")


def run(args, env=None, check=True):
    handoff()
    cp = subprocess.run(
        [BIN, *args],
        text=True,
        capture_output=True,
        env=_cli_env(env),
        preexec_fn=_demote,
    )
    if check and cp.returncode:
        raise AssertionError(f"{args}: {cp.stderr}")
    return cp


def reset():
    for p in (CORPUS, COUNTS, OUT):
        p.unlink(missing_ok=True)
    CORPUS.parent.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    handoff()


def pipe(root=INBOX):
    reset()
    run(["ingest"], {"TB3_LDA_ROOT": str(root)})
    run(["sample"])
    run(["export"])


def load(p):
    return json.loads(Path(p).read_text())


def rebuild():
    subprocess.run(
        ["bash", "/app/scripts/rebuild-ldactl.sh"],
        check=True,
        capture_output=True,
        text=True,
    )


def _flatten(value):
    out = []

    def rec(v):
        if isinstance(v, list):
            for e in v:
                rec(e)
        else:
            out.append(v)

    rec(value)
    return out


def approx_nested(actual, expected, rel=1e-9, abs_=1e-12):
    fa = _flatten(actual)
    fe = _flatten(expected)
    assert len(fa) == len(fe)
    assert fa == pytest.approx(fe, rel=rel, abs=abs_)


def assert_counts_exact(actual, expected):
    for key in (
        "schema", "k", "alpha", "beta", "seed", "sweeps", "burn_in",
        "retained_sweeps", "vocab", "doc_ids", "assignments", "n_dk", "n_kw", "n_k",
    ):
        assert actual[key] == expected[key], f"count field mismatch: {key}"
    approx_nested(actual["theta_sum"], expected["theta_sum"])


@pytest.fixture(scope="session", autouse=True)
def preserve_agent_tree():
    """Snapshot the agent's crates before testing and restore them afterwards."""
    shutil.rmtree(SNAP, ignore_errors=True)
    shutil.copytree(APP / "crates", SNAP / "crates")
    yield
    shutil.rmtree(APP / "crates")
    shutil.copytree(SNAP / "crates", APP / "crates")
    rebuild()
    reset()


def install_profile(golden):
    src = "golden_lib" if golden else "broken_lib"
    for m in MODULES:
        target = APP / f"crates/ldacore/src/{MODULE_PATHS[m]}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PRIV / src / f"{m}.rs", target)
    rebuild()


def restore_snapshot():
    shutil.rmtree(APP / "crates")
    shutil.copytree(SNAP / "crates", APP / "crates")
    rebuild()
    reset()


# --- corpus staging -------------------------------------------------------


def test_01_corpus_staging_matches_reference():
    """The corpus snapshot for the bundled inbox equals the independent reference."""
    pipe()
    assert load(CORPUS) == ref.corpus_staging(INBOX)


def test_02_corpus_docs_sorted_by_doc_id():
    """Documents appear in ascending doc_id order regardless of file names."""
    pipe()
    ids = [d["doc_id"] for d in load(CORPUS)["docs"]]
    assert ids == sorted(ids)
    assert ids == ["US-1005", "US-2006", "US-3001", "US-5003", "US-7002", "US-9004"]


def test_03_vocab_sorted_and_token_ids_are_indices():
    """The vocabulary is lexicographically sorted and token ids index into it."""
    pipe()
    corpus = load(CORPUS)
    vocab = corpus["vocab"]
    assert vocab == sorted(vocab)
    assert corpus["schema"] == "lda-corpus/v1"
    for doc in corpus["docs"]:
        assert all(0 <= tid < len(vocab) for tid in doc["token_ids"])


def test_04_duplicate_doc_id_rejected(tmp_path):
    """Two documents sharing a doc_id abort ingest without a corpus artifact."""
    root = tmp_path / "dup"
    root.mkdir()
    (root / "a.json").write_text(json.dumps({"doc_id": "D-1", "tokens": ["x", "y"]}))
    (root / "b.json").write_text(json.dumps({"doc_id": "D-1", "tokens": ["y", "z"]}))
    reset()
    assert run(["ingest"], {"TB3_LDA_ROOT": str(root)}, False).returncode != 0
    assert not CORPUS.exists()


def test_05_empty_tokens_rejected(tmp_path):
    """A document with an empty token list is rejected without a corpus artifact."""
    root = tmp_path / "empty"
    root.mkdir()
    (root / "a.json").write_text(json.dumps({"doc_id": "D-1", "tokens": []}))
    reset()
    assert run(["ingest"], {"TB3_LDA_ROOT": str(root)}, False).returncode != 0
    assert not CORPUS.exists()


def test_06_empty_token_string_rejected(tmp_path):
    """A document containing an empty token string is rejected."""
    root = tmp_path / "blank"
    root.mkdir()
    (root / "a.json").write_text(json.dumps({"doc_id": "D-1", "tokens": ["x", ""]}))
    reset()
    assert run(["ingest"], {"TB3_LDA_ROOT": str(root)}, False).returncode != 0
    assert not CORPUS.exists()


def test_07_absolute_override_selects_inbox():
    """An absolute TB3_LDA_ROOT overrides the configured inbox for ingest."""
    reset()
    run(["ingest"], {"TB3_LDA_ROOT": "/opt/verifier-fixtures/lda/lexical"})
    ids = [d["doc_id"] for d in load(CORPUS)["docs"]]
    assert ids == ["PX-10", "PX-20", "PX-30", "PX-40"]


def test_08_relative_override_ignored():
    """A relative TB3_LDA_ROOT is ignored and the configured inbox is used."""
    reset()
    run(["ingest"], {"TB3_LDA_ROOT": "relative/path"})
    assert len(load(CORPUS)["docs"]) == 6


# --- sampling / count ledger ---------------------------------------------


def test_09_count_assignments_match_reference():
    """Final token-topic assignments equal the reference sampler."""
    pipe()
    expected = ref.count_staging(load(CORPUS))
    assert load(COUNTS)["assignments"] == expected["assignments"]


def test_10_count_ndk_matches_reference():
    """The document-topic count matrix equals the reference sampler."""
    pipe()
    expected = ref.count_staging(load(CORPUS))
    assert load(COUNTS)["n_dk"] == expected["n_dk"]


def test_11_count_nkw_and_nk_match_reference():
    """The topic-term matrix and topic totals equal the reference sampler."""
    pipe()
    expected = ref.count_staging(load(CORPUS))
    got = load(COUNTS)
    assert got["n_kw"] == expected["n_kw"]
    assert got["n_k"] == expected["n_k"]


def test_12_count_staging_full_matches_reference():
    """The entire count snapshot equals the reference, theta_sum within tolerance."""
    pipe()
    expected = ref.count_staging(load(CORPUS))
    assert_counts_exact(load(COUNTS), expected)


def test_13_retained_sweeps_field():
    """retained_sweeps equals sweeps minus burn_in from the configuration."""
    pipe()
    p = ref.params()
    got = load(COUNTS)
    assert got["retained_sweeps"] == p["sweeps"] - p["burn_in"]
    assert got["burn_in"] == p["burn_in"]
    assert got["sweeps"] == p["sweeps"]


def test_14_count_conservation_invariants():
    """The three count structures stay mutually consistent after all sweeps."""
    pipe()
    corpus = load(CORPUS)
    counts = load(COUNTS)
    total_tokens = sum(len(d["token_ids"]) for d in corpus["docs"])
    assert sum(counts["n_k"]) == total_tokens
    k = counts["k"]
    for di, doc in enumerate(corpus["docs"]):
        assert sum(counts["n_dk"][di]) == len(doc["token_ids"])
    for topic in range(k):
        assert counts["n_k"][topic] == sum(counts["n_kw"][topic])
        assert counts["n_k"][topic] == sum(counts["n_dk"][di][topic] for di in range(len(corpus["docs"])))


def test_15_hidden_burnin_corpus_theta():
    """Hidden burn-in corpus: retained theta and retained_sweeps match the reference."""
    pipe(Path("/opt/verifier-fixtures/lda/burnin"))
    corpus = load(CORPUS)
    expected = ref.count_staging(corpus)
    got = load(COUNTS)
    assert got["retained_sweeps"] == expected["retained_sweeps"]
    assert got["assignments"] == expected["assignments"]
    approx_nested(got["theta_sum"], expected["theta_sum"])


def test_16_hidden_lexical_corpus_staging():
    """Hidden lexical corpus: sorted vocabulary, document order, and token ids match."""
    root = Path("/opt/verifier-fixtures/lda/lexical")
    pipe(root)
    assert load(CORPUS) == ref.corpus_staging(root)


# --- export / rollup ------------------------------------------------------


def test_17_export_theta_matches_reference():
    """Exported per-document theta rows match the reference rollup."""
    pipe()
    expected = ref.rollup(CORPUS.read_bytes(), COUNTS.read_bytes())
    got = load(OUT)
    assert [d["doc_id"] for d in got["documents"]] == [d["doc_id"] for d in expected["documents"]]
    approx_nested(
        [d["theta"] for d in got["documents"]],
        [d["theta"] for d in expected["documents"]],
    )


def test_18_export_top_terms_tokens_match_reference():
    """Each topic's ranked top-term tokens match the reference in order."""
    pipe()
    expected = ref.rollup(CORPUS.read_bytes(), COUNTS.read_bytes())
    got = load(OUT)
    assert [t["topic"] for t in got["topics"]] == list(range(load(COUNTS)["k"]))
    for gt, et in zip(got["topics"], expected["topics"]):
        assert [x["token"] for x in gt["top_terms"]] == [x["token"] for x in et["top_terms"]]


def test_19_export_top_term_probabilities_within_tolerance():
    """Top-term probabilities equal the smoothed posterior reference values."""
    pipe()
    expected = ref.rollup(CORPUS.read_bytes(), COUNTS.read_bytes())
    got = load(OUT)
    for gt, et in zip(got["topics"], expected["topics"]):
        approx_nested(
            [x["probability"] for x in gt["top_terms"]],
            [x["probability"] for x in et["top_terms"]],
        )


def test_20_hidden_ranking_ties_lexical_ascending():
    """Hidden ranking corpus: tied top-term slots break by ascending token order."""
    root = Path("/opt/verifier-fixtures/lda/ranking")
    pipe(root)
    expected = ref.rollup(CORPUS.read_bytes(), COUNTS.read_bytes())
    got = load(OUT)
    for gt, et in zip(got["topics"], expected["topics"]):
        tokens = [x["token"] for x in et["top_terms"]]
        probs = [x["probability"] for x in et["top_terms"]]
        for a in range(len(tokens) - 1):
            if probs[a] == pytest.approx(probs[a + 1]):
                assert tokens[a] < tokens[a + 1]
        assert [x["token"] for x in gt["top_terms"]] == tokens


def test_21_export_topic_and_document_shapes():
    """The rollup exposes one entry per topic and per document with length-K rows."""
    pipe()
    k = load(COUNTS)["k"]
    corpus = load(CORPUS)
    got = load(OUT)
    assert len(got["topics"]) == k
    assert len(got["documents"]) == len(corpus["docs"])
    for doc in got["documents"]:
        assert len(doc["theta"]) == k
        assert doc["theta"] == pytest.approx([abs(x) for x in doc["theta"]])
        assert sum(doc["theta"]) == pytest.approx(1.0)


def test_22_publish_checksum_exact():
    """snapshot_checksum is SHA-256 over corpus bytes, separator, then count bytes."""
    pipe()
    assert load(OUT)["snapshot_checksum"] == ref.checksum(
        CORPUS.read_bytes(), COUNTS.read_bytes()
    )


def test_23_export_snapshot_authority(tmp_path):
    """Export depends only on the state snapshots, not on later inbox edits."""
    pipe()
    before = OUT.read_bytes()
    sample = INBOX / "p1.json"
    old = sample.read_bytes()
    try:
        sample.write_text(json.dumps({"doc_id": "US-0000", "tokens": ["changed"]}))
        run(["export"])
        assert OUT.read_bytes() == before
    finally:
        sample.write_bytes(old)


def test_24_export_rejects_disagreeing_snapshots():
    """Export fails and leaves output untouched when the snapshots disagree."""
    pipe()
    before = OUT.read_bytes()
    counts = load(COUNTS)
    counts["doc_ids"] = list(reversed(counts["doc_ids"]))
    COUNTS.write_text(json.dumps(counts, separators=(",", ":")) + "\n")
    cp = run(["export"], check=False)
    assert cp.returncode != 0
    assert OUT.read_bytes() == before


# --- idempotency / process discipline ------------------------------------


def test_25_ingest_byte_and_mtime_idempotent():
    """Re-running ingest on unchanged input leaves bytes and mtime untouched."""
    reset()
    run(["ingest"])
    b = CORPUS.read_bytes()
    mt = CORPUS.stat().st_mtime_ns
    time.sleep(0.03)
    run(["ingest"])
    assert CORPUS.read_bytes() == b and CORPUS.stat().st_mtime_ns == mt


def test_26_sample_byte_and_mtime_idempotent():
    """Re-running sample on unchanged corpus leaves bytes and mtime untouched."""
    reset()
    run(["ingest"])
    run(["sample"])
    b = COUNTS.read_bytes()
    mt = COUNTS.stat().st_mtime_ns
    time.sleep(0.03)
    run(["sample"])
    assert COUNTS.read_bytes() == b and COUNTS.stat().st_mtime_ns == mt


def test_27_export_byte_and_mtime_idempotent():
    """Re-running export on unchanged state leaves bytes and mtime untouched."""
    pipe()
    b = OUT.read_bytes()
    mt = OUT.stat().st_mtime_ns
    time.sleep(0.03)
    run(["export"])
    assert OUT.read_bytes() == b and OUT.stat().st_mtime_ns == mt


def test_28_missing_prerequisites_fail_cleanly():
    """sample and export fail without creating artifacts when inputs are missing."""
    reset()
    assert run(["sample"], check=False).returncode != 0 and not COUNTS.exists()
    assert run(["export"], check=False).returncode != 0 and not OUT.exists()
    run(["ingest"])
    assert run(["export"], check=False).returncode != 0 and not OUT.exists()


def test_29_status_reads_state_not_output():
    """status reports from state snapshots and ignores a corrupted output file."""
    pipe()
    OUT.write_text("not-json")
    cp = run(["status"])
    assert "docs=6" in cp.stdout and "snapshot_checksum=" in cp.stdout


def test_30_config_hyperparameters_sourced():
    """The count snapshot records the configured topics, hyperparameters, and seed."""
    pipe()
    p = ref.params()
    counts = load(COUNTS)
    assert counts["k"] == p["k"]
    assert counts["alpha"] == pytest.approx(p["alpha"])
    assert counts["beta"] == pytest.approx(p["beta"])
    assert counts["seed"] == p["seed"]
    assert len(load(OUT)["topics"]) == p["k"]


def test_31_decoy_isolation_with_rebuild():
    """The TF-IDF decoy is never on the hot path; a panicking decoy still exports."""
    p = APP / "crates/ldacore/src/decoy/mod.rs"
    old = p.read_text()
    try:
        p.write_text('pub fn tfidf_preview() -> usize { panic!("decoy must stay off the hot path") }')
        rebuild()
        pipe()
        assert OUT.exists()
        assert load(OUT)["snapshot_checksum"] == ref.checksum(
            CORPUS.read_bytes(), COUNTS.read_bytes()
        )
    finally:
        p.write_text(old)
        rebuild()


# --- partial-profile traps ------------------------------------------------


def test_90_correct_corpus_only_still_fails_sampler():
    """Fixing only the corpus stage leaves the hidden count snapshot incorrect."""
    try:
        install_profile(False)
        for m in ("corpus", "vocab"):
            shutil.copyfile(PRIV / f"golden_lib/{m}.rs", APP / f"crates/ldacore/src/{MODULE_PATHS[m]}")
        rebuild()
        root = Path("/opt/verifier-fixtures/lda/lexical")
        pipe(root)
        assert load(CORPUS) == ref.corpus_staging(root)
        assert load(COUNTS)["assignments"] != ref.count_staging(load(CORPUS))["assignments"]
    finally:
        restore_snapshot()


def test_91_correct_counts_but_broken_retention_fails_hidden():
    """Fixing the count core but not retention leaves retained theta incorrect."""
    try:
        install_profile(False)
        for m in ("corpus", "vocab", "rng", "sampler", "ledger"):
            shutil.copyfile(PRIV / f"golden_lib/{m}.rs", APP / f"crates/ldacore/src/{MODULE_PATHS[m]}")
        rebuild()
        pipe(Path("/opt/verifier-fixtures/lda/burnin"))
        expected = ref.count_staging(load(CORPUS))
        got = load(COUNTS)
        assert got["assignments"] == expected["assignments"]
        assert got["retained_sweeps"] != expected["retained_sweeps"]
    finally:
        restore_snapshot()


def test_92_correct_counts_but_broken_publication_fails_export():
    """Fixing everything except ranking and publication yields a wrong rollup."""
    try:
        install_profile(True)
        for m in ("ranking", "publication"):
            shutil.copyfile(PRIV / f"broken_lib/{m}.rs", APP / f"crates/ldacore/src/{MODULE_PATHS[m]}")
        rebuild()
        pipe()
        assert load(OUT)["snapshot_checksum"] != ref.checksum(
            CORPUS.read_bytes(), COUNTS.read_bytes()
        )
    finally:
        restore_snapshot()


def test_99_full_golden_profile_reproduces_reference():
    """The complete golden profile reproduces the reference on a hidden corpus."""
    try:
        install_profile(True)
        root = Path("/opt/verifier-fixtures/lda/ranking")
        pipe(root)
        corpus = load(CORPUS)
        assert corpus == ref.corpus_staging(root)
        assert_counts_exact(load(COUNTS), ref.count_staging(corpus))
        expected = ref.rollup(CORPUS.read_bytes(), COUNTS.read_bytes())
        got = load(OUT)
        assert got["snapshot_checksum"] == expected["snapshot_checksum"]
        for gt, et in zip(got["topics"], expected["topics"]):
            assert [x["token"] for x in gt["top_terms"]] == [x["token"] for x in et["top_terms"]]
    finally:
        restore_snapshot()
