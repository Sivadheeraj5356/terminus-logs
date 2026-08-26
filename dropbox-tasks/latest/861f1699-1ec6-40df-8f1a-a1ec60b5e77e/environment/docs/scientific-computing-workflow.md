# Scientific computing workflow — CT violin acoustic FDTD

This repository ships CT cavity volumes and a working finite-difference acoustic
assay under /app/environment. The deliverable is a **numerical simulation with
lab calibration closure**: map cavity speeds, persist a mesh staging certificate,
advance a 2-D pressure field, recover spectral formant peaks with documented
reference math, and publish reports when prominence and frequency tolerances hold.

## Simulation stages

1. **Voxel speed map** — map air cavity (`0`) and wood shell (`1`) to laboratory
   wave speeds (`/app/docs/calibration_notes.md`, `/app/docs/format_contract.md`).
2. **Mesh staging** — write `/app/state/<profile>/cavity_mesh.json` per
   `/app/docs/cavity-mesh-staging.md` before any leapfrog step.
3. **Bridge excitation + leapfrog** — drive and advance pressure; sample the
   microphone cell into the export trace.
4. **Spectral formants** — FFT the trace; accept absolute-dB local maxima; keep
   four peaks; bind `cavity_speed_digest` from staging.
5. **Closure export** — write formants.json, pressure.wav, and summary.json when
   both CT stems close.

Operator commands: `/app/docs/assay-operator-commands.md`.
Grid constants: `/app/environment/include/ac_limits.h`.
Thresholds: `/app/environment/config/lab.toml`.
