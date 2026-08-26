# Ambergate assay ledger — overview

Ambergate performs numeric thermodynamic reconstruction of bulk Au–Ag–Cu alloy composition regions for historical coins from:

1. Measured bulk density with uncertainty
2. Surface XRF composition with uncertainty
3. A surface-enrichment (silver bloom) correction model
4. Pure-metal reference densities and a mixing rule

Bulk density alone cannot uniquely determine a three-metal composition: the mixing constraint defines a one-dimensional curve (band under uncertainty) in the two-simplex. XRF samples only the surface, which for aged silver alloys is often silver-enriched relative to bulk. The ledger therefore reports feasible regions (or inconsistency / insufficient-data), never a single collapsed point estimate that hides under-determination.

Pipeline stages: load → density band → surface correction → intersect → classify → emit.
