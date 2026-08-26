Edge and domain rules
=====================

Boundary schema
---------------

Halo fixtures under /app/fixtures/ declare per-edge types (Dirichlet or Neumann).
The mixed profile combines reflective and fixed edges on different sides of the
domain. Corner cells follow the horizontal-then-vertical precedence described in
the contract.

Configuration paths
-------------------

- /app/config/defaults.json — baseline simulation parameters
- /app/fixtures/halo_configuration.json — default edge profile
- /app/fixtures/halo_mixed.json — mixed edge profile
- /app/fixtures/source_layout.json — initial pulse shape

Operational limits
------------------

Interior domains up to 1024 cells per side are supported. Checkpoint bundles are
written to paths supplied on the command line (for example /app/work/sim.ckpt).

Transient working files created during a run should be removed once processing
completes. File descriptors opened for configuration or output must be closed
after use.

Numerical fidelity
------------------

Physical reference comparisons use the absolute tolerance documented in
/app/docs/pde_contract.md. Mixed-edge and multi-order workloads must remain
finite over long horizons without late-stage amplitude blowup.
