# Cedar Fork field hydrologists need Muskingum channel-storage routing of each flo

- **UUID:** `fdf2a9e0-9794-46f9-b759-4a2c0cbdcc9c`
- **Slug:** `cedar-fork-field-hydrologists-need-muskingum-channel-storage`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Cedar Fork field hydrologists need Muskingum channel-storage routing of each flood wave down a dendritic channel network: the peak discharge (m³/s), the time-to-peak (h), and the outflow hydrograph (m³/s) at every admitted channel reach. Each reach stores and delays its flow by a storage time K (hours) and a weighting factor X in [0, 0.5], and the network shares a routing step dt_hours and an admission floor peak_min_cms on the rounded peak discharge.

A storage pass marches an outflow series O[t] from the reach effective inflow I[t] through the Muskingum recurrence O[t] = C0·I[t] + C1·I[t−1] + C2·O[t−1], with the weights C0, C1, C2 formed from K, X, and dt_hours. The reach effective inflow gathers its headwater boundary series or the routed outflow arriving from the reaches above it, together with any lateral inflow marks; the peak discharge is the largest rounded outflow and the time-to-peak is the step index of that first maximum times dt_hours.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
