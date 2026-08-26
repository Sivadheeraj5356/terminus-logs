Each structure in this dataset is a small square integer scalar field sampled on a
triangulated grid, the kind of coarse height map or density slice that arises in
shape analysis. Its shape is summarized by a topological signature read from the
persistence of the field: as a threshold sweeps through the values, connected
components and loops are born and later die, and the spans from birth to death
encode the structure's fold.

This is a fold-recognition problem. Each reference structure carries a known fold
group; the queries do not. For each query, compute its integer topological
persistence signature, compare that signature to the signature of every reference
under an L1 distance, and assign the query the fold group of the nearest reference.

The data are related CSV tables under /app/data. The triangulation, the filtration,
the persistence-bar families and their signs, the significance floor that decides
which bars are counted, the seventeen integers that make up the signature, the
retrieval rule, how the tables are read, and the output format are all specified
exactly in /app/docs/contract.md, which is binding. One of the tables is a
non-authoritative summary and must not be trusted for roles or sizes.

The graded program is the executable /app/analyze; a Rust scaffold and a Makefile
that produces it are provided under /app, and any language available in the image
may be used instead. It reads the data directory as its first argument, defaulting
to /app/data, and prints one result line per query; every reported quantity is an
integer.
