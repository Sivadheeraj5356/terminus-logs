# resume_witness.json shape

The witness document has two top-level sections named summary and rows.

The summary section lists which fixtures and profiles were exercised and how many fixture-profile pairs ran.

Each rows entry carries fixture id, profile name, mode label (uninterrupted or resume), an eight-character lowercase hex curve_digest, plus numeric band_drift and band_tail fields.

Profile strict_pair uses the slower coefficient table with tighter band limits. Profile rapid_k uses the shorter-stride table with extended coefficients. There are no boolean verdict fields; graders derive pass or fail from digest agreement and band limits.
