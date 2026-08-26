# Runtime base rationale

Fabert is an R-language task whose required agent entry point is /app/analysis.R. The runtime uses the sanctioned canonical Python 3.13 slim image because the approved B2 canonical base list does not include an R image, while the verifier is a pinned Python pytest harness. R is installed with apt only so /app/analysis.R can run inside the canonical base. Python is present for verifier execution and package validation only, not as the task solution language.
