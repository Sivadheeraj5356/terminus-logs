The recovery clone still boots into emergency mode: an enabled target never gathers its real dependency set, a masked mount is reported active, and the service that owns the data path is missing from the final membership list. Repair the captured-host reconciler so every published yard artifact matches the operating contracts on the public command the verifier invokes.

Editable maintenance sources live under `/opt/boot_transaction_switchboard/rust_unitgraph_cells/` (installed for execution under `/app/rust_unitgraph_cells/`). The eight contracts in `/app/systemd_boot_contracts/` (mirrored under `/opt/boot_transaction_switchboard/systemd_boot_contracts/`) are normative. Decision tables and fallbacks wired through those cells must produce contract outcomes; rebuilding with the forge below is how the public launcher picks up your repair.

Required end-state behaviors (see the matching contract clauses for detail):

- Fragment search uses administrator, then transient, then vendor. Exact instance fragments win; otherwise load the template and keep the requested instance identity. Masks suppress the unit; aliases resolve without loops.
- Drop-ins merge by family, tier, and basename. Empty list assignments clear that list; empty scalar assignments do not erase the prior scalar.
- Specifiers expand only in the contracted directive set. `%i` is the escaped instance and `%I` the unescaped instance; unit-name escape round-trips path bytes including root as `-.mount`.
- `WantedBy=` creates relative `*.wants/` links; `RequiredBy=` creates relative `*.requires/` links. Absolute enablement targets are rejected. Disable removes only attributable links through `Also=` cycles. Presets are first-match; `ignore` is not disable. `SET_DEFAULT` writes a relative `default.target` symlink. Mask installs `/dev/null` at the administrator tier only.
- `Wants`, `Requires`, `Requisite`, `BindsTo`, and `PartOf` stay distinct edge kinds in `transaction.jobs`. `Before`/`After` order jobs already present and must not pull new start jobs. `DefaultDependencies=no` must not emit default synthetic edges. False conditions skip; false assertions fail; dependents observe both.
- Mounts, automount access triggers, and device-alias readiness follow the captured device table. Acceptance requires complete target membership and reasons. Injected write or replay faults must restore the exact prestate. Cold reopen, receipt idempotence, and relocated yard/order clones must keep identical configured bytes and the same receipt.

Public entrypoint: `/app/boot_recovery_console/reconcile_boot_graph.sh` with exactly two absolute operands — an existing `.bootyard` and a distinct sealed `.bootorder`. Success prints one lowercase 64-hex SHA-256 receipt on stdout and publishes eight records under `<yard>/var/lib/unitgraph/` in these exact tab-separated line formats:

- `effective.units` — one sorted line per unit: `<name>\t<fragment_logical_path>\t<origin>\t<loaded|masked>\t<dropin_count>\t<directive_digest>`. `origin` is `fragment`, `template`, or `mask`; a template-loaded instance keeps its instantiated name in column 1 with the `worker@.service`-style template path in column 2. Administrator fragments publish their `etc/systemd/system/...` logical path.
- `enablement.state` — sorted `<unit>\t<class>` lines using the INSTALL-2 classes (`enabled`, `disabled`, `static`, `indirect`, `alias`, `masked`, `generated`), followed by evidence lines.
- `transaction.jobs` — sorted lines of two shapes: job lines `<unit>\t<start|stop>\t<comma-joined origins>` and edge lines `edge\t<from>\t<to>\t<kind>\t<provenance>`. Edge kinds are the lowercase directive names (`wants`, `requires`, `requisite`, `bindsto`, `partof`, `conflicts`, `before`, `after`); provenance is `explicit:<Directive>` for unit-file edges and `default:<rule>` (for example `default:service-basic`) for synthesized ones.
- `boot.trace` — ordered `step\t<index>\t<action>\t<unit>\t<reason>\t<fragment_digest>` event lines, then sorted `state\t<unit>\t<state>\t<reason>` lines. Reasons are exact strings: skipped false conditions record `condition-failed`, failed false assertions record `assert-failed`, conflict stops record `conflict-stop`, and started units record `started`.
- `change.account` — sorted `<intent_seq>\t<logical_path>\t<kind>\t<before>\t<after>` lines, one per created, removed, or replaced item, using yard-relative logical paths only (never temporary or staging paths).
- `accepted.order` — `order_id=`, `order_seal=`, `pre_generation=`, `post_generation=` key=value lines.
- `generation` — the committed generation integer and a trailing newline.
- `reconcile.receipt` — the same receipt printed on stdout, with a trailing newline; reopening the yard must reproduce it byte-for-byte.

Rejection restores every preexisting yard byte, link target, mode, and absence. The environment variables `UNITGRAPH_INJECT_WRITE_FAULT=1` and `UNITGRAPH_INJECT_REPLAY_FAULT=1` inject a publish-time write fault and a cold-replay fault respectively; under either, the run must exit nonzero and leave the yard byte-identical to its prestate.

After correcting the cells, rebuild and reinstall:

`bash /opt/boot_transaction_switchboard/forge_boot_reconciler.sh /opt/boot_transaction_switchboard`

Keep vendor units, captured host facts, devices, and the sealed order as read-only custody; only the administrator unit tier and `var/lib/unitgraph/` may change on success.
