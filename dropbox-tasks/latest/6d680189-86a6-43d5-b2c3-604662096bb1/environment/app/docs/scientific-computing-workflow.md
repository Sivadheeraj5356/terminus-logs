# Scientific computing workflow

This repository is a numerical device-physics calibration lab for GAA nanosheet compact models. The scientific objective is calibration closure: measured IV and CV sweeps must agree with compact-model predictions within the tolerances in /app/docs/validation-schema.md after coordinate-descent fitting under /app/docs/parameter-bounds.md and /app/docs/compact-model.md.

Measurement fixtures under /app/data/bundled are already readable by the lab kernel. The remaining scientific work is sealed calibration snapshot construction with the measure digest, geometry rollup with aspect weights per /app/docs/geometry-rollup.md, compact-model drain-current and capacitance equations including contact-drop self-consistency and k1 body-factor scaling, coordinate-descent parameter estimation across geometry groups, and emission of the foundry SPICE card plus validation digest. Normative schemas live in /app/docs/tapeout-schema.md and /app/docs/spice-card.md. Lab entry points and absolute overlay roots are documented in /app/docs/lab-calibration-commands.md and /app/docs/measurement-source-overlays.md.


