# Modverse version strings

Every module in the modverse ecosystem is identified by a name plus a version
string. A version string has a numeric core of exactly three dot separated
fields written as `MAJOR.MINOR.PATCH`, each a non negative integer with no
leading zeros except the single digit `0`. The leading `v` that appears in a
require line is part of the on disk spelling, not part of the version, so `v1.4.0`
and `1.4.0` denote the same version.

Three optional shapes attach to that core.

A prerelease suffix begins with a single `-` and is a sequence of dot separated
identifiers, for example `1.4.0-rc.2` or `2.0.0-alpha`. A version that carries a
prerelease suffix ranks below the same numeric core with no suffix, so
`1.4.0-rc.2` is lower than `1.4.0`. Two prerelease versions that share a numeric
core are ordered by comparing their identifiers left to right. A purely numeric
identifier ranks below an identifier that contains a non digit. Two numeric
identifiers compare as integers. Two non numeric identifiers compare as ASCII
strings. A prerelease with fewer identifiers ranks below an otherwise equal
prerelease with more, so `1.4.0-rc` is lower than `1.4.0-rc.0`.

A pseudo version describes an untagged snapshot. It is written as a base numeric
core, then a prerelease shaped suffix whose final two dot separated identifiers
are a 14 digit timestamp and a 12 character lowercase hex short hash, for example
`0.0.0-20240118091500-9fceb02d0ae5` or `1.5.1-0.20240220140000-c1d2e3f4a5b6`.
A pseudo version ranks below every tagged release that shares its base numeric
core, and it ranks at the very bottom among everything that shares that base
core. Two pseudo versions with the same base core are ordered by their 14 digit
timestamp compared as an integer, and the short hash breaks an exact timestamp
tie by ASCII string order.

An incompatible release carries the literal build identifier `+incompatible`
attached after the numeric core, for example `2.0.0+incompatible`. This marks a
release that opted out of the usual import compatibility promise for its major
number. An incompatible version ranks above the identical numeric core without
the suffix, so `2.0.0+incompatible` is higher than `2.0.0`. The `+incompatible`
suffix never appears together with a prerelease suffix. No other build metadata
shape exists in modverse, so any `+` text other than `+incompatible` is invalid.

Ordering is a total order over all valid version strings. Comparing two versions
first compares the numeric core field by field as integers. If the cores are
equal, a tagged release with no suffix sits in the middle, an incompatible
release sits above it, and prerelease and pseudo versions sit below it with
pseudo versions at the bottom as described above. Versions that are byte equal
after dropping a leading `v` are equal.
