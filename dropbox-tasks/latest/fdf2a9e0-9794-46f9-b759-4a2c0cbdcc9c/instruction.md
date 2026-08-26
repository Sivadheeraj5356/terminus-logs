Cedar Fork field hydrologists need Muskingum channel-storage routing of each flood wave down a dendritic channel network: the peak discharge (m³/s), the time-to-peak (h), and the outflow hydrograph (m³/s) at every admitted channel reach.
Each reach stores and delays its flow by a storage time K (hours) and a weighting factor X in [0, 0.5], and the network shares a routing step dt_hours and an admission floor peak_min_cms on the rounded peak discharge.
A storage pass marches an outflow series O[t] from the reach effective inflow I[t] through the Muskingum recurrence O[t] = C0·I[t] + C1·I[t−1] + C2·O[t−1], with the weights C0, C1, C2 formed from K, X, and dt_hours.
The reach effective inflow gathers its headwater boundary series or the routed outflow arriving from the reaches above it, together with any lateral inflow marks; the peak discharge is the largest rounded outflow and the time-to-peak is the step index of that first maximum times dt_hours.
The basin geometry, each reach K and X, the routing step, the admission floor, and the event inflow marks arrive packed in a little-endian binary field survey at `/app/data/survey.bin`.
Field desk context is in `/app/data/field_protocol.md`, and the survey byte layout, the Muskingum weight formulas, the half-even three-decimal rounding rule, and the quantity field and record order are in `/app/docs/channel_hydrograph_contract.md`.
How many storage passes each reach is advanced through, the timing with which upstream reach outflow and lateral marks enter a reach effective inflow, the exact peak-floor boundary, and how a reach that fails the floor affects the reaches below it are fixed by the twelve worked surveys under `/app/calibration/`.

Reading the survey at `/app/data/survey.bin`, `/app/bin/channel-route /app/data/survey.bin` must apply the Cedar Fork routing conventions per `/app/docs/channel_hydrograph_contract.md` and print the routed quantities as JSON on standard output.
Apply the same conventions to the held-out survey fixtures evaluated during grading.
Each folder under `/app/calibration/` ships one worked survey with its measured target quantities.
