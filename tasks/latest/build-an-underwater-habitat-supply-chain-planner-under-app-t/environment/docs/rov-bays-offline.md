# ROV bays offline

Optional habitat policy input that marks ROV bays out of service for the mission.

## habitat field

| Field | Type | Notes |
|-------|------|-------|
| rov_bays_offline | array | Optional. One-based bay numbers (1..rov_bays) that must not be assigned. When absent or empty, all bays are eligible. |

Included in mission_hash like every other habitat field (see habitat-profile.md).

## rule

ROV slot reservation (see rov-lead-time.md) selects a bay from the eligible set only:

1. Eligible bays are the one-based bay numbers 1..rov_bays that do NOT appear in rov_bays_offline.
2. Bay availability tracking (free times and rov_turn_min turnaround) is unchanged. Offline bays are simply never selected.
3. The chosen bay is the eligible bay minimizing (max(free[i], need), i) exactly as in rov-lead-time.md.
4. rov_id still uses the one-based number of the chosen bay (R1..RN).

Valid missions always leave at least one eligible bay. Offline bays never appear in rov-index.json slots.
