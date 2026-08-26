"""The repaired policy must implement the documented semantics, not just the
shipped sample: it is evaluated over a second ledger corpus that exercises
boundary and multi-artifact corners the sample never reaches."""

import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ledger_ref

POLICY_DIR = "/app/policy"
INPUT_PATH = "/tmp/deployed_policy_input.json"


def _digest(tag):
    """Deterministic per-fixture digest derived from a short tag."""
    return hashlib.sha256(tag.encode()).hexdigest()


def _dep(name, ecosystem, version, **overrides):
    """A ledger dependency with unremarkable defaults, then overrides."""
    entry = {
        "name": name,
        "ecosystem": ecosystem,
        "version": version,
        "license": "MIT",
        "channel": "stable",
        "provenance": "verified",
        "lock_generation": 52,
        "scope": "runtime",
        "origin": "direct",
        "install_scripts": False,
        "artifacts": [],
    }
    entry.update(overrides)
    return entry


def _deployed_input():
    """A deployed-corpus input document exercising the documented corners."""
    dependencies = [
        _dep("acme/reranker-base", "huggingface", "v4.1.0", scope="build", artifacts=[
            {"path": "registry/acme/reranker-base/config.json", "digest": _digest("t1-a")},
            {"path": "registry/acme/reranker-base/vocab.txt", "digest": _digest("t1-b")},
            {"path": "registry/acme/reranker-base/weights.meta", "digest": _digest("t1-c-pinned")},
        ]),
        _dep("acme/segmenter", "huggingface", "v2.0.1", scope="build", artifacts=[
            {"path": "registry/acme/segmenter/config.json", "digest": _digest("t2-a")},
            {"path": "registry/acme/segmenter/rules.bin", "digest": _digest("t2-b")},
        ]),
        _dep("acme/toxicity-head", "huggingface", "v1.2.0", scope="build", artifacts=[
            {"path": "registry/acme/toxicity-head/config.json", "digest": _digest("t3-a")},
        ]),
        _dep("acme/lang-id", "huggingface", "v3.3.0", scope="build", artifacts=[
            {"path": "registry/acme/lang-id/config.json", "digest": _digest("t4-a")},
        ]),
        _dep("fastify", "npm", "4.28.1", lock_generation=50),
        _dep("pino", "npm", "9.3.1", lock_generation=49),
        _dep("gpl-vendored-grammar", "npm", "3.1.4", license="GPL-3.0-only"),
        _dep("readline-gpl-shim", "pypi", "6.2.1", license="GPL-3.0-only"),
        _dep("orchid-lint-rules", "pypi", "0.4.0",
             license="LicenseRef-Orchid-Internal", scope="dev"),
        _dep("orchid-seal", "go", "v1.0.3",
             license="LicenseRef-Orchid-Internal", scope="build"),
        _dep("hono", "npm", "4.5.0-beta.2", channel="beta"),
        _dep("undici-preview", "npm", "7.0.0-beta.1", channel="beta",
             provenance="unverified", origin="transitive"),
        _dep("croner-edge", "npm", "9.0.0-beta.4", channel="beta",
             provenance="unverified"),
        _dep("opa-wasm-runtime", "pypi", "0.9.0.dev4", channel="nightly", scope="build"),
        _dep("opa-wasm-runtime", "pypi", "0.9.0.dev6", channel="nightly",
             provenance="unverified", scope="build"),
        _dep("esbuild-canary", "npm", "0.21.0-nightly.88", channel="nightly", scope="build"),
        _dep("iniparse-shim", "pypi", "1.1.0", provenance="absent",
             lock_generation=0, origin="transitive", scope="build"),
        _dep("yaml-legacy", "go", "v2.4.0", provenance="absent",
             lock_generation=0, scope="build"),
        _dep("sharp-libvips", "npm", "1.0.4", install_scripts=True, origin="transitive"),
        _dep("chi", "go", "v5.1.0"),
    ]
    hash_report = {
        "registry/acme/reranker-base/config.json": _digest("t1-a"),
        "registry/acme/reranker-base/vocab.txt": _digest("t1-b"),
        "registry/acme/reranker-base/weights.meta": _digest("t1-c-actual"),
        "registry/acme/segmenter/config.json": _digest("t2-a"),
        "registry/acme/toxicity-head/config.json": _digest("t3-a"),
        "registry/acme/lang-id/config.json": _digest("t4-a"),
    }
    quarantine = [
        {"kind": "artifact", "ecosystem": "", "name": "",
         "digest": _digest("t3-a"), "status": "active", "clause": "QR-2311"},
        {"kind": "artifact", "ecosystem": "", "name": "",
         "digest": _digest("t4-a"), "status": "lifted", "clause": "QR-2178"},
        {"kind": "package", "ecosystem": "pypi", "name": "iniparse-shim",
         "digest": "", "status": "lifted", "clause": "QR-2050"},
    ]
    return {
        "generation": 52,
        "dependencies": dependencies,
        "hash_report": hash_report,
        "quarantine": quarantine,
    }


def _evaluate(doc):
    """Run the agent's policy bundle over the document with the OPA engine."""
    with open(INPUT_PATH, "w") as f:
        json.dump(doc, f)
    result = subprocess.run(
        ["opa", "eval", "--format", "json", "-d", POLICY_DIR, "-i", INPUT_PATH,
         "data.orchid.ledger.report"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"opa eval failed: {result.stderr[:800]}"
    payload = json.loads(result.stdout)
    return payload["result"][0]["expressions"][0]["value"]


def test_policy_generalizes_to_deployed_corpus():
    """Over the deployed corpus the policy reproduces the in-force decision,
    reasons, and annotations for every dependency."""
    doc = _deployed_input()
    actual = _evaluate(doc)
    expected = ledger_ref.expected_report(doc)
    actual_by_key = {
        (d["ecosystem"], d["name"], d["version"]): d
        for d in actual.get("decisions", [])
    }
    mismatches = []
    for want in expected["decisions"]:
        key = (want["ecosystem"], want["name"], want["version"])
        if actual_by_key.get(key) != want:
            mismatches.append((key, want, actual_by_key.get(key)))
    assert not mismatches, f"{len(mismatches)} decisions diverge: {mismatches[:4]}"
    assert len(actual["decisions"]) == len(expected["decisions"])


def test_deployed_report_ordering_and_generation():
    """The deployed-corpus report keeps contract ordering and the generation."""
    doc = _deployed_input()
    actual = _evaluate(doc)
    expected = ledger_ref.expected_report(doc)
    assert actual["generation"] == expected["generation"]
    actual_keys = [
        (d["ecosystem"], d["name"], d["version"]) for d in actual["decisions"]
    ]
    expected_keys = [
        (d["ecosystem"], d["name"], d["version"]) for d in expected["decisions"]
    ]
    assert actual_keys == expected_keys
