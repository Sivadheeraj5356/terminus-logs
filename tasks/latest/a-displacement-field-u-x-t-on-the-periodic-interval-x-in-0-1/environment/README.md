# telegraph — 1D damped wave solver

A small C project that integrates the damped wave (telegraph) equation

    u_tt + 2 g u_t = c^2 u_xx,   x in [0, 1)

on the periodic unit interval with wave speed `c` and damping rate `g`, released
from rest, and writes the field at a set of snapshot times. Each spatial mode
oscillates and decays: the amplitude of every wavenumber falls over time while
the constant part is preserved.

## Layout

    include/    public headers, one per module
      model.h     run description (c, g, grid size, Courant number, profile)
      json.h      flat-JSON reader for the input file
      config.h    assemble a Model from the JSON input
      grid.h      the pinned periodic grid x_i = i/N
      profile.h   evaluate the initial displacement profile u0(x)
      field.h     field allocation and simple mass/min/max diagnostics
      csvout.h    write the t,x,u,v snapshot file
      scheme.h    the time integrator (implemented in src/scheme.c)
    src/        one translation unit per header, plus main.c (the CLI driver)
    input/      example run descriptions (input/transport.json is the default)
    docs/       the input/output format

## Build and run

    make
    ./solver input/transport.json output/field.csv

`make` compiles every file under `src/` into the `solver` binary. The binary
takes the input JSON path and the output CSV path as its two arguments.

## What to implement

Every module is complete except the time integrator. `src/scheme.c` defines

    void scheme_advance(const Model *m, double *state, double t0, double t1);

which must advance the state in place from time `t0` to time `t1`. The state
array has length `2N`: the displacement `u` occupies `state[0 .. N-1]` and its
time derivative `u_t` occupies `state[N .. 2N-1]`. The starter leaves it empty,
so the untouched program reports the initial data (with zero velocity) unchanged
at every snapshot.
