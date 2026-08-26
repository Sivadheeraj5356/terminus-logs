package main

import "database/sql"

// runMigrations creates all application tables if they do not already exist.
func runMigrations(db *sql.DB) error {
	stmts := []string{
		sqlCreateAgentsTable,
		sqlCreateTicketsTable,
		sqlCreateResolutionsTable,
		sqlCreateResolutionChainTable,
	}
	for _, stmt := range stmts {
		if _, err := db.Exec(stmt); err != nil {
			return err
		}
	}
	return nil
}
