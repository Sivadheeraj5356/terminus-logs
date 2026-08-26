This is a scientific-computing bioinformatics task: predict RNA secondary structure under the RNPX-12 folding model.

RNPX-12 scores folded RNA structures using thermodynamic parameters, chemical-probing reactivity, and guide-channel evidence. For each RNA instance, determine the maximum-scoring secondary structure and report the scientific audit records required by `/app/docs/model_reference.md`.

The public RNA instance is `/app/input_data/rna_public.txt`, and the thermodynamic parameter tables are under `/app/thermo`. The same predictor must work for any valid RNPX-12 RNA instance and compatible parameter set of the same format.

The model reference defines the input grammar, parameter-table codec, scoring rules, probe/audit conventions, and output grammar. The reported structure, score, and audit records must match that reference exactly.

Put the C++17 predictor source at `/app/src/fold.cpp`. It is evaluated with strict C++17 warning settings and invoked as `./fold <rna_file>`.
