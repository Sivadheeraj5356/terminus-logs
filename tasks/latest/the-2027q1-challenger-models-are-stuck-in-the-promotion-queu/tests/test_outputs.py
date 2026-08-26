"""Verifier for the 2027Q1 feature-audit migration.

The registry CLI rebuilds the project from source on every invocation, so every check here
exercises the code the agent actually wrote. Ground truth is never taken from the database the
agent migrated: the audit is rebuilt from a pristine copy of the seed registry, and two
independent mutations of the reference data prove the pipeline derives its answers from the
registry rather than reproducing a memorised result.
"""

import csv
import glob
import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

EXPORT = Path("/app/out/promotion_audit.csv")
REGISTRY = "/app/registry"
SEED = Path("/opt/aurora/seed/registry.mv.db")

# Resolve the toolchain explicitly rather than trusting the inherited environment.
JAVA_HOME = os.environ.get("JAVA_HOME") or "/opt/java/openjdk"
JAVA = shutil.which("java") or f"{JAVA_HOME}/bin/java"
ENV = {
    **os.environ,
    "JAVA_HOME": JAVA_HOME,
    "PATH": f"{JAVA_HOME}/bin:/opt/venv/bin:" + os.environ.get("PATH", "/usr/bin:/bin"),
    "MAVEN_OPTS": os.environ.get("MAVEN_OPTS", "-Dmaven.repo.local=/root/.m2/repository"),
}

HEADER = (
    "run_id,model_name,model_version,cohorts_evaluated,rows_considered,"
    "drifted_features,underpowered_rows,unscored_rows,max_psi,null_rate_p95,decision"
)

# SHA-256 of the canonical export, fixed by the promotion controls in the review dossier.
GOLDEN_SHA256 = "482af0f48f7bf762aac7c69c8651187c95adc7efd6067df9acb0efca0a59cb2d"

# Severity ranks recorded in promotion_decision; the export leads with the most severe.
DECISION_RANK = {"PROMOTE": 1, "HOLD": 2, "REJECT": 3}

# Observations that survive supersession and referential integrity.
EXPECTED_FEATURE_AUDIT_ROWS = 525

WITHHELD_RUNS = ["run_2027q1_0104", "run_2027q1_0112"]
RECOVERED_RUN = "run_2027q1_0109"


def h2_jar() -> str:
    """Locate the H2 jar in the pre-populated Maven repository."""
    jars = glob.glob("/root/.m2/repository/com/h2database/h2/*/h2-*.jar")
    jars += glob.glob("/app/target/lib/h2-*.jar")
    assert jars, "H2 jar not found"
    return jars[0]


