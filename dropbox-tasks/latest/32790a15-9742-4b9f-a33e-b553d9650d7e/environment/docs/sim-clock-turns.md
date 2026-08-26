# Sim-clock turns

All turn, retrieval, tool, instruction, and failure clock fields use inclusive upper bounds: keep records when the field is `<= cutoff`.

Diagnostic helpers under `wincontam::opsdash` (including `pairwise_overlap`) are not a substitute for this gate.
