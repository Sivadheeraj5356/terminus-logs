package main

import (
	"database/sql"

	_ "modernc.org/sqlite"
)

// openDB opens (or creates) a SQLite database at the given path.
func openDB(path string) (*sql.DB, error) {
	return sql.Open("sqlite", path)
}
