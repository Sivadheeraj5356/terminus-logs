"""Behavioral tests for the SQLite-backed Go book-sorting puzzle."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

APP = Path('/app')
BIN = APP / 'bin' / 'booksort'


def run_cmd(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run the book sorting CLI and return the completed process."""
    result = subprocess.run(
        [str(BIN), *args],
        cwd=APP,
        text=True,
        capture_output=True,
        timeout=10,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed: {args}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def board_digest(db: Path) -> str:
    """Compute the documented canonical digest for the current SQLite board."""
    conn = sqlite3.connect(db)
    shelves = conn.execute(
        "SELECT shelf_id, position, capacity, required_genre, sort_mode FROM shelves ORDER BY position, shelf_id"
    ).fetchall()
    shelf_pos = {row[0]: (row[1], row[0]) for row in shelves}
    books = conn.execute(
        "SELECT book_id, title, genre, sort_key, shelf_id, slot FROM books"
    ).fetchall()
    edges = conn.execute(
        "SELECT e.from_shelf, e.to_shelf FROM edges e JOIN shelves sf ON sf.shelf_id=e.from_shelf "
        "JOIN shelves st ON st.shelf_id=e.to_shelf ORDER BY sf.position, e.from_shelf, st.position, e.to_shelf"
    ).fetchall()
    conn.close()
    parts = ['SHELVES']
    parts.extend('|'.join(map(str, row)) for row in shelves)
    parts.append('BOOKS')
    books.sort(key=lambda row: (shelf_pos[row[4]], row[5], row[0]))
    parts.extend('|'.join(map(str, row)) for row in books)
    parts.append('EDGES')
    parts.extend('|'.join(map(str, row)) for row in edges)
    return hashlib.sha256(('\n'.join(parts) + '\n').encode()).hexdigest()


def create_seed_db(
    path: Path,
    level_id: str,
    shelves: list[tuple],
    books: list[tuple],
    edges: list[tuple],
) -> None:
    """Create a seed database using the documented level schema."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE seed_levels(level_id TEXT PRIMARY KEY);
        CREATE TABLE seed_shelves(
            level_id TEXT,
            shelf_id TEXT,
            position INTEGER,
            capacity INTEGER,
            required_genre TEXT,
            sort_mode TEXT
        );
        CREATE TABLE seed_books(
            level_id TEXT,
            book_id TEXT,
            title TEXT,
            genre TEXT,
            sort_key INTEGER,
            shelf_id TEXT,
            slot INTEGER
        );
        CREATE TABLE seed_edges(level_id TEXT, from_shelf TEXT, to_shelf TEXT);
        """
    )
    conn.execute("INSERT INTO seed_levels(level_id) VALUES (?)", (level_id,))
    conn.executemany(
        "INSERT INTO seed_shelves VALUES (?, ?, ?, ?, ?, ?)",
        [(level_id, *row) for row in shelves],
    )
    conn.executemany(
        "INSERT INTO seed_books VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(level_id, *row) for row in books],
    )
    conn.executemany(
        "INSERT INTO seed_edges VALUES (?, ?, ?)",
        [(level_id, *row) for row in edges],
    )
    conn.commit()
    conn.close()


