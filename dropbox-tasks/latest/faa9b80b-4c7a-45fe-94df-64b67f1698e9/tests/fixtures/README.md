# Verifier fixtures

Verifier tests copy the runtime dataset from `/app/data` (or the local
`environment/app/data` fallback) into a temporary directory and mutate that
copy for each scenario.

This directory intentionally contains no CSV/JSON data files. Canonical inputs
live in the task environment image under `/app/data`.
