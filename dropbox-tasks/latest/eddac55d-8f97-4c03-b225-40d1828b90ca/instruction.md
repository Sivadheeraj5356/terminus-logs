Aurelia's regulator publishes civil-time ordinances, and since the 1991 amendments
landed our zone files have disagreed with them for at least three jurisdictions.
Bookings in the affected zones sit an hour off across half of every year. The
ordinances are the source of truth now. They live under /app/data/ordinances, one
directory per jurisdiction, with each jurisdiction's meridian recorded alongside them.

The tzforge crate under /app already walks that corpus. Its build subcommand writes
zone files into /app/out/zoneinfo, records a manifest at /app/out/manifest.json, loads
a transition index into Postgres, and its serve subcommand answers lookups on port
8080. All of it was written against the legacy offset table we are retiring, not
against the ordinance rules, and the emitter predates the layout we agreed with our
consumers. The documents in /app/docs define the corpus grammar, the rules that govern
which ordinance applies when, the exact bytes a zone file must contain, and the index
and service we owe downstream.

Those teams read the zone files with glibc and with Python, so a file only our own
reader accepts is a failure. The manifest, the index and the service must all describe
one timeline, and rebuilding on an unchanged corpus has to reproduce the same bytes,
because we cache by content hash.

Postgres is local; the connection string is in /app/config/tzforge.toml, and
/app/bin/pgstart.sh brings the cluster up. Leave /app/migrations and the ordinance
corpus alone. Some ordinances look like data-entry errors and are not.
