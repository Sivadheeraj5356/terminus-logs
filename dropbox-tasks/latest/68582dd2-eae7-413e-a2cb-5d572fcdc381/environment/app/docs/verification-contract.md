# Verification contract

Behavioral verification exercises the documented restore workflow against manifests in `/app/manifests`. The operator entrypoint is `/app/bin/restore-bundle` with flags `--archives-dir`, `--manifest`, `--output`, `--idmap`, and `--log`. `python3 -m restore.restore_main` accepts the same flags and must agree with the wrapper on identical inputs. The pytest suite imports helper modules `fixture_factory` and `verifier_expect` from `/tests`. Platform verification reruns `/tests/test_outputs.py` with `pytest` and records CTRF output at `/logs/verifier/ctrf.json` using the `--ctrf` flag. Shipped restore behavior under `/app` must be repaired per the public contracts rather than bypassed with static artifacts.

## Input integrity

Visible inputs are locked by SHA-256 manifest `/tests/assets/input-manifest.json`. The verifier expects zero mismatches against archives, manifests, and docs under `/app`.

## Representative restore paths

The bundled manifests exercise these normalized restore paths under `/output/restore-root`:

- `simple/etc/config.json`
- `meta/var/cache/token`

Generated matrix cases build temporary archives under a scratch workspace created at runtime with prefix `generated-restore-case-` beneath `/tmp`.

## Hardlink verification

Grouped paths use manifest `hardlink_group` tokens such as `hl-shared`. Verifiers inspect `hardlink_groups`, require `shared_inode` to be true, and compare `nlink` against the number of paths in each group.

## Module entrypoint

`python3 -m restore.restore_main` must agree with `/app/bin/restore-bundle` on identical inputs. The module runs with `PYTHONPATH=/app/src:/app`.
