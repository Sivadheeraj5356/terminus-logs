# Provenance Dossier Schema — Station Audit Series, Form PD-4

Standing requirement of SOP-9 §6: any remediation of the spectral service must be
accompanied by a provenance dossier reconstructing the decision record that the
remediation relies on. The dossier is a single JSON object written to
`/app/audit/provenance_dossier.json`. It must contain exactly the four top-level
objects below, each containing exactly the listed keys. Values must be derived
from the station archive (`/app/archive/`) and the `registry` schema of the
`meridian` database; where the two disagree, the precedence rules of SOP-9 §3
govern. All dates are ISO `YYYY-MM-DD` strings. All counts are JSON integers.
Version strings are given exactly as they appear in Maven coordinates.

Object and key names must be reproduced from this document letter for letter —
audits have been returned unread for renamed keys. The required shape, with
placeholder values, is:

```json
{
  "build_provenance": {
    "approved_jdbc_version": "",
    "rescinded_jdbc_versions": [""],
    "rescinding_advisory": "",
    "rescinding_advisory_issued": "",
    "jdbc_versions_ever_board_approved": 0,
    "jdbc_approval_missing_minute": "",
    "emergency_jdbc_version_never_approved": "",
    "emergency_change_applied_on": "",
    "emergency_change_reverted_on": "",
    "math_library_coordinate": "",
    "math4_migration_status": "",
    "json_library_version": "",
    "unresolvable_coordinates_count": 0,
    "noncompliant_resolvable_coordinates_count": 0,
    "pom_revision_entries_recorded": 0,
    "pom_revisions_reverted_count": 0
  },
  "query_compliance": {
    "binding_mandate_memo": "",
    "binding_mandate_effective": "",
    "concat_call_sites_in_query_service": 0,
    "quoted_channel_identifier": "",
    "quoted_channel_incident": ""
  },
  "spectral_method": {
    "adopted_smp_revision": "",
    "rescinded_smp_revision": "",
    "rescinding_erratum": "",
    "interim_fallback_revision": "",
    "band_count_adopted": 0,
    "burst_band_bounds_hz": [0.0, 0.0],
    "segment_length": 0,
    "segment_hop": 0,
    "window_normalization": ""
  },
  "registry_reconciliation": {
    "advisories_total_recorded": 0,
    "advisories_registered_in_db": 0,
    "advisories_never_registered": 0,
    "advisories_in_force_at_freeze": 0,
    "foreign_advisories_cited": 0,
    "audit_freeze_date": ""
  }
}
```

Note on tense: several fields describe the service working tree *as shipped* —
the state the auditor found, not the state after remediation. Record those
values from the tree as found, before changing anything.

## Object `build_provenance`

| Key | Type | Definition |
|---|---|---|
| `approved_jdbc_version` | string | The `org.postgresql:postgresql` version whose board approval is in force at the audit freeze date. |
| `rescinded_jdbc_versions` | array of strings | Every `org.postgresql:postgresql` version that received a board approval which was later rescinded. Ascending version order. |
| `rescinding_advisory` | string | Identifier of the advisory under which those approvals were rescinded. |
| `rescinding_advisory_issued` | string | Issue date of that advisory. |
| `jdbc_versions_ever_board_approved` | integer | Count of distinct `org.postgresql:postgresql` versions that ever received a board approval, regardless of later rescission. Versions that entered service without a board approval do not count. |
| `jdbc_approval_missing_minute` | string | Minute reference cited for a JDBC approval whose minute document is absent from `/app/archive/minutes/`. |
| `emergency_jdbc_version_never_approved` | string | The `org.postgresql:postgresql` version that was placed into service and later removed without ever receiving a board approval. |
| `emergency_change_applied_on` | string | The date that version entered service. |
| `emergency_change_reverted_on` | string | The date the emergency change was unwound. |
| `math_library_coordinate` | string | Full `groupId:artifactId:version` of the numerical library approval in force at the freeze date. |
| `math4_migration_status` | string | Disposition of the commons-math 4.x migration question as of the freeze date, per the governing record. One of `adopted`, `deferred`, `rejected`. |
| `json_library_version` | string | The `jackson-databind` version whose approval is in force at the freeze date. |
| `unresolvable_coordinates_count` | integer | Count of dependency coordinates in the shipped `/app/service/pom.xml` that name an artifact version which does not exist in the station Maven repository at all. |
| `noncompliant_resolvable_coordinates_count` | integer | Count of dependency coordinates in the shipped `/app/service/pom.xml` that resolve against the station Maven repository but whose version stands rescinded at the freeze date. |
| `pom_revision_entries_recorded` | integer | Count of engineering journal entries that record a pom revision (each such entry states that a pom revision was recorded). |
| `pom_revisions_reverted_count` | integer | Count of recorded pom revisions that were subsequently reverted by a later recorded pom revision. |

## Object `query_compliance`

| Key | Type | Definition |
|---|---|---|
| `binding_mandate_memo` | string | Identifier of the memo that mandates bound parameters for statements touching the `telemetry` schema. |
| `binding_mandate_effective` | string | Effective date stated in that memo. |
| `concat_call_sites_in_query_service` | integer | Count of call sites in the shipped `/app/service/src/main/java/org/mrgo/spectra/QueryService.java` that execute SQL assembled by string concatenation. Constant SQL strings executed without concatenation do not count. |
| `quoted_channel_identifier` | string | The station channel identifier, recorded verbatim, whose punctuation first exposed the interpolation defect. |
| `quoted_channel_incident` | string | Identifier of the incident report that recorded that failure. |

## Object `spectral_method`

| Key | Type | Definition |
|---|---|---|
| `adopted_smp_revision` | string | Single letter of the SMP-7 revision in force at the freeze date. |
| `rescinded_smp_revision` | string | Single letter of the SMP-7 revision rescinded by erratum. |
| `rescinding_erratum` | string | Identifier of that erratum. |
| `interim_fallback_revision` | string | Single letter of the revision that governed between the rescission and the adoption of the revision in force at the freeze date. |
| `band_count_adopted` | integer | Number of reporting bands defined by the revision in force at the freeze date. |
| `burst_band_bounds_hz` | array of two numbers | `[lower, upper]` bounds in Hz of the `burst` band under the revision in force at the freeze date. |
| `segment_length` | integer | Analysis segment length in samples under the revision in force at the freeze date. |
| `segment_hop` | integer | Segment advance in samples under the revision in force at the freeze date. |
| `window_normalization` | string | Denominator of the periodogram scaling under the revision in force at the freeze date. One of `sum_w_squared` (fs times the sum of squared window samples), `segment_length` (fs times the segment length), `squared_length` (fs times the squared segment length). |

## Object `registry_reconciliation`

| Key | Type | Definition |
|---|---|---|
| `advisories_total_recorded` | integer | Count of distinct station advisories recorded anywhere in the station archive or in `registry.advisory_register`, deduplicated by identifier. |
| `advisories_registered_in_db` | integer | Count of advisories carried as rows of `registry.advisory_register`. |
| `advisories_never_registered` | integer | Count of station advisories recorded in the archive that were never entered in `registry.advisory_register`. |
| `advisories_in_force_at_freeze` | integer | Count of distinct advisories that are in force at the freeze date. An advisory is in force if it was issued on or before the freeze date and its recorded status at the freeze date is none of withdrawn, superseded, closed, or pending. |
| `foreign_advisories_cited` | integer | Count of distinct advisories of other stations cited anywhere in the station archive. Foreign advisories are not station advisories (SOP-9 §2) and must not be included in any other count of this object. |
| `audit_freeze_date` | string | The Station Systems Freeze date defined by SOP-9. |
