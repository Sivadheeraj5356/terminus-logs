# Producing the answers

The program is built from `solver.rs`, which does not yet exist in `/app` and is
written from scratch. Running `make` in the app directory builds it with

```
rustc -O -o solver solver.rs
```

and then runs it on `data/set_01.txt`, leaving the answers under `outputs/`. The
program takes the path to a problem file as its only argument and writes its
answers to standard output, so any of the batches under `data/` or `examples/`
can be run directly, for example

```
./solver data/set_02.txt
```

Only the Rust standard library is available and the build runs with no network
access.
