# SOP-9 — Station Systems Governance (Meridian Ridge Geomagnetic Observatory)

Revision 4, adopted 2025-01-21. Applies station-wide.

## §1 Scope

This procedure governs how the observatory adopts, rescinds, and records
decisions about analysis methods, software dependencies, and security
advisories. It defines which records are authoritative when accounts disagree,
and it establishes the Station Systems Freeze.

## §2 Records of the station

Four record series exist. Dependency Review Board minutes (`DRB-` prefix)
record dependency and method adoptions. Engineering journals (`J-` prefix)
record day-to-day work in narrative form. Station memoranda (`M-` prefix)
record policy directives and proposals. Meridian Ridge advisories (`MRA-`
prefix) record security findings against software in service. Incident
reports (`INC-` prefix) record operational failures. Advisories of other
stations — for example the Fenn Hollow archive station's `FHA-` series —
are not station advisories, do not enter the station's advisory lifecycle,
and are cited in station records for context only.

## §3 Precedence

Where a journal entry and a board minute give differing accounts of the same
decision, the minute governs. A journal narrative, however carefully written,
records what its author understood; a minute records what the board resolved.
The one exception: where a minute has been lost or purged from the archive, a
journal entry that reproduces the minute's resolution verbatim is treated as
the authoritative record of that resolution.

Draft memoranda propose; they do not decide. A disposition stated in a draft
has no effect unless a minute or an adopted memorandum confirms it.

## §4 Rescission and fallback

When an erratum rescinds a methods revision, the station falls back to the
most recent earlier revision that has not itself been rescinded, and that
fallback remains in force until the board adopts a successor revision.
Rescission of a dependency approval removes that version from the approved
set immediately; it does not by itself approve any replacement.

## §5 Advisory lifecycle

An advisory is *in force* from its issue date until it is withdrawn,
superseded, or closed. An advisory awaiting intake review is recorded as
*pending* and is not in force until intake completes. Registration in
`registry.advisory_register` is an administrative step; an advisory's force
derives from its issuance, not from its registration, and registration
backlogs have occurred.

## §6 Station Systems Freeze and audit dossiers

The board set the Station Systems Freeze at 2025-11-30. The freeze fixes the
decision record against which any subsequent remediation of station software
is judged. Any remediation of the spectral service must be accompanied by a
provenance dossier on Form PD-4, prepared to the schema published at
`/app/archive/dossier_schema.md`, reconstructing the in-force decisions as of
the freeze date. Dossier preparers are reminded that the archive is the
instrument of record: no summary table of the values requested by Form PD-4
is maintained anywhere in the station, deliberately, so that each dossier is
an independent reconstruction.
