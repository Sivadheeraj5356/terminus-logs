# Device characterization contract

This repository holds the scientific-computing lab calibration workflow for GAA nanosheet tape-out. The characterization kernel performs numerical device physics and compact-model fitting that closes measured IV and CV sweeps against fitted model predictions within documented tolerances. The end-to-end scientific workflow is summarized in /app/docs/scientific-computing-workflow.md.

The workflow loads lab measurement inputs, runs the numerical kernel described in /app/docs/compact-model.md, and publishes a SPICE card plus validation report for scientific signoff. Sources under /app/tb3 implement that kernel. Calibration snapshots decouple measurement characterization from compact-model fitting so model-fit operates on the sealed calibration tapeout together with parameter bounds.

Reference math for thermal voltage, contact-drop fixed-point iteration, subthreshold and above-threshold drain current, gate capacitance, coordinate-descent optimization, and RMSE closure is normative in the cited docs. Published artifacts must match those formulas within the tolerances defined in /app/docs/validation-schema.md.


