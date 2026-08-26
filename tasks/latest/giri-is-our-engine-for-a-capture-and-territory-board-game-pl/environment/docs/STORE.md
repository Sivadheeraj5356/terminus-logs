# giri results store, graph, and command interface

## How the store is reached

The crate is dependency-free and the image has no network, so nothing can be
pulled from crates.io and there is no SQLite binding linked in. `giri` drives the
store by invoking the `sqlite3` command-line binary installed in the image: it
feeds it the schema and the inserts, and reads back what `graph` and `report`
need. `store::write_rows` creates the tables if they are absent and replaces any
previous contents; `store::query` runs one `SELECT` and returns a `Vec<String>`
per result row holding that row's columns in the order the `SELECT` listed them,
so pick a field separator that cannot occur in the stored values. The SVG
rendering goes the same way, through the installed Graphviz `dot` binary.

## Command interface

- `giri replay --board <spec> --games <dir> --db <path>`
  Replays every `*.log` file directly inside `<dir>` (subdirectories are not
  descended into) and writes the results into the SQLite database at `<path>`,
  replacing any previous contents. The game id is the file name without its `.log`
  suffix. A malformed log (see NOTATION.md) is a hard error and the command exits
  nonzero.

- `giri graph --board <spec> --game <id> --db <path> --dot <path> --svg <path>`
  Reads the stored final position for `<id>`, writes its group-and-region graph as
  Graphviz to the `--dot` path, and renders it to SVG at the `--svg` path with
  `dot`.

- `giri report --game <id> --db <path>`
  Prints a single-line JSON object of the stored row for `<id>`.

## SQLite schema

    CREATE TABLE games (
      game_id        TEXT PRIMARY KEY,
      first_illegal  INTEGER NOT NULL,   -- zero-based index, or -1 if none
      reason         TEXT NOT NULL,      -- 'occupied' | 'suicide' | 'superko' | ''
      black_score    INTEGER NOT NULL,
      white_score    INTEGER NOT NULL,
      black_captures INTEGER NOT NULL,   -- opponent stones black removed over the game
      white_captures INTEGER NOT NULL,
      moves_played   INTEGER NOT NULL,   -- number of recorded moves consumed
      final_board    TEXT NOT NULL       -- canonical board string, see below
    );

    CREATE TABLE superko_sites (
      game_id        TEXT NOT NULL,
      move_index     INTEGER NOT NULL
    );

`reason` is `''` and `first_illegal` is `-1` when a game has no illegal move.
`superko_sites` holds one row for each game whose first illegal move was rejected by
the repetition rule, with `move_index` equal to that game's `first_illegal`.

`report`'s JSON object carries the `games` columns under their own names.

## Canonical board string

`final_board` lists every intersection in ascending node-name order, joined by `;`,
each written as `<name>:<c>` where `<c>` is `B`, `W`, or `.` for black, white, or
empty. The same string is the whole-board key used by the repetition rule.

## Group/region graph

The graph of a position has one node per connected component of the board: each
stone group and each empty region. A DOT node is emitted as

    c<k> [kind="<kind>" color="<color>" size="<n>" members="<names>"];

where `<kind>` is `group` for a stone group or `region` for an empty region,
`<color>` is `black`, `white`, or `empty`, `<n>` is the number of intersections in
the component, and `<names>` is those intersection names in ascending order,
space-separated. Two components are joined by an edge `c<i> -- c<j>` when some
intersection of one is adjacent to some intersection of the other. The document is
wrapped as `graph giri { ... }`.
