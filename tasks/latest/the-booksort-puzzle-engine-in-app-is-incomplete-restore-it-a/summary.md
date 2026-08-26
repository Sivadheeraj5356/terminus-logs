# The BookSort puzzle engine in `/app` is incomplete. Restore it as a deterministi

- **UUID:** `d6b7eecf-e0af-4613-8f12-6bace1649909`
- **Slug:** `the-booksort-puzzle-engine-in-app-is-incomplete-restore-it-a`
- **Category:** games
- **Difficulty:** hard

## Summary

The BookSort puzzle engine in `/app` is incomplete. Restore it as a deterministic Go terminal game and build the finished executable at `/app/bin/booksort`.

The game loads level definitions from SQLite, persists a live board, enforces legal top-book moves, and must remain reproducible across repeated runs. Players must be able to create a level, inspect the shelves, move books, undo and redo play, evaluate the win state, inspect history, request a deterministic hint, and obtain a shortest bounded solution.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
