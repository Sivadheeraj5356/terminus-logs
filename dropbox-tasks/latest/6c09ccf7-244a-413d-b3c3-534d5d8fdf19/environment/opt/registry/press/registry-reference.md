# Aldreth county deeds registry, host reference

This reference names the accounts and places of the registry as they stand on
this host. It decides nothing the standing orders and the county minute decide;
where it and they disagree, they govern.

## Accounts

- `registrar`, the registry's own working account, under which the registry is
  kept and the seal is read to enrol a title. It keeps the company group
  `clerks`.
- `tolman` and `bazeley`, the serving clerks, each in the `clerks` group.
- `pentreath`, the deputy registrar whose engagement the county has ended.

## Places

- `/opt/registry/press`, the press in which these orders, the county minute, and
  the registry's notes are posted.
- `/srv/registry/charges`, the register of charges in force, an enrolment to a
  charge.
- `/srv/registry/deeds`, the muniment room, holding the county's enrolled deeds.
- `/srv/registry/register`, the register of titles.
- `/etc/registry/seal.key`, the registrar's seal.
- `/srv/registry`, the registry ground, holding the charges, the deeds, the
  register, and the registry's work.

## The seal and the mark

The registry's mark is set by reading the seal at `/etc/registry/seal.key`. The
keys of the registry's accounts are read by the ordinary tooling of the
distribution; nothing in this reference sets the keeping of any file, which the
standing orders provide.
