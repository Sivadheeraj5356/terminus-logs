# LINKS.md - link shaping provisioning reference

This document is the complete reference for the link shaping provisioner. It
covers the registry record layout, the interface API, the shaping and
smoothing arithmetic, the derived per-interface figures, the account and file
contracts, the manifest schema, and the manifest seal.

## 1. Overview

The host carries tenant egress traffic on a fleet of shaped network
interfaces. Each active interface keeps a state directory named after it
under /var/lib/link-rate. The link ledger registry in Redis carries, for
every interface the fleet has ever run, a packed history of daily egress
volume. A small HTTP API serves the interface list, the per-interface
metadata, and the shaping adjustments that operations applies on top of the
raw ledger figures.

Provisioning an interface means materializing its account, its state
directory, its networkd drop-in, and its policy environment file from the
ledger, then recording the run in a sealed manifest. Interfaces are
provisioned in the order the API lists them.

## 2. Registry layout in Redis

Redis listens on 127.0.0.1 port 6379 and holds two kinds of keys.

`link:index` is a Redis list holding every interface id in registry order.
This order is fixed, it is the order ledger rows are chained in the seal, and
it is not the same as the API list order.

`link:ledger:<iface_id>` is one binary string per interface:

| offset | size | field |
|--------|------|-------|
| 0      | 4    | magic, the ASCII bytes LKR1 |
| 4      | 1    | version, always 1 |
| 5      | 1    | flags, bit 0 set means the interface is detached |
| 6      | 2    | day_count, little-endian u16 |
| 8      | var  | payload, day_count varints, one per day, day 0 first |
| end    | 2    | checksum, big-endian u16, the sum of the payload bytes modulo 65521 |

Each varint is an unsigned MSB-first base-128 varint: the high bit is set on
every byte except the last, and the seven value bits of each byte arrive most
significant group first. The decoded value is the raw egress volume figure
for that day, in kilobytes moved. Day counts differ from interface to
interface.

## 3. Interface API

The API listens on 127.0.0.1 port 8080. Both it and Redis come up with
/app/scripts/start-services.sh.

- `GET /health` returns a liveness document.
- `GET /links` returns the interface list in provisioning order. Each entry
  carries `iface_id`, `display_name`, `uid`, and `tier`. The tier is one of
  `background`, `general`, or `express`.
- `GET /links/{iface_id}` returns the one entry for that interface.
- `GET /shaping/{iface_id}` returns `{"ops": [...]}`, the ordered shaping
  adjustments for that interface. The list may be empty.

Shaping adjustments must be fetched from the running API for every interface
the API lists. The private documents backing the API are not part of the
task interface.

## 4. Shaping adjustments

Each op object has an `op` field and applies to a single integer value `v`,
strictly in list order:

- `{"op": "scale", "num": N, "den": D}` replaces `v` with `floor(v * N / D)`.
- `{"op": "add", "k": K}` replaces `v` with `v + K`.
- `{"op": "floor", "k": K}` replaces `v` with `K` when `v < K`, otherwise
  leaves it unchanged.

For every interface, every day value in its ledger passes through that
interface's full op list. The result for day `d` is called `adjusted_d`.
Applying the ops in a different order gives different numbers, the order in
the shaping document is the only correct one.

## 5. Smoothing

Each interface's adjusted series is smoothed into the series `s` with a
carried remainder. The carry starts at zero and persists from day to day:

- `s_0 = adjusted_0`
- for `d >= 1`, let `t = 5 * s_(d-1) + adjusted_d + carry`, then
  `s_d = floor(t / 6)` and the new carry is `t mod 6`.

The smoothed volume `s_d` is the figure every downstream computation uses.
Dropping the carry gives systematically drifting values, the carry is part of
the definition.

The per-day transfer weight is `w_d = ceil(s_d / 1500)`, the number of 1500
kilobyte transfer windows the smoothed volume fills.

### Worked example, ops and smoothing

Raw series 9000, 6000, 10200 with ops
`[{"op": "scale", "num": 3, "den": 2}, {"op": "add", "k": 120},
{"op": "floor", "k": 10000}]`:

