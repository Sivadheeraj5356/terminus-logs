# Enablement, Mask, and Preset Law

Clause namespace: `INSTALL-*`

## INSTALL-1 Enablement links

`WantedBy=` creates `etc/systemd/system/<target>.wants/<unit>` relative symlinks. `RequiredBy=` creates `etc/systemd/system/<target>.requires/<unit>` relative symlinks. Link text is the relative path to the unit fragment or the unit name as documented for same-directory aliases; absolute link targets are rejected.

`Alias=` creates administrator-tier alias symlinks. `Also=` recursively processes declared sibling units under cycle checks. Disable removes only links attributable to the named unit; never delete an unrelated administrator link merely because it points at the same fragment.

## INSTALL-2 Enablement classes

Effective classes recorded in `enablement.state`: `enabled`, `disabled`, `static`, `indirect`, `alias`, `masked`, `generated`. Static units lack `[Install]` and are not enabled by wants links alone. Indirect units are pulled only through `Also=`.

## INSTALL-3 Presets

`PRESET` applies first-match policy from `preset.selection` for the exact unit or instantiated template. Actions: `enable`, `disable`, `ignore`. Unmatched units retain current state. `ignore` is not disable. A template preset without an instance obeys the contracted instance list or `DefaultInstance` and cannot invent an instance.

## INSTALL-4 Mask and unmask

`MASK` installs `etc/systemd/system/<unit>` → `/dev/null` after removing only conflicting administrator-layer unit material authorized by the order. `UNMASK` removes that exact administrator mask and does not resurrect deleted content. Runtime and vendor masks remain effective and cannot be overridden by administrator enablement alone.

## INSTALL-5 Default target

`SET_DEFAULT` manages only `etc/systemd/system/default.target` as a relative symlink to a loadable target unit. After all intent actions, that link must agree with `order.record` `final_target`.

## INSTALL-6 Prestate guards

Each intent line declares a prestate classification. If the cold yard disagrees, reject the order without mutation. Generation checks follow `YARD-6`.

## INSTALL-7 Change account

Every created, removed, or replaced file or link appears once in `change.account` with before/after kind, canonical target or digest, triggering intent sequence, and authorization. No-op reasoning is recorded when an operation intentionally changes nothing.

## INSTALL-8 Omissions

This law omits `systemctl link`, global user presets, and vendor preset file discovery outside `preset.selection`.
