# Hospital analytics fixtures

Fixed census snapshot timestamp:

as_of: 2024-06-20T18:00:00Z

See `/app/docs/data_contract.md` for the full output schema. Column definitions:

## admissions.csv

| column | type | notes |
| --- | --- | --- |
| admission_id | string | unique admission identifier |
| patient_id | string | patient identifier |
| event_time | string | ISO-8601 UTC timestamp |
| event_seq | integer | tie-breaker within identical timestamps |
| event_id | string | globally unique event identifier |
| acuity_level | integer | 1 critical, 2 urgent, 3 routine |
| preferred_ward | string | ward code from capacity.csv |

## transfers.csv

| column | type | notes |
| --- | --- | --- |
| transfer_id | string | unique transfer identifier |
| patient_id | string | patient identifier |
| event_time | string | ISO-8601 UTC timestamp |
| event_seq | integer | tie-breaker |
| event_id | string | globally unique event identifier |
| from_ward | string | source ward |
| to_ward | string | destination ward |
| status | string | completed, pending, or partial |

## procedures.csv

| column | type | notes |
| --- | --- | --- |
| procedure_id | string | unique procedure identifier |
| patient_id | string | patient identifier |
| event_time | string | ISO-8601 UTC timestamp |
| event_seq | integer | tie-breaker |
| event_id | string | globally unique event identifier |
| procedure_code | string | procedure code |
| duration_minutes | integer | minutes for completed procedures |
| status | string | scheduled, completed, or cancelled |

## discharges.csv

| column | type | notes |
| --- | --- | --- |
| discharge_id | string | unique discharge identifier |
| patient_id | string | patient identifier |
| event_time | string | ISO-8601 UTC timestamp |
| event_seq | integer | tie-breaker |
| event_id | string | globally unique event identifier |
| disposition | string | home, transfer_facility, or deceased |

## beds.csv

| column | type | notes |
| --- | --- | --- |
| bed_id | string | unique bed identifier |
| ward | string | ward code |
| is_icu | string | true or false |
| status | string | available or maintenance |

## capacity.csv

| column | type | notes |
| --- | --- | --- |
| ward | string | ward code |
| max_beds | integer | maximum concurrent patients allowed in the ward |