- adjusted = 13620, 10000, 15420
- `s_0 = 13620`, carry 0
- day 1: `t = 5 * 13620 + 10000 + 0 = 78100`, `s_1 = 13016`, carry 4
- day 2: `t = 5 * 13016 + 15420 + 4 = 80504`, `s_2 = 13417`, carry 2
- weights: 10, 9, 9

## 6. Per-interface shaping values

For each active interface, over its full smoothed series:

- `peak` is the largest `s_d`.
- `total_units` is the sum of all `w_d`.
- `rate_kbit` starts from the tier base, 2000 for background, 5000 for
  general, 12000 for express, plus `floor(total_units / 40000)`, and is then
  capped at the tier ceiling, 3500 for background, 8000 for general, 18000
  for express.
- `burst_kib` is `ceil(peak / 5500)`, raised to 24 when it comes out lower.

## 7. Accounts and files

For every active interface, in API list order:

- a unix group named `<iface_id>` with gid equal to the interface uid,
- a user named `<iface_id>` with that uid and gid, shell
  `/usr/sbin/nologin`, home directory `/var/lib/link-rate/<iface_id>`,
- the directory `/var/lib/link-rate/<iface_id>`, owned by that user and
  group, mode 0750,
- the drop-in `/etc/systemd/network/40-<iface_id>.network` containing
  exactly:

```
[Match]
Name=<iface_id>

[TokenBucketFilter]
Parent=root
Rate=<rate_kbit>K
BurstBytes=<burst_kib>K
LatencySec=0.05
```

- the environment file `/etc/link-rate.d/<iface_id>.env` containing exactly
  these lines in this order:

```
IFACE=<iface_id>
LINK_UID=<uid>
TIER=<tier>
PEAK=<peak>
TOTAL_UNITS=<total_units>
RATE_KBIT=<rate_kbit>
BURST_KIB=<burst_kib>
```

Detached interfaces get no account, no directory, no drop-in, and no
environment file. Their ledger rows still participate fully in the seal
chain of section 9.

Provisioning must be idempotent. A second run leaves every account, mode,
owner, and file byte for byte as the first run left it, and reproduces the
same manifest and seal.

## 8. Manifest

The manifest is written to /app/out/link-manifest.json as a single JSON
document:

```
{
  "interfaces": [
    {
      "iface_id": "...",
      "uid": 0,
      "tier": "...",
      "peak": 0,
      "total_units": 0,
      "rate_kbit": 0,
      "burst_kib": 0
    }
  ],
  "detached": ["..."],
  "row_count": 0,
  "seal": "16 lowercase hex digits"
}
```

`interfaces` holds one entry per active interface sorted by `iface_id`
ascending, which is not the provisioning order. `detached` holds the
detached interface ids sorted ascending. `row_count` is the total number of
ledger rows across every interface in the registry index, active and
detached.

## 9. The manifest seal

The seal is a 64-bit FNV-1a accumulator (offset basis 0xcbf29ce484222325,
prime 0x100000001b3, all arithmetic mod 2^64) folded over every ledger row of
every interface in registry order, that is the link:index order including
detached interfaces, days ascending within each interface. Start the
accumulator at the offset basis and keep a running 64-bit subtotal that
starts at zero and also wraps mod 2^64. For each ledger row, in that order:

- add to the subtotal the row's smoothed volume plus its transfer weight,
- then fold these bytes into the accumulator in this exact order: the
  interface's position in the registry index as a u16 (2 bytes), the day
  number as a u16 (2 bytes), the smoothed volume as a u64 (8 bytes), the
  running subtotal as a u64 (8 bytes), and the current accumulator value
  itself as a u64 (8 bytes). Every multi-byte value is little-endian.
  Folding a byte means xor it into the low 8 bits of the accumulator, then
  multiply by the prime.

Folding the accumulator into its own stream makes the seal a cascade: one
wrong or mis-ordered row changes every later step. Render the final
accumulator as 16 lowercase hex digits. That string is the manifest `seal`
field and, followed by a trailing newline, the entire content of
/app/out/seal.hex.
