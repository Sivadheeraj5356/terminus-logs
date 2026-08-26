# The retiring offset table

Until the 2024 migration, zone data came from `civil_offsets.csv`, an internal table
maintained by hand since the 1980s. It is worth knowing what that table was, because
`tzforge` was written against it and still reads the way it was written.

The table held one row per offset change: a date, an offset, an abbreviation, and a
free-text note nobody parsed. There was no record of when a change had been enacted,
no way to express that one instrument had superseded or undone another, and no concept
of a recurring seasonal rule beyond a pair of dates restated every year. Rows were
transcribed from published local times after each change had already taken effect,
which is the only reason the table was ever self-consistent.

Coverage began in 1970. Earlier history was held to be the almanac's problem, not the
table's, and the importer was never asked to produce it.

Its consumers were three internal services, all of which read the version 1 zone file
format and none of which looked past the transitions the table itself supplied. They
were retired last year along with the table.

The Bureau's ordinances carry everything the table could not: enactment dates,
repeals, anchors, and rules that recur on their own terms. What `tzforge` must do with
them is set out in the other documents in this directory.
