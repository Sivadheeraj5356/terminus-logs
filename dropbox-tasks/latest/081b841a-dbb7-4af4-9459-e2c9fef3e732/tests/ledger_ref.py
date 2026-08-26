"""Reference implementation of the in-force Orchid build-ledger gate rules.

Recomputes the decision every ledger dependency must receive, straight from the
ledger fixtures, so the verifier never trusts a shipped golden file.
"""

PERMISSIVE = {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC"}
WEAK_COPYLEFT = {"MPL-2.0", "LGPL-3.0-only", "EPL-2.0"}
STRONG_COPYLEFT = {"GPL-3.0-only", "AGPL-3.0-only", "SSPL-1.0"}

STALE_GAP = 2  # stale only when the lockfile trails by MORE than this many generations

# In-force exception clauses after every amendment in the handbook changelog.
LICENSE_WAIVERS = [
    {
        "clause": "EX-107",
        "ecosystem": "pypi",
        "name": "readline-gpl-shim",
        "versions": {"6.2.1", "6.2.2"},
        "scopes": {"build"},
    },
    {
        "clause": "EX-131",
        "ecosystem": "npm",
        "name": "gpl-vendored-grammar",
        "versions": {"3.1.0", "3.1.4"},
        "scopes": {"runtime", "build", "dev"},
    },
]

CHANNEL_EXCEPTIONS = [
    {
        "clause": "EX-118",
        "ecosystem": "pypi",
        "name": "opa-wasm-runtime",
        "versions": {"0.9.0.dev4", "0.9.0.dev6"},
    },
]


def license_class(license_id):
    """Classify an SPDX license id into the handbook's four classes."""
    if license_id in PERMISSIVE:
        return "permissive"
    if license_id in WEAK_COPYLEFT:
        return "weak-copyleft"
    if license_id in STRONG_COPYLEFT:
        return "strong-copyleft"
    return "unclassified"


def _waiver_applies(dep):
    """True when an active license waiver covers this package, version and scope."""
    return any(
        w["ecosystem"] == dep["ecosystem"]
        and w["name"] == dep["name"]
        and dep["version"] in w["versions"]
        and dep["scope"] in w["scopes"]
        for w in LICENSE_WAIVERS
    )


def _channel_exception_applies(dep):
    """True when an active nightly exception covers this package and version."""
    return dep["provenance"] == "verified" and any(
        c["ecosystem"] == dep["ecosystem"]
        and c["name"] == dep["name"]
        and dep["version"] in c["versions"]
        for c in CHANNEL_EXCEPTIONS
    )


def decide(dep, generation, hash_report, quarantine):
    """Return the (decision, reasons, annotations) triple for one dependency."""
    reasons = set()
    notes = set()

    # Quarantine: package entries match on ecosystem+name, artifact entries on
    # any pinned digest of the dependency.
    digests = {a["digest"] for a in dep.get("artifacts", [])}
    for q in quarantine:
        if q["kind"] == "package":
            hit = q["ecosystem"] == dep["ecosystem"] and q["name"] == dep["name"]
        else:
            hit = q["digest"] in digests
        if hit and q["status"] == "active":
            reasons.add("quarantined")
        if hit and q["status"] == "lifted":
            notes.add("quarantine-lifted")

    # Model integrity: every pinned artifact must be present in the hash report
    # and match it exactly.
    if dep["ecosystem"] == "huggingface":
        for a in dep.get("artifacts", []):
            if a["path"] not in hash_report:
                reasons.add("artifact-missing")
            elif hash_report[a["path"]] != a["digest"]:
                reasons.add("digest-mismatch")

    # License class rules.
    cls = license_class(dep["license"])
    if cls == "strong-copyleft":
        if _waiver_applies(dep):
            notes.add("license-exception")
        else:
            reasons.add("license-blocked")
    elif cls == "weak-copyleft":
        if dep["scope"] == "runtime":
            notes.add("license-review")
    elif cls == "unclassified":
        if dep["scope"] == "dev":
            notes.add("license-unclassified")
        else:
            reasons.add("license-unclassified")

    # Release channel rules.
    if dep["channel"] == "beta":
        notes.add("channel-beta")
        if (
            dep["scope"] == "runtime"
            and dep["origin"] == "direct"
            and dep["provenance"] != "verified"
        ):
            reasons.add("channel-unverified-beta")
    elif dep["channel"] == "nightly":
        if _channel_exception_applies(dep):
            notes.add("channel-exception")
        else:
            reasons.add("channel-nightly")

    # Lockfile provenance rules.
    if dep["provenance"] == "absent":
        if dep["origin"] == "direct":
            reasons.add("provenance-absent")
        else:
            notes.add("provenance-absent")
    elif dep["provenance"] == "unverified":
        notes.add("provenance-unverified")
    elif dep["provenance"] == "verified":
        if generation - dep["lock_generation"] > STALE_GAP:
            notes.add("provenance-stale")

    # npm install-script rules.
    if dep["ecosystem"] == "npm" and dep.get("install_scripts"):
        notes.add("npm-install-scripts")
        if dep["origin"] == "transitive" and dep["provenance"] != "verified":
            reasons.add("npm-untrusted-scripts")

    decision = "reject" if reasons else ("annotate" if notes else "approve")
    return decision, sorted(reasons), sorted(notes)


def expected_report(doc):
    """Build the full expected decisions report from a policy-input document."""
    deps = sorted(
        doc["dependencies"], key=lambda d: (d["ecosystem"], d["name"], d["version"])
    )
    decisions = []
    for dep in deps:
        decision, reasons, notes = decide(
            dep, doc["generation"], doc["hash_report"], doc["quarantine"]
        )
        decisions.append(
            {
                "name": dep["name"],
                "ecosystem": dep["ecosystem"],
                "version": dep["version"],
                "decision": decision,
                "reasons": reasons,
                "annotations": notes,
            }
        )
    return {"generation": doc["generation"], "decisions": decisions}
