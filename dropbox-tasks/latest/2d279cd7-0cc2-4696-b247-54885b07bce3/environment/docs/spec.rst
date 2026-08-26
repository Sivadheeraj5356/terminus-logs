2D Wave Integrator — Physics Overview
=====================================

This file summarizes the physical model. The full executable contract — CLI flags,
checkpoint layout, per-step ordering, output schema, and numeric tolerances — is
documented in ``/app/docs/pde_contract.md``.

The integrator solves the 2D wave equation with leapfrog time stepping and
2nd- or 4th-order spatial Laplacian stencils. Edge types (Dirichlet and Neumann)
are loaded from halo fixtures under ``/app/fixtures/``. Pulse parameters come from
``/app/fixtures/source_layout.json``.

Run simulations with::

    node /app/run_entry.js <config.json> <output.json>
