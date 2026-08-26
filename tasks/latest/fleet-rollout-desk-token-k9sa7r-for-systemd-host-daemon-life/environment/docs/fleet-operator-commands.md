# Fleet operator commands

Rebuild after source edits (toolchain at /usr/local/cargo/bin/cargo):

```bash
cd /app/environment
cargo build --release --locked
```

The grading harness runs the same rebuild before pytest so updated sources
take effect even when the desk-run is not rerun manually. This is the fleet
daemon lifecycle path for socket-activation start-race desks on systemd hosts.

## k9_invoke

```bash
/app/environment/tools/k9_invoke --scenario N
```

Desk-run one scenario. N must be the integer index 0 through 3 (the sN
directory name is only a fixture path). Caches rows under
/app/desk-state/epoch_N.json. Re-invoking the same scenario is repeat-stable
when barrier sequence is consistent. sk8 slot files under /app/desk-state/signal/
are keyed per scenario index plus xfer source (sN-source.slot); reuse
does not cross scenario indices.

## k9_emit

```bash
/app/environment/tools/k9_emit --out /app/output/k9_trace.json
```

Rebuild flags: cargo build --release --locked from /app/environment.

Emit the cross-phase operational seal when checkpoint state is valid and every
WAL line CRC matches its payload.

## k9_recover

```bash
/app/environment/tools/k9_recover
```

Rebuild checkpoint validity from the WAL append log. Double recover is
repeat-stable.

## Cases

Scenario fixtures live under /app/cases/seq/s0 through /app/cases/seq/s3.
Each scenario directory ships a0.evt, b0.evt, and p0.res snapshots with
whitespace-separated key=value fields. The reservation snapshot p0.res
carries tail, epoch, rank_a, and rank_b inputs that drive xr4 sampling
and sequence tie-breaks.

The platform verifier may invoke pytest with harness-only logging flags such as
--ctrf; those flags are not part of the trace contract.

Two consecutive k9_emit runs after the same desk-run must produce identical
chain_fingerprint values.
