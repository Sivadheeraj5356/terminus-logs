# Architecture

The analytics engine is organized as a batch pipeline that loads static facility
configuration, merges heterogeneous event CSV feeds into one timeline, applies
events to mutable facility state, and emits a JSON census report.

## Data flow

```text
CSV inputs (admissions, transfers, procedures, discharges)
        │
        ▼
   parser ──► merged, ordered event stream
        │
        ▼
   validator ──► dispatches each event to a domain handler
        │
        ├── admissions
        ├── transfers
        ├── procedures
        └── discharge handling
        │
        ▼
   state + beds ──► patient records, assignments, occupancy, rejections
        │
        ▼
   analytics + reports ──► summary, patients, ward_occupancy JSON
```

## Modules

| Module | Responsibility |
| --- | --- |
| `parser` | Load CSV rows, normalize events, merge and order the global timeline |
| `validator` | Enforce event-id uniqueness and route events to handlers |
| `admissions` | Create patients and initial bed assignments |
| `transfers` | Move patients between wards when transfers complete |
| `beds` | Track physical beds, ward capacity limits, and ICU eligibility |
| `procedures` | Accumulate completed procedure counts and minutes |
| `state` | Patient and facility snapshots used across handlers |
| `analytics` | Derive census metrics and length-of-stay at `as_of` |
| `reports` | Serialize the final JSON document |

Static inputs `beds.csv` and `capacity.csv` are loaded before event processing
begins. Handlers mutate shared `FacilityState`; analytics reads that state after
all events are applied.

## Design constraints

- Processing is single-threaded and deterministic.
- Handlers record rejections instead of panicking on rule violations.
- The report reflects patient state **as of** the configured census timestamp,
  not merely the final post-event snapshot when discharge timing differs.
