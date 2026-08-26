# Build notes

The operations team expects this repository to behave like a small offline Go CLI package, not like a service. A clean checkout should support:

- `make test` for the project test suite.
- `make build` for a local command binary named `beacon-drift`.
- execution of the built command from outside the repository.

The command validates a beacon packet against a named profile. Profile data is repository configuration that must be available to the command after it is built; operators should not need to copy the `config` directory into their current working directory.

Expected CLI usage:

`beacon-drift --profile north-pier --input /path/to/packet.json --output /path/to/result.json`

Expected result shape includes `beacon_id`, `profile`, `accepted`, `reasons`, and `severity`. Invalid packets should return a successful process exit only when the command can inspect the packet and write a deterministic hold result. Structural command or IO problems may exit non-zero.
