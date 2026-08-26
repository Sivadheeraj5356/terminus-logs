package main

const (
	sqlCreateAgentsTable = `
CREATE TABLE IF NOT EXISTS agents (
	agent_id TEXT PRIMARY KEY,
	name     TEXT NOT NULL,
	tier     TEXT NOT NULL CHECK(tier IN ('L1','L2','L3'))
);`

	sqlCreateTicketsTable = `
CREATE TABLE IF NOT EXISTS tickets (
	ticket_id         TEXT PRIMARY KEY,
	title             TEXT NOT NULL,
	priority          TEXT NOT NULL CHECK(priority IN ('low','medium','high','critical')),
	status            TEXT NOT NULL DEFAULT 'open',
	assigned_agent_id TEXT,
	opened_at         TEXT NOT NULL DEFAULT (datetime('now'))
);`

	sqlCreateResolutionsTable = `
CREATE TABLE IF NOT EXISTS resolutions (
	resolution_id      INTEGER PRIMARY KEY AUTOINCREMENT,
	ticket_id          TEXT NOT NULL,
	agent_id           TEXT NOT NULL,
	resolution_minutes INTEGER NOT NULL,
	sla_met            INTEGER NOT NULL,
	resolved_at        TEXT NOT NULL
);`

	sqlCreateResolutionChainTable = `
CREATE TABLE IF NOT EXISTS resolution_chain (
	chain_id           INTEGER PRIMARY KEY AUTOINCREMENT,
	ticket_id          TEXT NOT NULL,
	agent_id           TEXT NOT NULL,
	resolution_minutes INTEGER NOT NULL,
	sla_met            TEXT NOT NULL,
	resolved_at        TEXT NOT NULL,
	prev_hash          TEXT NOT NULL,
	current_hash       TEXT NOT NULL
);`
)
