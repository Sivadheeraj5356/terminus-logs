# Cipherwave incident materials

This directory contains the immutable evidence and normative contracts for one paused HLS key-rotation incident. The required deliverable is the six-file security audit packet described by `/app/docs/artifact-contract.md`; there is no application source tree to repair or service to run.

The authorities under `/app/fixtures/visible` are the incident's complete trust boundary. The registry manifest is a transport-neutral export of the signed and AES-GCM-wrapped key records. Media files, playlists, and the signed catalog provide the AES-CBC fragment evidence. Guardian trust and the signed rollout ledger provide amendment, revocation, checkpoint-quorum, and resilient-authorization evidence. The profile fixes the audit instant and expected current/candidate generations.
