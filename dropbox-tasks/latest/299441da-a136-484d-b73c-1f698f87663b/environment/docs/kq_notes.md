# sccache kq_run release-lane notes

```bash
/app/environment/tools/kq_run --deck <deck_dir> --out <report.json>
```

Ingest writes `/app/output/kq_frames.ndjson`. Export (`zen_e`) reads that file and writes `/app/output/kq_report.json` plus `/app/output/kq_stage.ndjson` (reproducibility / SBOM staging).

See also `/app/environment/docs/build-cache-sbom-lockfile.md` for lockfile and supply-chain release-guard framing.

## Environment

- `KQ_DEFINE_BLOB`, `KQ_ARGV_WIRE`, `KQ_WRAP_BIN` — override fixture paths for pin-mismatch release gates
- `KQ_APPEND_CONTROL=1` — append empty-control wrap frame (metamorphic digest shift)
- `KQ_DENYLIST` — JSON with `blocked_keys` and `required_width`; argv suppression applies only at matching wire width

## Lock / attestation surfaces

- `kep_a(rank_path, reload_flag)` → dependency lock-tier `effective`, `tier`, `scope_hash`
  - `reload_flag == 0`: `scope_hash = len(effective)` (YAML highest tier)
  - `reload_flag > 0`: `scope_hash = len(effective) + tier` (rsp override path)
- `molt_b(bytes, 0)` argv wire; `molt_b(bytes, 2)` wrapper aggregate (sum or max per KQWH mode byte)
- `rune_c(bytes, _)` define-order decode; return `eff_tick` after flag scaling, sentinel `% 512`, proportional fold when sum > 512, then tighten (flag value 4 subtracts 1 per entry, minimum 1)
- `volt_d(so_path, _)` native bands; reconciled `(readelf_band + nm_band) // 2` (16 on the shipped witbit)
- `auth_f(argv_sum, wrap_head, epoch)` → `(argv_sum XOR wrap_head XOR (epoch * 31)) & 0xffff`; ingest writes the little-endian result to `/app/output/kq_auth.bin` using `base_a` argv and wrapper authorities
- `bind_h(argv_hc, wrap_hc, def_sum, epoch, scope_tier, auth_lane, frame_count)` → `(argv_hc*7 + wrap_hc*11 + def_sum + epoch*13 + scope_tier*3 + (auth_lane*5)%241 + (frame_count%17)*3) % 241` (`auth_lane` from `kq_auth.bin`; `frame_count` = non-`_meta` frames in the ingest stream)
- `lane_g(status_label)` → argv wire gate from scenario `argv_status`
- `zen_e(frames_path, _)` frames + auth lane → attestation rows + ledger_bind + staging digest (control wraps staging-only)

## Deck locals

Each deck directory may include `epoch.txt`, `rank_s0.yml`, and `*_resp.rsp` response files used under `--reload` for lockfile tier precedence.