class TestBookSortCli:
    def test_new_and_show_render_seeded_level_in_database_order(self, tmp_path: Path) -> None:
        """A seeded level should load and render shelves by position and book slot."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'render-case',
            shelves=[
                ('alpha', 1, 3, 'ANY', 'ASC'),
                ('beta', 2, 2, 'FIC', 'DESC'),
                ('empty', 3, 1, 'MYS', 'NONE'),
            ],
            books=[
                ('a-10', 'Atlas', 'FIC', 10, 'alpha', 0),
                ('a-20', 'Beacon', 'MYS', 20, 'alpha', 1),
                ('b-90', 'Cipher', 'FIC', 90, 'beta', 0),
            ],
            edges=[('alpha', 'beta'), ('beta', 'empty')],
        )

        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'render-case')
        shown = run_cmd('show', '--db', str(db)).stdout.splitlines()

        assert shown == [
            'Shelf alpha [genre=ANY sort=ASC cap=3]: a-10(FIC:10) | a-20(MYS:20)',
            'Shelf beta [genre=FIC sort=DESC cap=2]: b-90(FIC:90)',
            'Shelf empty [genre=MYS sort=NONE cap=1]:',
        ]

    def test_new_replaces_existing_runtime_database(self, tmp_path: Path) -> None:
        """Running new twice should discard old state and reload the seed level."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'replace-case',
            shelves=[('source', 1, 2, 'ANY', 'NONE'), ('target', 2, 2, 'FIC', 'ASC')],
            books=[('fic-top', 'Top', 'FIC', 44, 'source', 0)],
            edges=[('source', 'target')],
        )

        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'replace-case')
        original = run_cmd('show', '--db', str(db)).stdout
        run_cmd('move', '--db', str(db), '--from', 'source', '--to', 'target')
        assert run_cmd('show', '--db', str(db)).stdout != original

        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'replace-case')
        assert run_cmd('show', '--db', str(db)).stdout == original
        conn = sqlite3.connect(db)
        history_count = conn.execute('SELECT COUNT(*) FROM move_history').fetchone()[0]
        conn.close()
        assert history_count == 0

    def test_invalid_route_is_rejected_without_mutation(
        self, tmp_path: Path
    ) -> None:
        """A missing edge should fail without changing positions or history."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'route-case',
            shelves=[('source', 1, 2, 'ANY', 'NONE'), ('target', 2, 2, 'FIC', 'ASC')],
            books=[('top-fic', 'Top Fic', 'FIC', 40, 'source', 1)],
            edges=[],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'route-case')

        before = run_cmd('show', '--db', str(db)).stdout
        result = run_cmd(
            'move', '--db', str(db), '--from', 'source', '--to', 'target', check=False
        )
        after = run_cmd('show', '--db', str(db)).stdout

        assert result.returncode != 0
        assert result.stderr.startswith('ERROR:')
        assert after == before
        conn = sqlite3.connect(db)
        history_count = conn.execute('SELECT COUNT(*) FROM move_history').fetchone()[0]
        conn.close()
        assert history_count == 0

    def test_genre_capacity_and_sort_constraints_are_database_backed(self, tmp_path: Path) -> None:
        """Move validation rejects genre, capacity, and ordering violations."""
        seed = tmp_path / 'levels.db'
        create_seed_db(
            seed,
            'constraint-case',
            shelves=[
                ('mixed', 1, 3, 'ANY', 'NONE'),
                ('fiction', 2, 2, 'FIC', 'ASC'),
                ('mystery', 3, 1, 'MYS', 'ASC'),
                ('full', 4, 1, 'ANY', 'NONE'),
            ],
            books=[
                ('fic-low', 'Low', 'FIC', 10, 'mixed', 0),
                ('mys-top', 'Wrong Genre', 'MYS', 50, 'mixed', 1),
                ('fic-high', 'High', 'FIC', 30, 'fiction', 0),
                ('already-full', 'Full', 'FIC', 5, 'full', 0),
            ],
            edges=[('mixed', 'fiction'), ('mixed', 'mystery'), ('mixed', 'full')],
        )
        db = tmp_path / 'game.db'
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'constraint-case')

        genre = run_cmd('move', '--db', str(db), '--from', 'mixed', '--to', 'fiction', check=False)
        assert genre.returncode != 0
        assert genre.stderr.startswith('ERROR:')

        ok = run_cmd('move', '--db', str(db), '--from', 'mixed', '--to', 'mystery')
        assert ok.stdout.strip() == 'OK moved mys-top from mixed to mystery'

        full = run_cmd('move', '--db', str(db), '--from', 'mixed', '--to', 'full', check=False)
        assert full.returncode != 0
        assert full.stderr.startswith('ERROR:')

        sort = run_cmd('move', '--db', str(db), '--from', 'mixed', '--to', 'fiction', check=False)
        assert sort.returncode != 0
        assert sort.stderr.startswith('ERROR:')

        conn = sqlite3.connect(db)
        rows = conn.execute(
            'SELECT book_id, shelf_id, slot FROM books ORDER BY book_id'
        ).fetchall()
        history_count = conn.execute('SELECT COUNT(*) FROM move_history').fetchone()[0]
        conn.close()
        assert ('mys-top', 'mystery', 0) in rows
        assert ('fic-low', 'mixed', 0) in rows
        assert history_count == 1

    def test_capacity_applies_to_any_buffer_shelves(self, tmp_path: Path) -> None:
        """ANY shelves still enforce capacity for move and hint validation."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'any-capacity-case',
            shelves=[
                ('source', 1, 1, 'ANY', 'NONE'),
                ('buffer', 2, 1, 'ANY', 'NONE'),
            ],
            books=[
                ('move-me', 'Move Me', 'FIC', 10, 'source', 0),
                ('fills-buffer', 'Full', 'MYS', 20, 'buffer', 0),
            ],
            edges=[('source', 'buffer')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'any-capacity-case')
        before = run_cmd('show', '--db', str(db)).stdout

        rejected = run_cmd('move', '--db', str(db), '--from', 'source', '--to', 'buffer', check=False)

        assert rejected.returncode != 0
        assert rejected.stderr.startswith('ERROR:')
        assert run_cmd('hint', '--db', str(db)).stdout.strip() == 'NO_MOVE'
        assert run_cmd('show', '--db', str(db)).stdout == before

    def test_move_to_same_shelf_is_rejected_without_history(self, tmp_path: Path) -> None:
        """Moving a top book to its own shelf should fail without mutating state."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'same-shelf-case',
            shelves=[('stack', 1, 2, 'ANY', 'NONE')],
            books=[('book-1', 'Loop', 'FIC', 11, 'stack', 0)],
            edges=[('stack', 'stack')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'same-shelf-case')
        before = run_cmd('show', '--db', str(db)).stdout

        result = run_cmd('move', '--db', str(db), '--from', 'stack', '--to', 'stack', check=False)

        assert result.returncode != 0
        assert result.stderr.startswith('ERROR:')
        assert run_cmd('show', '--db', str(db)).stdout == before
        conn = sqlite3.connect(db)
        history_count = conn.execute('SELECT COUNT(*) FROM move_history').fetchone()[0]
        conn.close()
        assert history_count == 0

    def test_move_persists_and_undo_restores_previous_state(
        self, tmp_path: Path
    ) -> None:
        """Moves persist in SQLite and undo reverses the latest move."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'undo-case',
            shelves=[('stack', 1, 2, 'ANY', 'NONE'), ('fiction', 2, 2, 'FIC', 'ASC')],
            books=[
                ('fic-high-slot', 'High Slot', 'FIC', 10, 'stack', 5),
                ('fic-low-slot', 'Low Slot', 'FIC', 20, 'stack', 2),
            ],
            edges=[('stack', 'fiction')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'undo-case')
        before = run_cmd('show', '--db', str(db)).stdout

        run_cmd('move', '--db', str(db), '--from', 'stack', '--to', 'fiction')
        moved = run_cmd('show', '--db', str(db)).stdout
        assert 'Shelf fiction [genre=FIC sort=ASC cap=2]: fic-high-slot(FIC:10)' in moved
        assert 'fic-low-slot(FIC:20)' in moved

        run_cmd('undo', '--db', str(db))
        restored = run_cmd('show', '--db', str(db)).stdout
        assert restored == before
        conn = sqlite3.connect(db)
        undone_count = conn.execute(
            'SELECT COUNT(*) FROM move_history WHERE undone = 1'
        ).fetchone()[0]
        conn.close()
        assert undone_count == 1

    def test_history_json_preserves_active_and_undone_rows(self, tmp_path: Path) -> None:
        """History should expose JSON rows and keep undone moves instead of deleting them."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'history-case',
            shelves=[
                ('a', 1, 3, 'ANY', 'NONE'),
                ('b', 2, 3, 'ANY', 'NONE'),
                ('c', 3, 3, 'ANY', 'NONE'),
            ],
            books=[('book-1', 'One', 'FIC', 1, 'a', 0), ('book-2', 'Two', 'MYS', 2, 'a', 1)],
            edges=[('a', 'b'), ('a', 'c')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'history-case')
        assert json.loads(run_cmd('history', '--db', str(db)).stdout) == []

        run_cmd('move', '--db', str(db), '--from', 'a', '--to', 'b')
        run_cmd('move', '--db', str(db), '--from', 'a', '--to', 'c')
        run_cmd('undo', '--db', str(db))
        rows = json.loads(run_cmd('history', '--db', str(db)).stdout)

        comparable = [
            {key: row[key] for key in ('id', 'book_id', 'from_shelf', 'to_shelf', 'from_slot', 'to_slot', 'undone')}
            for row in rows
        ]
        assert comparable == [
            {
                'id': 1,
                'book_id': 'book-2',
                'from_shelf': 'a',
                'to_shelf': 'b',
                'from_slot': 1,
                'to_slot': 0,
                'undone': 0,
            },
            {
                'id': 2,
                'book_id': 'book-1',
                'from_shelf': 'a',
                'to_shelf': 'c',
                'from_slot': 0,
                'to_slot': 0,
                'undone': 1,
            },
        ]
        for row in rows:
            assert set(row) == {
                'id', 'book_id', 'from_shelf', 'to_shelf', 'from_slot', 'to_slot',
                'before_digest', 'after_digest', 'undone'
            }
            assert len(row['before_digest']) == 64
            assert len(row['after_digest']) == 64
            int(row['before_digest'], 16)
            int(row['after_digest'], 16)

    def test_history_digests_match_canonical_board_snapshots_and_guard_stale_undo(self, tmp_path: Path) -> None:
        """Move history digests should match board snapshots and stale undo must not mutate state."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'digest-case',
            shelves=[('left', 1, 3, 'ANY', 'NONE'), ('right', 2, 2, 'FIC', 'ASC')],
            books=[('fic-1', 'One', 'FIC', 10, 'left', 0), ('fic-2', 'Two', 'FIC', 20, 'left', 1)],
            edges=[('left', 'right')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'digest-case')
        before_digest = board_digest(db)
        run_cmd('move', '--db', str(db), '--from', 'left', '--to', 'right')
        after_digest = board_digest(db)

        rows = json.loads(run_cmd('history', '--db', str(db)).stdout)
        assert rows[0]['before_digest'] == before_digest
        assert rows[0]['after_digest'] == after_digest

        conn = sqlite3.connect(db)
        conn.execute("UPDATE books SET shelf_id='left', slot=9 WHERE book_id='fic-2'")
        conn.commit()
        conn.close()
        tampered = run_cmd('show', '--db', str(db)).stdout

        result = run_cmd('undo', '--db', str(db), check=False)
        assert result.returncode != 0
        assert result.stderr.startswith('ERROR:')
        assert run_cmd('show', '--db', str(db)).stdout == tampered
        assert json.loads(run_cmd('history', '--db', str(db)).stdout)[0]['undone'] == 0


    def test_undo_with_no_successful_history_fails_cleanly(self, tmp_path: Path) -> None:
        """Undo on a fresh level should fail without changing the database."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'empty-undo-case',
            shelves=[('solo', 1, 2, 'ANY', 'NONE')],
            books=[('book-1', 'Solo', 'FIC', 7, 'solo', 0)],
            edges=[],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'empty-undo-case')
        before = run_cmd('show', '--db', str(db)).stdout

        result = run_cmd('undo', '--db', str(db), check=False)

        assert result.returncode != 0
        assert result.stderr.startswith('ERROR:')
        assert run_cmd('show', '--db', str(db)).stdout == before

    def test_status_detects_win_after_rules_are_satisfied(self, tmp_path: Path) -> None:
        """Status switches to WIN after the last misplaced book moves legally."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'win-case',
            shelves=[
                ('fiction', 1, 3, 'FIC', 'ASC'),
                ('mystery', 2, 2, 'MYS', 'ASC'),
            ],
            books=[
                ('fic-10', 'Fic Ten', 'FIC', 10, 'fiction', 0),
                ('mys-20', 'Mystery Twenty', 'MYS', 20, 'fiction', 1),
                ('mys-05', 'Mystery Five', 'MYS', 5, 'mystery', 0),
            ],
            edges=[('fiction', 'mystery')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'win-case')
        assert run_cmd('status', '--db', str(db)).stdout.strip() == 'IN_PROGRESS'

        run_cmd('move', '--db', str(db), '--from', 'fiction', '--to', 'mystery')
        assert run_cmd('status', '--db', str(db)).stdout.strip() == 'WIN'

    def test_desc_sort_mode_rejects_and_accepts_database_moves(self, tmp_path: Path) -> None:
        """DESC shelves should reject higher sort keys and accept lower sort keys."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'desc-case',
            shelves=[
                ('src', 1, 3, 'ANY', 'NONE'),
                ('desc', 2, 3, 'FIC', 'DESC'),
                ('buffer', 3, 3, 'ANY', 'NONE'),
            ],
            books=[
                ('fic-30', 'Thirty', 'FIC', 30, 'src', 0),
                ('fic-80', 'Eighty', 'FIC', 80, 'src', 1),
                ('anchor-50', 'Anchor', 'FIC', 50, 'desc', 0),
            ],
            edges=[('src', 'desc'), ('src', 'buffer')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'desc-case')
        before = run_cmd('show', '--db', str(db)).stdout

        rejected = run_cmd('move', '--db', str(db), '--from', 'src', '--to', 'desc', check=False)
        assert rejected.returncode != 0
        assert rejected.stderr.startswith('ERROR:')
        assert run_cmd('show', '--db', str(db)).stdout == before

        run_cmd('move', '--db', str(db), '--from', 'src', '--to', 'buffer')
        accepted = run_cmd('move', '--db', str(db), '--from', 'src', '--to', 'desc')
        assert accepted.stdout.strip() == 'OK moved fic-30 from src to desc'
        shown = run_cmd('show', '--db', str(db)).stdout
        assert (
            'Shelf desc [genre=FIC sort=DESC cap=3]: '
            'anchor-50(FIC:50) | fic-30(FIC:30)'
        ) in shown

    def test_missing_shelf_and_empty_source_fail_without_mutation(self, tmp_path: Path) -> None:
        """Move should reject nonexistent shelves and an empty source cleanly."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'missing-empty-case',
            shelves=[('source', 1, 1, 'ANY', 'NONE'), ('target', 2, 2, 'ANY', 'NONE')],
            books=[('only-book', 'Only', 'FIC', 1, 'source', 0)],
            edges=[('source', 'target'), ('target', 'source')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'missing-empty-case')
        before = run_cmd('show', '--db', str(db)).stdout

        missing_from = run_cmd(
            'move', '--db', str(db), '--from', 'ghost', '--to', 'target', check=False
        )
        missing_to = run_cmd(
            'move', '--db', str(db), '--from', 'source', '--to', 'ghost', check=False
        )
        assert missing_from.returncode != 0
        assert missing_to.returncode != 0
        assert missing_from.stderr.startswith('ERROR:')
        assert missing_to.stderr.startswith('ERROR:')
        assert run_cmd('show', '--db', str(db)).stdout == before

        run_cmd('move', '--db', str(db), '--from', 'source', '--to', 'target')
        empty = run_cmd('move', '--db', str(db), '--from', 'source', '--to', 'target', check=False)
        assert empty.returncode != 0
        assert empty.stderr.startswith('ERROR:')
        conn = sqlite3.connect(db)
        history_count = conn.execute('SELECT COUNT(*) FROM move_history').fetchone()[0]
        conn.close()
        assert history_count == 1

    def test_status_requires_ordering_not_only_genre_and_capacity(self, tmp_path: Path) -> None:
        """Status should remain IN_PROGRESS when genre is correct but ordering is wrong."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'status-order-case',
            shelves=[
                ('ordered', 1, 3, 'FIC', 'ASC'),
                ('stash', 2, 3, 'ANY', 'NONE'),
                ('buffer', 3, 2, 'ANY', 'NONE'),
            ],
            books=[
                ('fic-90', 'Ninety', 'FIC', 90, 'ordered', 0),
                ('fic-10', 'Ten', 'FIC', 10, 'ordered', 1),
            ],
            edges=[
                ('ordered', 'stash'),
                ('stash', 'buffer'),
                ('stash', 'ordered'),
                ('buffer', 'ordered'),
            ],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'status-order-case')
        assert run_cmd('status', '--db', str(db)).stdout.strip() == 'IN_PROGRESS'

        run_cmd('move', '--db', str(db), '--from', 'ordered', '--to', 'stash')
        run_cmd('move', '--db', str(db), '--from', 'ordered', '--to', 'stash')
        run_cmd('move', '--db', str(db), '--from', 'stash', '--to', 'buffer')
        run_cmd('move', '--db', str(db), '--from', 'stash', '--to', 'ordered')
        run_cmd('move', '--db', str(db), '--from', 'buffer', '--to', 'ordered')
        assert run_cmd('status', '--db', str(db)).stdout.strip() == 'WIN'

    def test_successive_undo_skips_already_undone_history_rows(self, tmp_path: Path) -> None:
        """Undo should restore the latest active move and ignore history already marked undone."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'multi-undo-case',
            shelves=[
                ('a', 1, 2, 'ANY', 'NONE'),
                ('b', 2, 2, 'ANY', 'NONE'),
                ('c', 3, 2, 'ANY', 'NONE'),
            ],
            books=[('book-1', 'One', 'FIC', 1, 'a', 0), ('book-2', 'Two', 'FIC', 2, 'a', 1)],
            edges=[('a', 'b'), ('a', 'c')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'multi-undo-case')
        original = run_cmd('show', '--db', str(db)).stdout
        run_cmd('move', '--db', str(db), '--from', 'a', '--to', 'b')
        after_first = run_cmd('show', '--db', str(db)).stdout
        run_cmd('move', '--db', str(db), '--from', 'a', '--to', 'c')

        run_cmd('undo', '--db', str(db))
        assert run_cmd('show', '--db', str(db)).stdout == after_first
        run_cmd('undo', '--db', str(db))
        assert run_cmd('show', '--db', str(db)).stdout == original
        final_undo = run_cmd('undo', '--db', str(db), check=False)
        assert final_undo.returncode != 0
        assert final_undo.stderr.startswith('ERROR:')

    def test_status_requires_any_buffer_shelves_to_be_empty(self, tmp_path: Path) -> None:
        """Status should not report WIN while an ANY buffer shelf still holds books."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'buffer-win-case',
            shelves=[
                ('fiction', 1, 2, 'FIC', 'ASC'),
                ('buffer', 2, 1, 'ANY', 'NONE'),
            ],
            books=[
                ('fic-10', 'Ten', 'FIC', 10, 'fiction', 0),
                ('fic-20', 'Twenty', 'FIC', 20, 'buffer', 0),
            ],
            edges=[('buffer', 'fiction')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'buffer-win-case')

        assert run_cmd('status', '--db', str(db)).stdout.strip() == 'IN_PROGRESS'
        run_cmd('move', '--db', str(db), '--from', 'buffer', '--to', 'fiction')
        assert run_cmd('status', '--db', str(db)).stdout.strip() == 'WIN'

    def test_hint_uses_shelf_position_order_not_seed_edge_insertion(self, tmp_path: Path) -> None:
        """Hint should sort candidate edges by shelf metadata instead of insertion order."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'hint-order-case',
            shelves=[
                ('alpha', 1, 1, 'ANY', 'NONE'),
                ('beta', 2, 1, 'ANY', 'NONE'),
                ('alpha-dest', 3, 1, 'ANY', 'NONE'),
                ('beta-dest', 4, 1, 'ANY', 'NONE'),
            ],
            books=[
                ('a-top', 'Alpha', 'FIC', 10, 'alpha', 0),
                ('b-top', 'Beta', 'MYS', 20, 'beta', 0),
            ],
            edges=[('beta', 'beta-dest'), ('alpha', 'alpha-dest')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'hint-order-case')
        before = run_cmd('show', '--db', str(db)).stdout

        assert run_cmd('hint', '--db', str(db)).stdout.strip() == 'MOVE alpha alpha-dest a-top'
        assert run_cmd('show', '--db', str(db)).stdout == before

    def test_hint_reports_first_legal_move_without_mutation(self, tmp_path: Path) -> None:
        """Hint should print the first legal move in edge order and leave state unchanged."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'hint-case',
            shelves=[
                ('fiction', 1, 3, 'FIC', 'ASC'),
                ('mystery', 2, 1, 'MYS', 'ASC'),
                ('buffer', 3, 2, 'ANY', 'NONE'),
            ],
            books=[
                ('fic-10', 'Fiction Ten', 'FIC', 10, 'fiction', 0),
                ('mys-20', 'Mystery Twenty', 'MYS', 20, 'fiction', 1),
                ('fic-30', 'Fiction Thirty', 'FIC', 30, 'fiction', 2),
            ],
            edges=[
                ('fiction', 'mystery'),
                ('fiction', 'buffer'),
                ('buffer', 'fiction'),
                ('mystery', 'buffer'),
            ],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'hint-case')
        before = run_cmd('show', '--db', str(db)).stdout

        hint = run_cmd('hint', '--db', str(db)).stdout.strip()

        assert hint == 'MOVE fiction buffer fic-30'
        assert run_cmd('show', '--db', str(db)).stdout == before
        conn = sqlite3.connect(db)
        history_count = conn.execute('SELECT COUNT(*) FROM move_history').fetchone()[0]
        conn.close()
        assert history_count == 0

    def test_hint_reports_no_move_when_all_candidates_are_illegal(self, tmp_path: Path) -> None:
        """Hint should report NO_MOVE when every routed top-book move is illegal."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'hint-no-move-case',
            shelves=[
                ('source', 1, 1, 'ANY', 'NONE'),
                ('fiction', 2, 1, 'FIC', 'ASC'),
                ('full', 3, 1, 'ANY', 'NONE'),
            ],
            books=[
                ('mys-20', 'Mystery', 'MYS', 20, 'source', 0),
                ('full-book', 'Full', 'FIC', 1, 'full', 0),
            ],
            edges=[('source', 'fiction'), ('source', 'full')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'hint-no-move-case')
        before = run_cmd('show', '--db', str(db)).stdout

        assert run_cmd('hint', '--db', str(db)).stdout.strip() == 'NO_MOVE'
        assert run_cmd('show', '--db', str(db)).stdout == before

    def test_solve_finds_shortest_plan_without_mutating_database(self, tmp_path: Path) -> None:
        """Solve should produce the shortest legal plan and leave the board unchanged."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'planner-case',
            shelves=[
                ('fiction', 1, 3, 'FIC', 'ASC'),
                ('mystery', 2, 1, 'MYS', 'ASC'),
                ('buffer', 3, 2, 'ANY', 'NONE'),
            ],
            books=[
                ('fic-10', 'Fiction Ten', 'FIC', 10, 'fiction', 0),
                ('mys-20', 'Mystery Twenty', 'MYS', 20, 'fiction', 1),
                ('fic-30', 'Fiction Thirty', 'FIC', 30, 'fiction', 2),
            ],
            edges=[
                ('fiction', 'mystery'),
                ('fiction', 'buffer'),
                ('buffer', 'fiction'),
                ('mystery', 'buffer'),
            ],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'planner-case')
        before = run_cmd('show', '--db', str(db)).stdout
        assert run_cmd('status', '--db', str(db)).stdout.strip() == 'IN_PROGRESS'

        plan = run_cmd('solve', '--db', str(db), '--max-depth', '3').stdout.splitlines()

        assert plan == [
            'MOVE fiction buffer fic-30',
            'MOVE fiction mystery mys-20',
            'MOVE buffer fiction fic-30',
        ]
        assert run_cmd('show', '--db', str(db)).stdout == before
        conn = sqlite3.connect(db)
        history_count = conn.execute('SELECT COUNT(*) FROM move_history').fetchone()[0]
        conn.close()
        assert history_count == 0

    def test_solve_handles_desc_goal_and_buffering(
        self, tmp_path: Path
    ) -> None:
        """Solve should find the shortest plan across DESC goals and temporary buffers."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'desc-planner-case',
            shelves=[
                ('fiction', 1, 4, 'FIC', 'ASC'),
                ('buffer', 2, 1, 'ANY', 'NONE'),
                ('mystery', 3, 2, 'MYS', 'DESC'),
            ],
            books=[
                ('fic-10', 'Fiction Ten', 'FIC', 10, 'fiction', 0),
                ('mys-20', 'Mystery Twenty', 'MYS', 20, 'fiction', 1),
                ('fic-30', 'Fiction Thirty', 'FIC', 30, 'fiction', 2),
                ('mys-40', 'Mystery Forty', 'MYS', 40, 'fiction', 3),
            ],
            edges=[
                ('fiction', 'buffer'),
                ('fiction', 'mystery'),
                ('buffer', 'fiction'),
            ],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'desc-planner-case')
        before = run_cmd('show', '--db', str(db)).stdout
        too_shallow = run_cmd('solve', '--db', str(db), '--max-depth', '3')
        assert too_shallow.stdout.strip() == 'NO_SOLUTION'

        plan = run_cmd('solve', '--db', str(db), '--max-depth', '4').stdout.splitlines()

        assert plan == [
            'MOVE fiction mystery mys-40',
            'MOVE fiction buffer fic-30',
            'MOVE fiction mystery mys-20',
            'MOVE buffer fiction fic-30',
        ]
        assert run_cmd('show', '--db', str(db)).stdout == before
        conn = sqlite3.connect(db)
        history_count = conn.execute('SELECT COUNT(*) FROM move_history').fetchone()[0]
        conn.close()
        assert history_count == 0

    def test_solve_backtracks_from_legal_dead_end_before_shortest_plan(self, tmp_path: Path) -> None:
        """Solve should explore legal branches and avoid returning a dead-end prefix."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'branch-case',
            shelves=[
                ('start', 1, 3, 'ANY', 'NONE'),
                ('trap', 2, 1, 'ANY', 'NONE'),
                ('fiction', 3, 2, 'FIC', 'DESC'),
                ('mystery', 4, 1, 'MYS', 'ASC'),
            ],
            books=[
                ('fic-10', 'Fic Ten', 'FIC', 10, 'start', 0),
                ('mys-20', 'Mystery Twenty', 'MYS', 20, 'start', 1),
                ('fic-30', 'Fic Thirty', 'FIC', 30, 'start', 2),
            ],
            edges=[
                ('start', 'trap'),      # first legal hint, but it cannot lead to WIN because trap is ANY and has no exit
                ('start', 'fiction'),
                ('start', 'mystery'),
                ('trap', 'fiction'),
                ('mystery', 'fiction'),
            ],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'branch-case')
        assert run_cmd('hint', '--db', str(db)).stdout.strip() == 'MOVE start trap fic-30'

        plan = run_cmd('solve', '--db', str(db), '--max-depth', '3').stdout.splitlines()

        assert plan == [
            'MOVE start fiction fic-30',
            'MOVE start mystery mys-20',
            'MOVE start fiction fic-10',
        ]
        assert json.loads(run_cmd('history', '--db', str(db)).stdout) == []

    def test_solve_uses_default_depth_and_leaves_history_empty(self, tmp_path: Path) -> None:
        """Solve without --max-depth should use the documented default and remain read-only."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'default-depth-case',
            shelves=[
                ('fiction', 1, 3, 'FIC', 'ASC'),
                ('mystery', 2, 1, 'MYS', 'ASC'),
                ('buffer', 3, 2, 'ANY', 'NONE'),
            ],
            books=[
                ('fic-10', 'Fiction Ten', 'FIC', 10, 'fiction', 0),
                ('mys-20', 'Mystery Twenty', 'MYS', 20, 'fiction', 1),
                ('fic-30', 'Fiction Thirty', 'FIC', 30, 'fiction', 2),
            ],
            edges=[
                ('fiction', 'mystery'),
                ('fiction', 'buffer'),
                ('buffer', 'fiction'),
                ('mystery', 'buffer'),
            ],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'default-depth-case')
        before = run_cmd('show', '--db', str(db)).stdout

        plan = run_cmd('solve', '--db', str(db)).stdout.splitlines()

        assert plan == [
            'MOVE fiction buffer fic-30',
            'MOVE fiction mystery mys-20',
            'MOVE buffer fiction fic-30',
        ]
        assert run_cmd('show', '--db', str(db)).stdout == before
        assert json.loads(run_cmd('history', '--db', str(db)).stdout) == []

    def test_solve_respects_depth_limit_and_already_solved_boards(self, tmp_path: Path) -> None:
        """Solve should report depth-limited failure and already-winning boards accurately."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'depth-case',
            shelves=[
                ('fiction', 1, 3, 'FIC', 'ASC'),
                ('mystery', 2, 1, 'MYS', 'ASC'),
                ('buffer', 3, 2, 'ANY', 'NONE'),
            ],
            books=[
                ('fic-10', 'Fiction Ten', 'FIC', 10, 'fiction', 0),
                ('mys-20', 'Mystery Twenty', 'MYS', 20, 'fiction', 1),
                ('fic-30', 'Fiction Thirty', 'FIC', 30, 'fiction', 2),
            ],
            edges=[
                ('fiction', 'mystery'),
                ('fiction', 'buffer'),
                ('buffer', 'fiction'),
                ('mystery', 'buffer'),
            ],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'depth-case')
        before = run_cmd('show', '--db', str(db)).stdout

        too_shallow = run_cmd('solve', '--db', str(db), '--max-depth', '2')
        assert too_shallow.stdout.strip() == 'NO_SOLUTION'
        assert run_cmd('show', '--db', str(db)).stdout == before

        run_cmd('move', '--db', str(db), '--from', 'fiction', '--to', 'buffer')
        run_cmd('move', '--db', str(db), '--from', 'fiction', '--to', 'mystery')
        run_cmd('move', '--db', str(db), '--from', 'buffer', '--to', 'fiction')
        assert run_cmd('status', '--db', str(db)).stdout.strip() == 'WIN'
        solved = run_cmd('solve', '--db', str(db), '--max-depth', '2')
        assert solved.stdout.strip() == 'ALREADY_SOLVED'

    def test_audit_replays_history_rows_and_undone_moves_from_seed(self, tmp_path: Path) -> None:
        """Audit should rebuild the seed board, replay history, and report matching digests."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'audit-valid-case',
            shelves=[
                ('start', 1, 3, 'ANY', 'NONE'),
                ('fiction', 2, 3, 'FIC', 'ASC'),
                ('buffer', 3, 2, 'ANY', 'NONE'),
            ],
            books=[
                ('fic-10', 'Ten', 'FIC', 10, 'start', 0),
                ('fic-20', 'Twenty', 'FIC', 20, 'start', 1),
            ],
            edges=[
                ('start', 'fiction'),
                ('fiction', 'buffer'),
                ('buffer', 'fiction'),
            ],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'audit-valid-case')
        run_cmd('move', '--db', str(db), '--from', 'start', '--to', 'fiction')
        run_cmd('undo', '--db', str(db))
        run_cmd('move', '--db', str(db), '--from', 'start', '--to', 'fiction')

        before = run_cmd('show', '--db', str(db)).stdout
        report = json.loads(
            run_cmd('audit', '--db', str(db), '--seed-db', str(seed), '--level', 'audit-valid-case').stdout
        )

        assert report['valid'] is True
        assert report['history_count'] == 2
        assert report['active_count'] == 1
        assert report['undone_count'] == 1
        assert report['first_bad_history_id'] is None
        assert report['current_digest'] == board_digest(db)
        assert report['replayed_digest'] == report['current_digest']
        assert run_cmd('show', '--db', str(db)).stdout == before
        assert len(json.loads(run_cmd('history', '--db', str(db)).stdout)) == 2

    def test_audit_detects_history_digest_tampering_without_mutating_state(self, tmp_path: Path) -> None:
        """Audit should pinpoint the first history row whose stored digest no longer replays."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'audit-tamper-case',
            shelves=[('start', 1, 2, 'ANY', 'NONE'), ('fiction', 2, 2, 'FIC', 'ASC')],
            books=[('fic-10', 'Ten', 'FIC', 10, 'start', 0)],
            edges=[('start', 'fiction')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'audit-tamper-case')
        run_cmd('move', '--db', str(db), '--from', 'start', '--to', 'fiction')
        before_show = run_cmd('show', '--db', str(db)).stdout
        before_history = json.loads(run_cmd('history', '--db', str(db)).stdout)

        conn = sqlite3.connect(db)
        conn.execute("UPDATE move_history SET after_digest=? WHERE id=1", ('0' * 64,))
        conn.commit()
        conn.close()

        report = json.loads(
            run_cmd('audit', '--db', str(db), '--seed-db', str(seed), '--level', 'audit-tamper-case').stdout
        )

        assert report['valid'] is False
        assert report['first_bad_history_id'] == 1
        assert report['history_count'] == 1
        assert report['active_count'] == 1
        assert report['undone_count'] == 0
        assert report['current_digest'] == board_digest(db)
        assert run_cmd('show', '--db', str(db)).stdout == before_show
        assert json.loads(run_cmd('history', '--db', str(db)).stdout)[0]['book_id'] == before_history[0]['book_id']

    def test_audit_reports_final_board_mismatch_as_zero_history_id(self, tmp_path: Path) -> None:
        """Audit should use first_bad_history_id 0 when history is valid but live books changed."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'audit-final-case',
            shelves=[('start', 1, 2, 'ANY', 'NONE'), ('fiction', 2, 2, 'FIC', 'ASC')],
            books=[('fic-10', 'Ten', 'FIC', 10, 'start', 0)],
            edges=[('start', 'fiction')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'audit-final-case')
        run_cmd('move', '--db', str(db), '--from', 'start', '--to', 'fiction')
        conn = sqlite3.connect(db)
        conn.execute("UPDATE books SET title='Tampered Title' WHERE book_id='fic-10'")
        conn.commit()
        conn.close()

        report = json.loads(
            run_cmd('audit', '--db', str(db), '--seed-db', str(seed), '--level', 'audit-final-case').stdout
        )

        assert report['valid'] is False
        assert report['first_bad_history_id'] == 0
        assert report['history_count'] == 1
        assert report['current_digest'] == board_digest(db)
        assert report['replayed_digest'] != report['current_digest']

    def test_apply_plan_commits_verified_multi_move_transaction_and_provenance(self, tmp_path: Path) -> None:
        """A digest-bound plan should commit all legal moves and one provenance row atomically."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        probe = tmp_path / 'probe.db'
        plan_file = tmp_path / 'plan.json'
        create_seed_db(
            seed,
            'plan-case',
            shelves=[
                ('start', 1, 3, 'ANY', 'NONE'),
                ('fiction', 2, 3, 'FIC', 'DESC'),
            ],
            books=[
                ('fic-10', 'Ten', 'FIC', 10, 'start', 0),
                ('fic-20', 'Twenty', 'FIC', 20, 'start', 1),
            ],
            edges=[('start', 'fiction')],
        )
        run_cmd('new', '--db', str(probe), '--seed-db', str(seed), '--level', 'plan-case')
        start_digest = board_digest(probe)
        run_cmd('move', '--db', str(probe), '--from', 'start', '--to', 'fiction')
        run_cmd('move', '--db', str(probe), '--from', 'start', '--to', 'fiction')
        final_digest = board_digest(probe)
        plan = {
            'expected_start_digest': start_digest,
            'expected_final_digest': final_digest,
            'moves': [
                {'from': 'start', 'to': 'fiction', 'book_id': 'fic-20'},
                {'from': 'start', 'to': 'fiction', 'book_id': 'fic-10'},
            ],
        }
        plan_file.write_text(json.dumps(plan))
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'plan-case')

        report = json.loads(run_cmd('apply-plan', '--db', str(db), '--file', str(plan_file)).stdout)

        assert report['start_digest'] == start_digest
        assert report['final_digest'] == final_digest
        assert report['move_count'] == 2
        canonical_plan = (
            f"{start_digest}\n{final_digest}\n"
            "start|fiction|fic-20\n"
            "start|fiction|fic-10\n"
        )
        assert report['plan_id'] == hashlib.sha256(canonical_plan.encode()).hexdigest()
        assert board_digest(db) == final_digest
        conn = sqlite3.connect(db)
        history = conn.execute(
            'SELECT book_id, before_digest, after_digest, undone FROM move_history ORDER BY id'
        ).fetchall()
        provenance = conn.execute(
            'SELECT plan_id, start_digest, final_digest, move_count FROM plan_runs'
        ).fetchall()
        conn.close()
        assert [row[0] for row in history] == ['fic-20', 'fic-10']
        assert history[0][1] == start_digest
        assert history[-1][2] == final_digest
        assert all(row[3] == 0 for row in history)
        assert provenance == [(report['plan_id'], start_digest, final_digest, 2)]

    def test_apply_plan_rejects_mid_plan_failure_without_partial_state(self, tmp_path: Path) -> None:
        """A plan with a later illegal step should leave books, history, and plan provenance unchanged."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        plan_file = tmp_path / 'bad-plan.json'
        create_seed_db(
            seed,
            'plan-rollback-case',
            shelves=[('start', 1, 2, 'ANY', 'NONE'), ('fiction', 2, 2, 'FIC', 'ASC')],
            books=[('fic-10', 'Ten', 'FIC', 10, 'start', 0)],
            edges=[('start', 'fiction')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'plan-rollback-case')
        before_show = run_cmd('show', '--db', str(db)).stdout
        before_digest = board_digest(db)
        plan_file.write_text(json.dumps({
            'expected_start_digest': before_digest,
            'expected_final_digest': 'f' * 64,
            'moves': [
                {'from': 'start', 'to': 'fiction', 'book_id': 'fic-10'},
                {'from': 'start', 'to': 'fiction', 'book_id': 'fic-10'},
            ],
        }))

        result = run_cmd('apply-plan', '--db', str(db), '--file', str(plan_file), check=False)

        assert result.returncode != 0
        assert result.stderr.startswith('ERROR:')
        assert run_cmd('show', '--db', str(db)).stdout == before_show
        assert board_digest(db) == before_digest
        conn = sqlite3.connect(db)
        assert conn.execute('SELECT COUNT(*) FROM move_history').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM plan_runs').fetchone()[0] == 0
        conn.close()

    def test_redo_reapplies_latest_undone_move_without_new_history_row(self, tmp_path: Path) -> None:
        """Redo should reactivate the newest undone row only when its digest-bound move still matches."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'redo-case',
            shelves=[('start', 1, 2, 'ANY', 'NONE'), ('fiction', 2, 2, 'FIC', 'ASC')],
            books=[('fic-10', 'Ten', 'FIC', 10, 'start', 0)],
            edges=[('start', 'fiction')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'redo-case')
        run_cmd('move', '--db', str(db), '--from', 'start', '--to', 'fiction')
        moved_digest = board_digest(db)
        run_cmd('undo', '--db', str(db))

        result = run_cmd('redo', '--db', str(db))

        assert result.stdout == 'OK redone fic-10\n'
        assert board_digest(db) == moved_digest
        history = json.loads(run_cmd('history', '--db', str(db)).stdout)
        assert len(history) == 1
        assert history[0]['undone'] == 0
        assert history[0]['after_digest'] == moved_digest

    def test_redo_refuses_stale_board_and_preserves_undone_marker(self, tmp_path: Path) -> None:
        """Redo should fail without mutation when the live board no longer matches the row's before digest."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'redo-stale-case',
            shelves=[('start', 1, 2, 'ANY', 'NONE'), ('fiction', 2, 2, 'FIC', 'ASC')],
            books=[('fic-10', 'Ten', 'FIC', 10, 'start', 0)],
            edges=[('start', 'fiction')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'redo-stale-case')
        run_cmd('move', '--db', str(db), '--from', 'start', '--to', 'fiction')
        run_cmd('undo', '--db', str(db))
        conn = sqlite3.connect(db)
        conn.execute("UPDATE books SET title='Changed' WHERE book_id='fic-10'")
        conn.commit()
        conn.close()
        before = run_cmd('show', '--db', str(db)).stdout

        result = run_cmd('redo', '--db', str(db), check=False)

        assert result.returncode != 0
        assert result.stderr.startswith('ERROR:')
        assert run_cmd('show', '--db', str(db)).stdout == before
        history = json.loads(run_cmd('history', '--db', str(db)).stdout)
        assert history[0]['undone'] == 1


    def test_apply_plan_rejects_unknown_fields_and_noncanonical_digests(self, tmp_path: Path) -> None:
        """Plan parsing should reject schema extensions and uppercase digest spellings without mutation."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        plan_file = tmp_path / 'invalid-plan.json'
        create_seed_db(
            seed,
            'plan-schema-case',
            shelves=[('start', 1, 2, 'ANY', 'NONE'), ('fiction', 2, 2, 'FIC', 'ASC')],
            books=[('fic-10', 'Ten', 'FIC', 10, 'start', 0)],
            edges=[('start', 'fiction')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'plan-schema-case')
        before = board_digest(db)
        invalid_plans = [
            {
                'expected_start_digest': before,
                'expected_final_digest': before,
                'moves': [{'from': 'start', 'to': 'fiction', 'book_id': 'fic-10'}],
                'unexpected': True,
            },
            {
                'expected_start_digest': before.upper(),
                'expected_final_digest': before,
                'moves': [{'from': 'start', 'to': 'fiction', 'book_id': 'fic-10'}],
            },
        ]
        for payload in invalid_plans:
            plan_file.write_text(json.dumps(payload))
            result = run_cmd('apply-plan', '--db', str(db), '--file', str(plan_file), check=False)
            assert result.returncode != 0
            assert result.stderr.startswith('ERROR:')
            assert board_digest(db) == before

        conn = sqlite3.connect(db)
        assert conn.execute('SELECT COUNT(*) FROM move_history').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM plan_runs').fetchone()[0] == 0
        conn.close()

    def test_apply_batch_topologically_orders_ready_operations_and_records_history_links(self, tmp_path: Path) -> None:
        """A dependency batch should use lexical ready-order and persist exact execution provenance atomically."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        probe = tmp_path / 'probe.db'
        batch_file = tmp_path / 'batch.json'
        create_seed_db(
            seed,
            'batch-order-case',
            shelves=[
                ('source-a', 1, 2, 'ANY', 'NONE'),
                ('source-b', 2, 2, 'ANY', 'NONE'),
                ('fiction', 3, 3, 'FIC', 'DESC'),
            ],
            books=[
                ('fic-30', 'Thirty', 'FIC', 30, 'source-a', 0),
                ('fic-20', 'Twenty', 'FIC', 20, 'source-b', 0),
            ],
            edges=[('source-a', 'fiction'), ('source-b', 'fiction')],
        )
        run_cmd('new', '--db', str(probe), '--seed-db', str(seed), '--level', 'batch-order-case')
        start_digest = board_digest(probe)
        run_cmd('move', '--db', str(probe), '--from', 'source-a', '--to', 'fiction')
        digest_a = board_digest(probe)
        run_cmd('move', '--db', str(probe), '--from', 'source-b', '--to', 'fiction')
        digest_b = board_digest(probe)
        payload = {
            'expected_start_digest': start_digest,
            'expected_final_digest': digest_b,
            'operations': [
                {
                    'id': 'op-b',
                    'from': 'source-b',
                    'to': 'fiction',
                    'book_id': 'fic-20',
                    'expected_after_digest': digest_b,
                    'depends_on': [],
                },
                {
                    'id': 'op-a',
                    'from': 'source-a',
                    'to': 'fiction',
                    'book_id': 'fic-30',
                    'expected_after_digest': digest_a,
                    'depends_on': [],
                },
            ],
        }
        batch_file.write_text(json.dumps(payload))
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'batch-order-case')

        report = json.loads(run_cmd('apply-batch', '--db', str(db), '--file', str(batch_file)).stdout)

        assert report['execution_ids'] == ['op-a', 'op-b']
        assert report['start_digest'] == start_digest
        assert report['final_digest'] == digest_b
        assert report['step_count'] == 2
        canonical = (
            f'{start_digest}\n{digest_b}\n'
            f'op-a|source-a|fiction|fic-30|{digest_a}|\n'
            f'op-b|source-b|fiction|fic-20|{digest_b}|\n'
        )
        assert report['batch_id'] == hashlib.sha256(canonical.encode()).hexdigest()
        assert board_digest(db) == digest_b
        conn = sqlite3.connect(db)
        history = conn.execute(
            'SELECT id, book_id, before_digest, after_digest FROM move_history ORDER BY id'
        ).fetchall()
        run_row = conn.execute(
            'SELECT batch_id, start_digest, final_digest, step_count FROM batch_runs'
        ).fetchone()
        step_rows = conn.execute(
            'SELECT step_index, operation_id, history_id, after_digest FROM batch_steps ORDER BY step_index'
        ).fetchall()
        conn.close()
        assert [row[1] for row in history] == ['fic-30', 'fic-20']
        assert history[0][2] == start_digest and history[0][3] == digest_a
        assert history[1][2] == digest_a and history[1][3] == digest_b
        assert run_row == (report['batch_id'], start_digest, digest_b, 2)
        assert step_rows == [
            (0, 'op-a', history[0][0], digest_a),
            (1, 'op-b', history[1][0], digest_b),
        ]

    def test_apply_batch_honors_dependencies_even_when_ids_would_otherwise_sort_first(self, tmp_path: Path) -> None:
        """Dependencies should override lexical ordering while each ready-set tie remains deterministic."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        probe = tmp_path / 'probe.db'
        batch_file = tmp_path / 'dependent-batch.json'
        create_seed_db(
            seed,
            'batch-dependency-case',
            shelves=[('start', 1, 3, 'ANY', 'NONE'), ('fiction', 2, 3, 'FIC', 'DESC')],
            books=[
                ('fic-10', 'Ten', 'FIC', 10, 'start', 0),
                ('fic-20', 'Twenty', 'FIC', 20, 'start', 1),
            ],
            edges=[('start', 'fiction')],
        )
        run_cmd('new', '--db', str(probe), '--seed-db', str(seed), '--level', 'batch-dependency-case')
        start = board_digest(probe)
        run_cmd('move', '--db', str(probe), '--from', 'start', '--to', 'fiction')
        first = board_digest(probe)
        run_cmd('move', '--db', str(probe), '--from', 'start', '--to', 'fiction')
        final = board_digest(probe)
        payload = {
            'expected_start_digest': start,
            'expected_final_digest': final,
            'operations': [
                {
                    'id': 'a-second',
                    'from': 'start',
                    'to': 'fiction',
                    'book_id': 'fic-10',
                    'expected_after_digest': final,
                    'depends_on': ['z-first'],
                },
                {
                    'id': 'z-first',
                    'from': 'start',
                    'to': 'fiction',
                    'book_id': 'fic-20',
                    'expected_after_digest': first,
                    'depends_on': [],
                },
            ],
        }
        batch_file.write_text(json.dumps(payload))
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'batch-dependency-case')

        report = json.loads(run_cmd('apply-batch', '--db', str(db), '--file', str(batch_file)).stdout)

        assert report['execution_ids'] == ['z-first', 'a-second']
        assert board_digest(db) == final

    def test_apply_batch_rejects_graph_and_schema_errors_without_creating_provenance(self, tmp_path: Path) -> None:
        """Cycles, unknown dependencies, repeated dependencies, and unknown JSON fields should be read-only failures."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        batch_file = tmp_path / 'invalid-batch.json'
        create_seed_db(
            seed,
            'batch-invalid-case',
            shelves=[('start', 1, 2, 'ANY', 'NONE'), ('fiction', 2, 2, 'FIC', 'ASC')],
            books=[('fic-10', 'Ten', 'FIC', 10, 'start', 0)],
            edges=[('start', 'fiction')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'batch-invalid-case')
        digest = board_digest(db)
        base_op = {
            'id': 'op-a',
            'from': 'start',
            'to': 'fiction',
            'book_id': 'fic-10',
            'expected_after_digest': digest,
            'depends_on': [],
        }
        payloads = [
            {
                'expected_start_digest': digest,
                'expected_final_digest': digest,
                'operations': [dict(base_op, depends_on=['op-b']), dict(base_op, id='op-b', depends_on=['op-a'])],
            },
            {
                'expected_start_digest': digest,
                'expected_final_digest': digest,
                'operations': [dict(base_op, depends_on=['missing'])],
            },
            {
                'expected_start_digest': digest,
                'expected_final_digest': digest,
                'operations': [dict(base_op, depends_on=['other', 'other']), dict(base_op, id='other')],
            },
            {
                'expected_start_digest': digest,
                'expected_final_digest': digest,
                'operations': [dict(base_op, extra=True)],
            },
        ]
        for payload in payloads:
            batch_file.write_text(json.dumps(payload))
            result = run_cmd('apply-batch', '--db', str(db), '--file', str(batch_file), check=False)
            assert result.returncode != 0
            assert result.stderr.startswith('ERROR:')
            assert board_digest(db) == digest
        conn = sqlite3.connect(db)
        assert conn.execute('SELECT COUNT(*) FROM move_history').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM batch_runs').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM batch_steps').fetchone()[0] == 0
        conn.close()

    def test_apply_batch_rejects_late_operation_digest_atomically(self, tmp_path: Path) -> None:
        """A late per-operation digest mismatch should roll back all books, history, and batch provenance."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        probe = tmp_path / 'probe.db'
        batch_file = tmp_path / 'stale-batch.json'
        create_seed_db(
            seed,
            'batch-rollback-case',
            shelves=[('start', 1, 3, 'ANY', 'NONE'), ('fiction', 2, 3, 'FIC', 'DESC')],
            books=[
                ('fic-10', 'Ten', 'FIC', 10, 'start', 0),
                ('fic-20', 'Twenty', 'FIC', 20, 'start', 1),
            ],
            edges=[('start', 'fiction')],
        )
        run_cmd('new', '--db', str(probe), '--seed-db', str(seed), '--level', 'batch-rollback-case')
        start = board_digest(probe)
        run_cmd('move', '--db', str(probe), '--from', 'start', '--to', 'fiction')
        first = board_digest(probe)
        run_cmd('move', '--db', str(probe), '--from', 'start', '--to', 'fiction')
        final = board_digest(probe)
        batch_file.write_text(json.dumps({
            'expected_start_digest': start,
            'expected_final_digest': final,
            'operations': [
                {
                    'id': 'first', 'from': 'start', 'to': 'fiction', 'book_id': 'fic-20',
                    'expected_after_digest': first, 'depends_on': [],
                },
                {
                    'id': 'second', 'from': 'start', 'to': 'fiction', 'book_id': 'fic-10',
                    'expected_after_digest': '0' * 64, 'depends_on': ['first'],
                },
            ],
        }))
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'batch-rollback-case')
        before_show = run_cmd('show', '--db', str(db)).stdout

        result = run_cmd('apply-batch', '--db', str(db), '--file', str(batch_file), check=False)

        assert result.returncode != 0
        assert result.stderr.startswith('ERROR:')
        assert run_cmd('show', '--db', str(db)).stdout == before_show
        assert board_digest(db) == start
        conn = sqlite3.connect(db)
        assert conn.execute('SELECT COUNT(*) FROM move_history').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM batch_runs').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM batch_steps').fetchone()[0] == 0
        conn.close()

    def test_verify_ledger_validates_history_root_and_plan_provenance(self, tmp_path: Path) -> None:
        """A clean planned transaction should replay, chain, and verify through its provenance rows."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        probe = tmp_path / 'probe.db'
        plan_file = tmp_path / 'plan.json'
        create_seed_db(
            seed,
            'ledger-plan-case',
            shelves=[('start', 1, 3, 'ANY', 'NONE'), ('fiction', 2, 3, 'FIC', 'DESC')],
            books=[
                ('fic-10', 'Ten', 'FIC', 10, 'start', 0),
                ('fic-20', 'Twenty', 'FIC', 20, 'start', 1),
            ],
            edges=[('start', 'fiction')],
        )
        run_cmd('new', '--db', str(probe), '--seed-db', str(seed), '--level', 'ledger-plan-case')
        start = board_digest(probe)
        run_cmd('move', '--db', str(probe), '--from', 'start', '--to', 'fiction')
        run_cmd('move', '--db', str(probe), '--from', 'start', '--to', 'fiction')
        final = board_digest(probe)
        plan_file.write_text(json.dumps({
            'expected_start_digest': start,
            'expected_final_digest': final,
            'moves': [
                {'from': 'start', 'to': 'fiction', 'book_id': 'fic-20'},
                {'from': 'start', 'to': 'fiction', 'book_id': 'fic-10'},
            ],
        }))
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'ledger-plan-case')
        plan_report = json.loads(run_cmd('apply-plan', '--db', str(db), '--file', str(plan_file)).stdout)

        report = json.loads(run_cmd(
            'verify-ledger', '--db', str(db), '--seed-db', str(seed), '--level', 'ledger-plan-case'
        ).stdout)

        conn = sqlite3.connect(db)
        rows = conn.execute(
            'SELECT id,book_id,from_shelf,to_shelf,from_slot,to_slot,before_digest,after_digest,undone '
            'FROM move_history ORDER BY id'
        ).fetchall()
        plan_steps = conn.execute(
            'SELECT step_index,history_id,after_digest FROM plan_steps WHERE plan_id=? ORDER BY step_index',
            (plan_report['plan_id'],),
        ).fetchall()
        conn.close()
        root = hashlib.sha256(b'booksort-ledger-v1\n').hexdigest()
        for row in rows:
            line = '|'.join(map(str, row)) + '\n'
            root = hashlib.sha256((root + '\n' + line).encode()).hexdigest()
        assert report == {
            'current_digest': final,
            'replayed_digest': final,
            'history_root': root,
            'history_count': 2,
            'plan_count': 1,
            'batch_count': 0,
            'valid': True,
            'first_error': None,
        }
        assert plan_steps == [
            (0, rows[0][0], rows[0][7]),
            (1, rows[1][0], rows[1][7]),
        ]

    def test_verify_ledger_identifies_history_before_provenance_failures(self, tmp_path: Path) -> None:
        """History replay corruption should take precedence over later plan or batch provenance defects."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'ledger-history-case',
            shelves=[('start', 1, 2, 'ANY', 'NONE'), ('fiction', 2, 2, 'FIC', 'ASC')],
            books=[('fic-10', 'Ten', 'FIC', 10, 'start', 0)],
            edges=[('start', 'fiction')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'ledger-history-case')
        run_cmd('move', '--db', str(db), '--from', 'start', '--to', 'fiction')
        conn = sqlite3.connect(db)
        conn.execute("UPDATE move_history SET before_digest=? WHERE id=1", ('0' * 64,))
        conn.execute(
            "INSERT INTO batch_steps(batch_id,step_index,operation_id,history_id,after_digest) VALUES ('orphan',0,'x',1,?)",
            ('0' * 64,),
        )
        conn.commit()
        conn.close()

        report = json.loads(run_cmd(
            'verify-ledger', '--db', str(db), '--seed-db', str(seed), '--level', 'ledger-history-case'
        ).stdout)

        assert report['valid'] is False
        assert report['first_error'] == 'history:1'
        assert report['history_count'] == 1

    def test_verify_ledger_rejects_broken_plan_chain_without_mutation(self, tmp_path: Path) -> None:
        """A provenance digest that no longer matches its history row should report the owning plan deterministically."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        probe = tmp_path / 'probe.db'
        plan_file = tmp_path / 'plan.json'
        create_seed_db(
            seed,
            'ledger-plan-tamper-case',
            shelves=[('start', 1, 2, 'ANY', 'NONE'), ('fiction', 2, 2, 'FIC', 'ASC')],
            books=[('fic-10', 'Ten', 'FIC', 10, 'start', 0)],
            edges=[('start', 'fiction')],
        )
        run_cmd('new', '--db', str(probe), '--seed-db', str(seed), '--level', 'ledger-plan-tamper-case')
        start = board_digest(probe)
        run_cmd('move', '--db', str(probe), '--from', 'start', '--to', 'fiction')
        final = board_digest(probe)
        plan_file.write_text(json.dumps({
            'expected_start_digest': start,
            'expected_final_digest': final,
            'moves': [{'from': 'start', 'to': 'fiction', 'book_id': 'fic-10'}],
        }))
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'ledger-plan-tamper-case')
        plan = json.loads(run_cmd('apply-plan', '--db', str(db), '--file', str(plan_file)).stdout)
        before_show = run_cmd('show', '--db', str(db)).stdout
        conn = sqlite3.connect(db)
        conn.execute('UPDATE plan_steps SET after_digest=?', ('f' * 64,))
        conn.commit()
        conn.close()

        report = json.loads(run_cmd(
            'verify-ledger', '--db', str(db), '--seed-db', str(seed), '--level', 'ledger-plan-tamper-case'
        ).stdout)

        assert report['valid'] is False
        assert report['first_error'] == f"plan:{plan['plan_id']}"
        assert run_cmd('show', '--db', str(db)).stdout == before_show

    def test_verify_ledger_reports_orphan_batch_steps_before_board_mismatch(self, tmp_path: Path) -> None:
        """An orphaned batch step should be surfaced before a later live-board divergence and remain read-only."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'ledger-orphan-case',
            shelves=[('start', 1, 2, 'ANY', 'NONE'), ('fiction', 2, 2, 'FIC', 'ASC')],
            books=[('fic-10', 'Ten', 'FIC', 10, 'start', 0)],
            edges=[('start', 'fiction')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'ledger-orphan-case')
        run_cmd('move', '--db', str(db), '--from', 'start', '--to', 'fiction')
        conn = sqlite3.connect(db)
        history_id, after_digest = conn.execute('SELECT id,after_digest FROM move_history').fetchone()
        conn.execute(
            "INSERT INTO batch_steps(batch_id,step_index,operation_id,history_id,after_digest) VALUES ('missing-run',0,'op',?,?)",
            (history_id, after_digest),
        )
        conn.execute("UPDATE books SET shelf_id='start',slot=0 WHERE book_id='fic-10'")
        conn.commit()
        conn.close()
        before = db.read_bytes()

        report = json.loads(run_cmd(
            'verify-ledger', '--db', str(db), '--seed-db', str(seed), '--level', 'ledger-orphan-case'
        ).stdout)

        assert report['valid'] is False
        assert report['first_error'] == 'batch:missing-run'
        assert db.read_bytes() == before

    def test_verify_ledger_reports_board_when_all_rows_are_internally_consistent(self, tmp_path: Path) -> None:
        """A live board changed outside history should yield the terminal board error after all row checks pass."""
        seed = tmp_path / 'levels.db'
        db = tmp_path / 'game.db'
        create_seed_db(
            seed,
            'ledger-board-case',
            shelves=[('start', 1, 2, 'ANY', 'NONE'), ('fiction', 2, 2, 'FIC', 'ASC')],
            books=[('fic-10', 'Ten', 'FIC', 10, 'start', 0)],
            edges=[('start', 'fiction')],
        )
        run_cmd('new', '--db', str(db), '--seed-db', str(seed), '--level', 'ledger-board-case')
        conn = sqlite3.connect(db)
        conn.execute("UPDATE books SET shelf_id='fiction',slot=0 WHERE book_id='fic-10'")
        conn.commit()
        conn.close()

        report = json.loads(run_cmd(
            'verify-ledger', '--db', str(db), '--seed-db', str(seed), '--level', 'ledger-board-case'
        ).stdout)

        assert report['valid'] is False
        assert report['first_error'] == 'board'
        assert report['history_count'] == 0
