The Express API at `/app/api` provides simulated accelerometer data through the POST `/simulate` endpoint. The physics team says the damped-oscillator readings don't match the expected model. The model is a standard damped harmonic oscillator. Investigate the simulation code under `/app/api/src/`, identify and fix all root causes in the TypeScript source.

After fixing the source, rebuild the TypeScript with `npx tsc` and launch the server so it runs on port 3000 as a background daemon. The server must remain running and responsive throughout validation — the verifier will query it via its HTTP endpoints. After starting the server, write a note at `/app/.fix-applied` naming the changed file and describing what you changed and why.

The verifier checks three physical properties: the damping envelope corresponds to the correct physical units, energy is properly conserved between time and frequency domains (Parseval's theorem), and the signal baseline has zero constant offset.