def sql(db: str, statement: str) -> list[dict]:
    """Run a query against an H2 database and return its rows as dictionaries."""
    out = "/tmp/verifier_query.csv"
    Path(out).unlink(missing_ok=True)
    escaped = statement.replace("'", "''")
    script = f"CALL CSVWRITE('{out}', '{escaped}');"
    result = subprocess.run(
        [JAVA, "-cp", h2_jar(), "org.h2.tools.Shell",
         "-url", f"jdbc:h2:file:{db}", "-user", "sa", "-password", ""],
        input=script, capture_output=True, text=True, timeout=180, env=ENV,
    )
    assert result.returncode == 0, f"query failed: {result.stdout}\n{result.stderr}"
    with open(out, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def registry(*args: str) -> subprocess.CompletedProcess:
    """Invoke the registry CLI, which rebuilds the project from source before it runs."""
    return subprocess.run(
        [REGISTRY, *args], cwd="/app", capture_output=True, text=True, timeout=600, env=ENV,
    )


def sha256(path: Path) -> str:
    """Checksum a file's exact bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rebuild(workdir: Path, mutation: str | None = None) -> Path:
    """Rebuild the audit from the pristine seed, optionally mutating the reference data first."""
    workdir.mkdir(parents=True, exist_ok=True)
    db = workdir / "registry"
    shutil.copyfile(SEED, workdir / "registry.mv.db")
    if mutation:
        result = subprocess.run(
            [JAVA, "-cp", h2_jar(), "org.h2.tools.Shell",
             "-url", f"jdbc:h2:file:{db}", "-user", "sa", "-password", ""],
            input=mutation, capture_output=True, text=True, timeout=180, env=ENV,
        )
        assert result.returncode == 0, f"mutation failed: {result.stdout}"

    applied = registry("migrate", "--db", str(db))
    assert applied.returncode == 0, f"migrate failed:\n{applied.stdout}\n{applied.stderr}"
    exported = registry("export", "--db", str(db), "--out", str(workdir / "out.csv"))
    assert exported.returncode == 0, f"export failed:\n{exported.stdout}\n{exported.stderr}"
    return workdir / "out.csv"


@pytest.fixture(scope="session")
def scratch(tmp_path_factory) -> Path:
    """Session scratch directory for rebuilt databases."""
    return tmp_path_factory.mktemp("aurora")


@pytest.fixture(scope="session")
def rebuilt_export(scratch) -> Path:
    """The export produced by rebuilding the registry from the pristine seed."""
    return rebuild(scratch / "pristine")


@pytest.fixture(scope="session")
def export_rows() -> list[dict]:
    """The agent's export, parsed."""
    assert EXPORT.exists(), f"{EXPORT} was not produced"
    with open(EXPORT, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_export_file_exists():
    """The canonical export is written to /app/out/promotion_audit.csv."""
    assert EXPORT.exists(), f"{EXPORT} does not exist"
    assert EXPORT.stat().st_size > 0, f"{EXPORT} is empty"


def test_export_is_canonically_encoded():
    """The export is UTF-8 with no BOM, LF line endings, and exactly one trailing newline."""
    raw = EXPORT.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "export carries a UTF-8 BOM"
    assert b"\r" not in raw, "export contains carriage returns; line endings must be LF"
    assert raw.endswith(b"\n"), "export must end with a newline"
    assert not raw.endswith(b"\n\n"), "export must not end with a blank line"
    raw.decode("utf-8")


def test_export_header_is_exact():
    """The first line of the export is the contracted header, verbatim."""
    first = EXPORT.read_text(encoding="utf-8").split("\n")[0]
    assert first == HEADER, f"header mismatch\n  expected: {HEADER}\n  actual:   {first}"


def test_export_numeric_rendering(export_rows):
    """max_psi carries 4 decimals, null_rate_p95 carries 6, and the counts are plain integers."""
    assert export_rows, "export has no data rows"
    for row in export_rows:
        assert re.fullmatch(r"\d+\.\d{4}", row["max_psi"]), (
            f"max_psi must have exactly 4 decimal places, got {row['max_psi']!r} "
            f"for {row['run_id']}"
        )
        assert re.fullmatch(r"\d+\.\d{6}", row["null_rate_p95"]), (
            f"null_rate_p95 must have exactly 6 decimal places, got "
            f"{row['null_rate_p95']!r} for {row['run_id']}"
        )
        for column in ("cohorts_evaluated", "rows_considered", "drifted_features",
                       "underpowered_rows", "unscored_rows"):
            assert re.fullmatch(r"\d+", row[column]), (
                f"{column} must be a plain integer, got {row[column]!r} for {row['run_id']}"
            )
        assert row["decision"] in {"PROMOTE", "HOLD", "REJECT"}, (
            f"unknown decision {row['decision']!r} for {row['run_id']}"
        )


def test_export_is_ordered_by_severity_then_run_id(export_rows):
    """Export rows lead with the most severe determination, then run_id ascending within it."""
    actual = [(row["decision"], row["run_id"]) for row in export_rows]
    expected = sorted(actual, key=lambda pair: (-DECISION_RANK[pair[0]], pair[1]))
    assert actual == expected, (
        "export rows are not ordered by determination severity (most severe first) "
        f"and then run_id.\n  actual:   {actual}\n  expected: {expected}"
    )


def test_null_rate_percentile_is_nearest_rank(export_rows):
    """null_rate_p95 is an observed null rate, as the nearest-rank method requires."""
    for row in export_rows:
        run = row["run_id"]
        observed = sql("/app/data/registry",
                       "SELECT null_rate FROM feature_audit "
                       f"WHERE run_id = '{run}'")
        rates = {round(float(item["NULL_RATE"]), 6) for item in observed}
        reported = round(float(row["null_rate_p95"]), 6)
        assert reported in rates, (
            f"null_rate_p95 for {run} is {reported}, which is not one of that run's observed "
            "null rates - an interpolated percentile invents a value that was never measured"
        )


def test_export_matches_golden_checksum():
    """The export reproduces the promotion audit byte for byte (SHA-256 against the golden copy)."""
    actual = sha256(EXPORT)
    assert actual == GOLDEN_SHA256, (
        "export checksum mismatch - the promotion audit does not match the board's copy.\n"
        f"  expected {GOLDEN_SHA256}\n  actual   {actual}"
    )


def test_schema_version_records_v7_once():
    """The bundle load is recorded in the ledger exactly once, as version 7."""
    rows = sql("/app/data/registry", "SELECT version FROM schema_version ORDER BY version")
    versions = [int(row["VERSION"]) for row in rows]
    assert 7 in versions, f"version 7 is not recorded in schema_version: {versions}"
    assert versions.count(7) == 1, f"version 7 recorded {versions.count(7)} times: {versions}"


def test_feature_audit_holds_surviving_observations():
    """feature_audit holds exactly the observations that survive supersession and integrity checks."""
    rows = sql("/app/data/registry", "SELECT COUNT(*) AS n FROM feature_audit")
    assert int(rows[0]["N"]) == EXPECTED_FEATURE_AUDIT_ROWS, (
        f"feature_audit holds {rows[0]['N']} rows, expected {EXPECTED_FEATURE_AUDIT_ROWS}"
    )


def test_quarantined_member_is_not_ingested():
    """Observations from the quarantined bundle member never reach the audit table."""
    by_value = sql("/app/data/registry",
                   "SELECT COUNT(*) AS n FROM feature_audit "
                   "WHERE psi > 0.6099 AND psi < 0.6101")
    assert int(by_value[0]["N"]) == 0, "rows from the quarantined member were ingested"

    by_instant = sql("/app/data/registry",
                     "SELECT COUNT(*) AS n FROM feature_audit "
                     "WHERE observed_at = TIMESTAMP '2027-03-01 12:00:00'")
    assert int(by_instant[0]["N"]) == 0, "rows from the quarantined member were ingested"


def test_referential_integrity_is_enforced():
    """Observations naming an unknown run, feature, or cohort alias are discarded on load."""
    unknown_run = sql("/app/data/registry",
                      "SELECT COUNT(*) AS n FROM feature_audit "
                      "WHERE run_id NOT IN (SELECT run_id FROM model_run)")
    assert int(unknown_run[0]["N"]) == 0, "feature_audit references a run that is not registered"

    unknown_feature = sql("/app/data/registry",
                          "SELECT COUNT(*) AS n FROM feature_audit "
                          "WHERE feature_id NOT IN (SELECT feature_id FROM feature_catalog)")
    assert int(unknown_feature[0]["N"]) == 0, "feature_audit references an unregistered feature"

    unknown_cohort = sql("/app/data/registry",
                         "SELECT COUNT(*) AS n FROM feature_audit "
                         "WHERE cohort_id NOT IN (SELECT cohort_id FROM cohort_register)")
    assert int(unknown_cohort[0]["N"]) == 0, "feature_audit references an unregistered cohort"


def test_legacy_units_are_normalised():
    """Legacy observations are converted from basis points and ppm and keyed by cohort id."""
    rows = sql("/app/data/registry",
               "SELECT psi, null_rate, source FROM feature_audit "
               "WHERE run_id = 'run_2027q1_0111' "
               "AND feature_id = 'fa_postal_deprivation_index' "
               "AND cohort_id = 'ch_high_value'")
    assert len(rows) == 1, "the legacy observation for run_2027q1_0111 was not loaded"
    assert rows[0]["SOURCE"] == "legacy"
    assert float(rows[0]["PSI"]) == pytest.approx(0.1450, abs=1e-9), (
        "legacy psi was not converted from basis points"
    )
    assert float(rows[0]["NULL_RATE"]) == pytest.approx(0.0121, abs=1e-9), (
        "legacy null rate was not converted from parts per million"
    )


def test_stability_index_is_recomputed_from_the_bins(export_rows):
    """Observations with a distribution input carry a PSI recomputed from their bins, floored, not the raw column."""
    # The recomputed index for each affected observation, floored at 0.0005 on the empty bin.
    expected = {
        ("run_2027q1_0105", "fa_open_litigation_flag", "ch_legacy_motor"): 0.2306446101,
        ("run_2027q1_0109", "fa_housing_price_index", "ch_core_auto"): 0.2911986519,
        ("run_2027q1_0111", "fa_cpi_yoy_delta", "ch_core_auto"): 0.3270092307,
    }
    for (run, feature, cohort), value in expected.items():
        rows = sql("/app/data/registry",
                   "SELECT psi FROM feature_audit "
                   f"WHERE run_id = '{run}' AND feature_id = '{feature}' AND cohort_id = '{cohort}'")
        assert len(rows) == 1, f"the recomputed observation for {run}/{feature} was not loaded"
        assert float(rows[0]["PSI"]) == pytest.approx(value, abs=1e-6), (
            f"the stability index for {run}/{feature} was not recomputed from its bins; a raw or "
            "differently-floored value gives a different figure"
        )

    # The recomputed value is the one that reaches the export as the run's peak stability.
    by_run = {row["run_id"]: row for row in export_rows}
    assert by_run["run_2027q1_0105"]["max_psi"] == "0.2306"
    assert by_run["run_2027q1_0109"]["max_psi"] == "0.2912"
    assert by_run["run_2027q1_0111"]["max_psi"] == "0.3270"


def test_supersession_keeps_the_latest_observation():
    """Where a natural key repeats, the latest observation survives and CSV wins an exact tie."""
    later = sql("/app/data/registry",
                "SELECT psi, source FROM feature_audit WHERE run_id = 'run_2027q1_0106' "
                "AND feature_id = 'fa_policy_tenure_months' AND cohort_id = 'ch_core_auto'")
    assert len(later) == 1, "supersession left more than one row for a natural key"
    assert float(later[0]["PSI"]) == pytest.approx(0.0904, abs=1e-9), (
        "the superseded (earlier) observation survived"
    )

    tie = sql("/app/data/registry",
              "SELECT psi, source FROM feature_audit WHERE run_id = 'run_2027q1_0108' "
              "AND feature_id = 'fa_coverage_limit_ratio' AND cohort_id = 'ch_core_home'")
    assert len(tie) == 1, "supersession left more than one row for a natural key"
    assert tie[0]["SOURCE"] == "csv", "the legacy observation won a tie it should have lost"
    assert float(tie[0]["PSI"]) == pytest.approx(0.1004, abs=1e-9)


def test_quoted_member_is_parsed_as_rfc4180_csv():
    """The bundle member that quotes every field is parsed, not split blindly on commas."""
    stray = sql("/app/data/registry",
                "SELECT COUNT(*) AS n FROM feature_audit "
                "WHERE run_id LIKE '%\"%' OR feature_id LIKE '%\"%' OR cohort_id LIKE '%\"%'")
    assert int(stray[0]["N"]) == 0, (
        "quote marks leaked into the identifiers: the quoted CSV member was split on commas "
        "without honouring RFC 4180 quoting"
    )
    # An observation that only exists in the quoted member must have survived the load.
    quoted = sql("/app/data/registry",
                 "SELECT psi FROM feature_audit WHERE run_id = 'run_2027q1_0101' "
                 "AND feature_id = 'fa_deductible_band' AND cohort_id = 'ch_core_auto'")
    assert len(quoted) == 1, "the observation carried only by the quoted member was not loaded"


def test_amendment_binds_only_from_its_effective_date(export_rows):
    """The provisional-cohort surcharge reaches observations recorded on or after it took effect."""
    decisions = {row["run_id"]: row["decision"] for row in export_rows}

    # These two carry a provisional-cohort observation recorded before the surcharge was enacted;
    # under the rule in force at the time it is not a drift finding.
    for run in ("run_2027q1_0101", "run_2027q1_0107"):
        assert decisions[run] == "PROMOTE", (
            f"{run} was penalised under an amendment that did not yet exist when its features "
            "were scored"
        )

    # This one carries a provisional-cohort observation recorded after the surcharge took effect.
    assert decisions["run_2027q1_0108"] == "HOLD", (
        "run_2027q1_0108 drifts in a provisional cohort under the surcharge in force by then"
    )


def test_provisional_surcharge_is_withdrawn_after_its_sunset(export_rows):
    """The provisional surcharge is withdrawn from its sunset date; later observations use the plain threshold."""
    decisions = {row["run_id"]: row["decision"] for row in export_rows}

    # Each of these carries a provisional-cohort observation recorded after the surcharge was
    # withdrawn, sitting between the surcharged threshold and the plain family threshold: it drifts
    # only if the withdrawn surcharge is still (wrongly) applied. Under the rule in force it does not
    # drift, so the run clears.
    for run in ("run_2027q1_0101", "run_2027q1_0107"):
        assert decisions[run] == "PROMOTE", (
            f"{run} was penalised under the provisional surcharge after it had been withdrawn; "
            "an observation recorded past the surcharge's sunset must use the plain family threshold"
        )

    # The post-sunset observations were still ingested into the audit, just not surcharged.
    for run, cohort in (("run_2027q1_0101", "ch_pilot_ev"), ("run_2027q1_0107", "ch_smb_fleet")):
        rows = sql("/app/data/registry",
                   "SELECT observed_at FROM feature_audit "
                   f"WHERE run_id = '{run}' AND feature_id = 'fa_prior_claim_count' "
                   f"AND cohort_id = '{cohort}'")
        assert len(rows) == 1, f"the post-sunset observation for {run} was not loaded"
        assert rows[0]["OBSERVED_AT"].startswith("2027-03"), (
            f"the post-sunset observation for {run} was not recorded in March"
        )


def test_telemetry_tightening_is_rescinded_after_its_sunset(export_rows):
    """Once the telemetry tightening is rescinded, later telemetry observations use the general threshold again."""
    decisions = {row["run_id"]: row for row in export_rows}

    # run_2027q1_0102 carries a telemetry observation recorded after the tightening was rescinded,
    # sitting between the tightened 0.15 figure and the general 0.20. It drifts only if the
    # rescinded telemetry figure is still applied; under the general threshold in force it does not.
    assert decisions["run_2027q1_0102"]["drifted_features"] == "1", (
        "run_2027q1_0102's post-rescission telemetry observation raised a drift finding; once A-11 "
        "is rescinded a later telemetry observation is judged against the general threshold"
    )

    rows = sql("/app/data/registry",
               "SELECT observed_at FROM feature_audit WHERE run_id = 'run_2027q1_0102' "
               "AND feature_id = 'fa_telematics_night_ratio' AND cohort_id = 'ch_core_home'")
    assert len(rows) == 1 and rows[0]["OBSERVED_AT"].startswith("2027-03"), (
        "the post-rescission telemetry observation for run_2027q1_0102 was not loaded"
    )


def test_regulated_portfolio_amendment_overrides_the_narrative(export_rows):
    """The amendment log admits acr_severity_gbm to the regulated portfolio despite clause 8.1."""
    decisions = {row["run_id"]: row["decision"] for row in export_rows}

    # run_2027q1_0106 is an acr_severity_gbm run carrying a sensitive-attribute drift finding.
    # Clause 8.1's narrative reads as though acr_severity_gbm is not regulated, but the amendment
    # log governs and admits it, so the conduct override fires and rejects the run outright.
    assert decisions["run_2027q1_0106"] == "REJECT", (
        "run_2027q1_0106 drifts on a sensitive feature and its model is in the regulated "
        "portfolio per the authoritative amendment log; the conduct override must reject it"
    )

    # A run of the same model with no sensitive drift is not swept up by the override.
    assert decisions["run_2027q1_0101"] == "PROMOTE", (
        "the conduct override fired on a run that carries no sensitive-attribute drift"
    )


def test_telemetry_threshold_amendment_binds_from_its_date(export_rows):
    """The telemetry family's enacted threshold applies only from its effective date."""
    decisions = {row["run_id"]: row["decision"] for row in export_rows}

    # run_2027q1_0110 carries a telemetry observation recorded after the amendment took effect,
    # below the general 0.20 but at or above the enacted telemetry figure, so it drifts.
    assert decisions["run_2027q1_0110"] == "HOLD", (
        "run_2027q1_0110's telemetry observation is at or above the enacted telemetry threshold "
        "and must raise a drift finding"
    )

    # run_2027q1_0101 carries a telemetry observation in the same band but recorded before the
    # amendment took effect; under the general threshold in force then it is not a drift finding.
    assert decisions["run_2027q1_0101"] == "PROMOTE", (
        "run_2027q1_0101 was penalised under the telemetry threshold before it took effect"
    )


def test_legacy_extracts_are_read_by_column_name(export_rows):
    """Both legacy extracts load correctly even though their columns are in different orders."""
    later = sql("/app/data/registry",
                "SELECT psi, sample_count, source FROM feature_audit "
                "WHERE run_id = 'run_2027q1_0106' AND feature_id = 'fa_open_litigation_flag' "
                "AND cohort_id = 'ch_core_home'")
    assert len(later) == 1, (
        "the observation carried by the second legacy extract was not loaded; its columns are "
        "in a different order from the first extract and must be read by header name"
    )
    assert later[0]["SOURCE"] == "legacy"
    assert float(later[0]["PSI"]) == pytest.approx(0.2400, abs=1e-9), (
        "the second legacy extract was read by column position, so the values landed in the "
        "wrong fields"
    )
    assert int(later[0]["SAMPLE_COUNT"]) == 3000


def test_adequacy_floor_and_threshold_are_inclusive(export_rows):
    """An observation at exactly 500 samples is scored, and one exactly at the threshold drifts."""
    decisions = {row["run_id"]: row for row in export_rows}

    # 500 samples is not "below 500", and 0.2000 is "at or above" the 0.20 threshold.
    assert decisions["run_2027q1_0103"]["decision"] == "HOLD", (
        "the observation at exactly the adequacy floor and exactly at the threshold must drift"
    )
    assert decisions["run_2027q1_0103"]["max_psi"] == "0.2000", (
        "the boundary observation was excluded from the scored set"
    )

    # One sample below the floor, and hot: underpowered, so it never raises a drift finding.
    hot = sql("/app/data/registry",
              "SELECT psi, sample_count FROM feature_audit "
              "WHERE run_id = 'run_2027q1_0115' AND feature_id = 'fa_telematics_night_ratio' "
              "AND cohort_id = 'ch_high_value'")
    assert len(hot) == 1 and int(hot[0]["SAMPLE_COUNT"]) == 499
    assert decisions["run_2027q1_0115"]["drifted_features"] == "3", (
        "an underpowered observation raised a drift finding despite being below the floor"
    )


def test_withheld_runs_receive_no_determination(export_rows):
    """Runs whose latest event is an abort are withheld; a run that recovered is not."""
    ids = {row["run_id"] for row in export_rows}
    for run in WITHHELD_RUNS:
        assert run not in ids, f"{run} aborted terminally and must not be in the promotion audit"
    assert RECOVERED_RUN in ids, (
        f"{RECOVERED_RUN} aborted and was then re-run to completion; it must be audited"
    )


def test_systemic_feature_escalates_a_hold_to_reject(export_rows):
    """A run held for review is escalated to reject when it drifts on a cycle-wide systemic feature."""
    by_run = {row["run_id"]: row for row in export_rows}

    # run_2027q1_0114 carries a single drift finding, is not in the regulated portfolio, and its
    # peak stability is well under the hard ceiling, so on its own facts it is a manual-review hold.
    # It is rejected only because its drifted feature is systemic across the cycle (it drifts in
    # three or more distinct runs), which a per-run reading of the run in isolation cannot see.
    row = by_run["run_2027q1_0114"]
    assert row["drifted_features"] == "1", "run_2027q1_0114 should carry exactly one drift finding"
    assert float(row["max_psi"]) < 0.50, "run_2027q1_0114's peak stability is below the hard ceiling"
    assert row["decision"] == "REJECT", (
        "run_2027q1_0114 drifts on a feature that is systemic across the cycle and must be escalated "
        "from a hold to a rejection; deciding the run in isolation leaves it a hold"
    )

    # A run that drifts on the same feature but was already rejected on its own facts is untouched.
    assert by_run["run_2027q1_0116"]["decision"] == "REJECT"

    # Systemic status is counted over distinct runs, not drift findings. run_2027q1_0102 and
    # run_2027q1_0108 both carry a drift on the same feature, and that feature accounts for three
    # drift findings in total, but across only two distinct runs — so it is not systemic and neither
    # run is escalated. Counting findings instead of runs would wrongly reject both.
    assert by_run["run_2027q1_0102"]["decision"] == "HOLD", (
        "run_2027q1_0102 was escalated on a feature that drifts in only two distinct runs; the "
        "systemic count is over distinct runs, not the number of drift findings"
    )
    assert by_run["run_2027q1_0108"]["decision"] == "HOLD", (
        "run_2027q1_0108's drifted feature is not systemic across the cycle; it must remain a hold"
    )


def test_promotion_audit_table_agrees_with_the_export(export_rows):
    """The exported file is a rendering of promotion_audit, not an independent artefact."""
    rows = sql("/app/data/registry",
               "SELECT run_id, model_name, model_version, cohorts_evaluated, rows_considered, "
               "drifted_features, underpowered_rows, unscored_rows, decision "
               "FROM promotion_audit ORDER BY run_id")
    assert len(rows) == len(export_rows), (
        f"promotion_audit holds {len(rows)} rows but the export has {len(export_rows)}"
    )
    by_run = {row["RUN_ID"]: row for row in rows}
    for file_row in export_rows:
        table_row = by_run.get(file_row["run_id"])
        assert table_row is not None, (
            f"{file_row['run_id']} is in the export but not in promotion_audit"
        )
        for column in ("run_id", "model_name", "model_version", "cohorts_evaluated",
                       "rows_considered", "drifted_features", "underpowered_rows",
                       "unscored_rows", "decision"):
            assert str(table_row[column.upper()]) == file_row[column], (
                f"{column} disagrees between promotion_audit and the export "
                f"for {file_row['run_id']}"
            )


def test_rebuild_from_the_pristine_seed_reproduces_the_audit(rebuilt_export):
    """Migrating a pristine seed registry from scratch reproduces the same canonical export."""
    actual = sha256(rebuilt_export)
    assert actual == GOLDEN_SHA256, (
        "rebuilding the registry from the seed did not reproduce the promotion audit; "
        "the result is not derived from the bundle and the registry.\n"
        f"  expected {GOLDEN_SHA256}\n  actual   {actual}"
    )


def test_migration_and_export_are_idempotent(scratch, rebuilt_export):
    """Re-running the migration applies nothing further and the export stays byte-stable."""
    workdir = scratch / "pristine"
    db = str(workdir / "registry")

    before = rebuilt_export.read_bytes()
    again = registry("migrate", "--db", db)
    assert again.returncode == 0, f"second migrate failed:\n{again.stdout}\n{again.stderr}"

    rows = sql(db, "SELECT COUNT(*) AS n FROM schema_version WHERE version = 7")
    assert int(rows[0]["N"]) == 1, "the second migration recorded version 7 a second time"

    audit = sql(db, "SELECT COUNT(*) AS n FROM feature_audit")
    assert int(audit[0]["N"]) == EXPECTED_FEATURE_AUDIT_ROWS, (
        "the second migration rewrote the audit table"
    )

    rebuilt_export.unlink()
    reexport = registry("export", "--db", db, "--out", str(rebuilt_export))
    assert reexport.returncode == 0, f"second export failed:\n{reexport.stderr}"
    assert rebuilt_export.read_bytes() == before, "the export is not byte-stable"


def test_feature_catalog_drives_the_evaluation(scratch):
    """Retiring a feature from monitoring changes the determinations that depended on it."""
    export = rebuild(
        scratch / "unmonitored",
        "UPDATE feature_catalog SET monitored = FALSE WHERE feature_id = 'fa_claim_severity_p90';",
    )
    with open(export, newline="", encoding="utf-8") as handle:
        rows = {row["run_id"]: row for row in csv.DictReader(handle)}
    assert sha256(export) != GOLDEN_SHA256, (
        "the audit ignored the feature catalog: unmonitoring a feature changed nothing"
    )
    assert rows["run_2027q1_0116"]["decision"] == "PROMOTE", (
        "run_2027q1_0116 was rejected on a feature that is no longer monitored"
    )
    assert rows["run_2027q1_0114"]["decision"] == "PROMOTE", (
        "run_2027q1_0114 still carries a drift finding on an unmonitored feature"
    )


def test_cohort_register_drives_the_scoping(scratch):
    """Reinstating the suspended cohort brings its observations into scope."""
    export = rebuild(
        scratch / "reinstated",
        "UPDATE cohort_register SET status = 'ACTIVE' WHERE cohort_id = 'ch_shadow_test';",
    )
    with open(export, newline="", encoding="utf-8") as handle:
        rows = {row["run_id"]: row for row in csv.DictReader(handle)}
    assert sha256(export) != GOLDEN_SHA256, (
        "the audit ignored cohort status: reinstating a suspended cohort changed nothing"
    )
    for run in ("run_2027q1_0107", "run_2027q1_0114"):
        assert rows[run]["decision"] == "REJECT", (
            f"{run} should be rejected once the reinstated cohort's observations are in scope"
        )
