# SDK ABI index release

Lane-oriented C++/CMake release pipeline. IDL fragments under `idl/` feed
`tools/genabi`, which emits a per-lane header and layout JSON. The matrix
driver under `runbook/` configures each lane, probes the compiled record, and
writes the public artifacts under `/app/output/sdk-abi-index`.

See `docs/sdk-contract.md` for the public command and artifact schemas.
