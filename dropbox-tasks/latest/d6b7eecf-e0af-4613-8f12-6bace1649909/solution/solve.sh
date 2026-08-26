#!/bin/bash
set -euo pipefail

cd /app
cat > /app/cmd/booksort/main.go <<'GO'
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

type Shelf struct {
	ID       string
	Position int
	Capacity int
	Genre    string
	Sort     string
}

type Book struct {
	ID      string
	Title   string
	Genre   string
	SortKey int
	Shelf   string
	Slot    int
}

type Edge struct {
	From string
	To   string
}

type Move struct {
	From string
	To   string
	Book Book
}

type Board struct {
	Shelves []Shelf
	Books   map[string]Book
	Edges   []Edge
}

func die(msg string) {
	fmt.Fprintln(os.Stderr, "ERROR: "+msg)
	os.Exit(1)
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: booksort <new|show|move|undo|redo|status|history|hint|solve|audit|apply-plan|apply-batch|verify-ledger> --db PATH ...")
	os.Exit(2)
}

func sqlQuote(v string) string {
	return "'" + strings.ReplaceAll(v, "'", "''") + "'"
}

func sqlite(db string, query string) (string, error) {
	cmd := exec.Command("sqlite3", "-batch", "-noheader", "-separator", "|", db, query)
	out, err := cmd.CombinedOutput()
	return string(out), err
}

func runSQL(db string, query string) string {
	out, err := sqlite(db, query)
	if err != nil {
		msg := strings.TrimSpace(out)
		if msg == "" {
			msg = err.Error()
		}
		die(msg)
	}
	return out
}

func parseFlags(args []string) map[string]string {
	flags := map[string]string{}
	for i := 0; i < len(args); i++ {
		if !strings.HasPrefix(args[i], "--") || i+1 >= len(args) {
			usage()
		}
		flags[strings.TrimPrefix(args[i], "--")] = args[i+1]
		i++
	}
	return flags
}

func requireFlag(flags map[string]string, name string) string {
	value, ok := flags[name]
	if !ok || value == "" {
		usage()
	}
	return value
}

func optionalInt(flags map[string]string, name string, def int) int {
	value, ok := flags[name]
	if !ok || value == "" {
		return def
	}
	n, err := strconv.Atoi(value)
	if err != nil || n < 0 {
		usage()
	}
	return n
}

func splitRows(out string) []string {
	trimmed := strings.TrimSpace(out)
	if trimmed == "" {
		return nil
	}
	return strings.Split(trimmed, "\n")
}

func atoi(s string) int {
	n, err := strconv.Atoi(s)
	if err != nil {
		die("bad integer in database")
	}
	return n
}

func shelfByID(db, id string) (Shelf, bool) {
	out := runSQL(db, "SELECT shelf_id, position, capacity, required_genre, sort_mode FROM shelves WHERE shelf_id="+sqlQuote(id)+";")
	rows := splitRows(out)
	if len(rows) == 0 {
		return Shelf{}, false
	}
	parts := strings.Split(rows[0], "|")
	return Shelf{ID: parts[0], Position: atoi(parts[1]), Capacity: atoi(parts[2]), Genre: parts[3], Sort: strings.ToUpper(parts[4])}, true
}

func topBook(db, shelf string) (Book, bool) {
	out := runSQL(db, "SELECT book_id, title, genre, sort_key, shelf_id, slot FROM books WHERE shelf_id="+sqlQuote(shelf)+" ORDER BY slot DESC LIMIT 1;")
	rows := splitRows(out)
	if len(rows) == 0 {
		return Book{}, false
	}
	parts := strings.Split(rows[0], "|")
	return Book{ID: parts[0], Title: parts[1], Genre: parts[2], SortKey: atoi(parts[3]), Shelf: parts[4], Slot: atoi(parts[5])}, true
}

func targetBooksWithCandidate(db, shelf string, candidate Book) []Book {
	out := runSQL(db, "SELECT book_id, title, genre, sort_key, shelf_id, slot FROM books WHERE shelf_id="+sqlQuote(shelf)+" ORDER BY slot ASC;")
	books := []Book{}
	for _, row := range splitRows(out) {
		parts := strings.Split(row, "|")
		books = append(books, Book{ID: parts[0], Title: parts[1], Genre: parts[2], SortKey: atoi(parts[3]), Shelf: parts[4], Slot: atoi(parts[5])})
	}
	books = append(books, candidate)
	return books
}

func nextSlot(db, shelf string) int {
	out := strings.TrimSpace(runSQL(db, "SELECT COALESCE(MAX(slot)+1, 0) FROM books WHERE shelf_id="+sqlQuote(shelf)+";"))
	if out == "" {
		return 0
	}
	return atoi(out)
}

func countBooks(db, shelf string) int {
	out := strings.TrimSpace(runSQL(db, "SELECT COUNT(*) FROM books WHERE shelf_id="+sqlQuote(shelf)+";"))
	if out == "" {
		return 0
	}
	return atoi(out)
}

func commandNew(args []string) {
	flags := parseFlags(args)
	db := requireFlag(flags, "db")
	seed := requireFlag(flags, "seed-db")
	level := requireFlag(flags, "level")
	initializeRuntimeDB(db, seed, level, true)
}

func commandShow(args []string) {
	flags := parseFlags(args)
	db := requireFlag(flags, "db")
	out := runSQL(db, "SELECT shelf_id, position, capacity, required_genre, sort_mode FROM shelves ORDER BY position ASC, shelf_id ASC;")
	for _, row := range splitRows(out) {
		parts := strings.Split(row, "|")
		shelf := Shelf{ID: parts[0], Position: atoi(parts[1]), Capacity: atoi(parts[2]), Genre: parts[3], Sort: strings.ToUpper(parts[4])}
		bout := runSQL(db, "SELECT book_id || '(' || genre || ':' || sort_key || ')' FROM books WHERE shelf_id="+sqlQuote(shelf.ID)+" ORDER BY slot ASC;")
		books := splitRows(bout)
		suffix := ""
		if len(books) > 0 {
			suffix = " " + strings.Join(books, " | ")
		}
		fmt.Printf("Shelf %s [genre=%s sort=%s cap=%d]:%s\n", shelf.ID, shelf.Genre, shelf.Sort, shelf.Capacity, suffix)
	}
}

func validateMove(db, from, to string) (Book, int) {
	if from == to {
		die("source and target shelves must differ")
	}
	_, ok := shelfByID(db, from)
	if !ok {
		die("source shelf not found")
	}
	target, ok := shelfByID(db, to)
	if !ok {
		die("target shelf not found")
	}
	edge := strings.TrimSpace(runSQL(db, "SELECT COUNT(*) FROM edges WHERE from_shelf="+sqlQuote(from)+" AND to_shelf="+sqlQuote(to)+";"))
	if edge != "1" {
		die("route is not allowed")
	}
	book, ok := topBook(db, from)
	if !ok {
		die("source shelf is empty")
	}
	if countBooks(db, to) >= target.Capacity {
		die("target shelf is full")
	}
	if target.Genre != "ANY" && book.Genre != target.Genre {
		die("book genre does not match target shelf")
	}
	toSlot := nextSlot(db, to)
	candidate := book
	candidate.Shelf = to
	candidate.Slot = toSlot
	books := targetBooksWithCandidate(db, to, candidate)
	for i := 1; i < len(books); i++ {
		if target.Sort == "ASC" && books[i-1].SortKey > books[i].SortKey {
			die("target shelf ordering would be broken")
		}
		if target.Sort == "DESC" && books[i-1].SortKey < books[i].SortKey {
			die("target shelf ordering would be broken")
		}
	}
	return book, toSlot
}

func commandMove(args []string) {
	flags := parseFlags(args)
	db := requireFlag(flags, "db")
	from := requireFlag(flags, "from")
	to := requireFlag(flags, "to")
	start := loadBoard(db)
	beforeDigest := boardDigest(start)
	book, toSlot := validateMove(db, from, to)
	afterDigest := boardDigest(applyMove(start, Move{From: from, To: to, Book: book}))
	script := "BEGIN IMMEDIATE;\n" +
		"UPDATE books SET shelf_id=" + sqlQuote(to) + ", slot=" + strconv.Itoa(toSlot) + " WHERE book_id=" + sqlQuote(book.ID) + ";\n" +
		"INSERT INTO move_history(book_id, from_shelf, to_shelf, from_slot, to_slot, before_digest, after_digest, undone) VALUES (" +
		sqlQuote(book.ID) + "," + sqlQuote(from) + "," + sqlQuote(to) + "," + strconv.Itoa(book.Slot) + "," + strconv.Itoa(toSlot) + "," + sqlQuote(beforeDigest) + "," + sqlQuote(afterDigest) + ",0);\n" +
		"COMMIT;"
	runSQL(db, script)
	fmt.Printf("OK moved %s from %s to %s\n", book.ID, from, to)
}

func commandUndo(args []string) {
	flags := parseFlags(args)
	db := requireFlag(flags, "db")
	out := runSQL(db, "SELECT id, book_id, from_shelf, to_shelf, from_slot, to_slot, after_digest FROM move_history WHERE undone=0 ORDER BY id DESC LIMIT 1;")
	rows := splitRows(out)
	if len(rows) == 0 {
		die("no move to undo")
	}
	parts := strings.Split(rows[0], "|")
	id, bookID, fromShelf, fromSlot, afterDigest := parts[0], parts[1], parts[2], parts[4], parts[6]
	if boardDigest(loadBoard(db)) != afterDigest {
		die("history is stale")
	}
	script := "BEGIN IMMEDIATE;\n" +
		"UPDATE books SET shelf_id=" + sqlQuote(fromShelf) + ", slot=" + fromSlot + " WHERE book_id=" + sqlQuote(bookID) + ";\n" +
		"UPDATE move_history SET undone=1 WHERE id=" + id + ";\n" +
		"COMMIT;"
	runSQL(db, script)
	fmt.Printf("OK undone %s\n", bookID)
}

func loadBoard(db string) Board {
	b := Board{Books: map[string]Book{}}
	out := runSQL(db, "SELECT shelf_id, position, capacity, required_genre, sort_mode FROM shelves ORDER BY position ASC, shelf_id ASC;")
	for _, row := range splitRows(out) {
		parts := strings.Split(row, "|")
		b.Shelves = append(b.Shelves, Shelf{ID: parts[0], Position: atoi(parts[1]), Capacity: atoi(parts[2]), Genre: parts[3], Sort: strings.ToUpper(parts[4])})
	}
	bout := runSQL(db, "SELECT book_id, title, genre, sort_key, shelf_id, slot FROM books ORDER BY book_id ASC;")
	for _, row := range splitRows(bout) {
		parts := strings.Split(row, "|")
		book := Book{ID: parts[0], Title: parts[1], Genre: parts[2], SortKey: atoi(parts[3]), Shelf: parts[4], Slot: atoi(parts[5])}
		b.Books[book.ID] = book
	}
	eout := runSQL(db, "SELECT e.from_shelf, e.to_shelf FROM edges e JOIN shelves sf ON sf.shelf_id=e.from_shelf JOIN shelves st ON st.shelf_id=e.to_shelf ORDER BY sf.position ASC, e.from_shelf ASC, st.position ASC, e.to_shelf ASC;")
	for _, row := range splitRows(eout) {
		parts := strings.Split(row, "|")
		b.Edges = append(b.Edges, Edge{From: parts[0], To: parts[1]})
	}
	return b
}

func shelfMap(b Board) map[string]Shelf {
	m := map[string]Shelf{}
	for _, shelf := range b.Shelves {
		m[shelf.ID] = shelf
	}
	return m
}

func booksOnShelf(b Board, shelf string) []Book {
	books := []Book{}
	for _, book := range b.Books {
		if book.Shelf == shelf {
			books = append(books, book)
		}
	}
	sort.Slice(books, func(i, j int) bool {
		if books[i].Slot == books[j].Slot {
			return books[i].ID < books[j].ID
		}
		return books[i].Slot < books[j].Slot
	})
	return books
}

func boardShelfValid(b Board, shelf Shelf, finalCheck bool) bool {
	books := booksOnShelf(b, shelf.ID)
	if len(books) > shelf.Capacity {
		return false
	}
	if finalCheck && shelf.Genre == "ANY" && len(books) > 0 {
		return false
	}
	for i, book := range books {
		if shelf.Genre != "ANY" && book.Genre != shelf.Genre {
			return false
		}
		if i > 0 {
			prev := books[i-1]
			if shelf.Sort == "ASC" && prev.SortKey > book.SortKey {
				return false
			}
			if shelf.Sort == "DESC" && prev.SortKey < book.SortKey {
				return false
			}
		}
	}
	return true
}

func boardWin(b Board) bool {
	for _, shelf := range b.Shelves {
		if !boardShelfValid(b, shelf, true) {
			return false
		}
	}
	return true
}

type HistoryRow struct {
	ID           int    `json:"id"`
	BookID       string `json:"book_id"`
	FromShelf    string `json:"from_shelf"`
	ToShelf      string `json:"to_shelf"`
	FromSlot     int    `json:"from_slot"`
	ToSlot       int    `json:"to_slot"`
	BeforeDigest string `json:"before_digest"`
	AfterDigest  string `json:"after_digest"`
	Undone       int    `json:"undone"`
}

type AuditReport struct {
	CurrentDigest     string `json:"current_digest"`
	ReplayedDigest    string `json:"replayed_digest"`
	HistoryCount      int    `json:"history_count"`
	ActiveCount       int    `json:"active_count"`
	UndoneCount       int    `json:"undone_count"`
	Valid             bool   `json:"valid"`
	FirstBadHistoryID *int   `json:"first_bad_history_id"`
}

func initializeRuntimeDB(db, seed, level string, includeHistory bool) {
	_ = os.Remove(db)
	if err := os.MkdirAll(filepath.Dir(db), 0o755); err != nil {
		die(err.Error())
	}
	stmts := []string{
		"ATTACH DATABASE " + sqlQuote(seed) + " AS seed;",
		"CREATE TABLE meta(level_id TEXT PRIMARY KEY);",
		"CREATE TABLE shelves(shelf_id TEXT PRIMARY KEY, position INTEGER NOT NULL, capacity INTEGER NOT NULL, required_genre TEXT NOT NULL, sort_mode TEXT NOT NULL);",
		"CREATE TABLE books(book_id TEXT PRIMARY KEY, title TEXT NOT NULL, genre TEXT NOT NULL, sort_key INTEGER NOT NULL, shelf_id TEXT NOT NULL, slot INTEGER NOT NULL);",
		"CREATE TABLE edges(from_shelf TEXT NOT NULL, to_shelf TEXT NOT NULL, PRIMARY KEY(from_shelf, to_shelf));",
	}
	if includeHistory {
		stmts = append(stmts, "CREATE TABLE move_history(id INTEGER PRIMARY KEY AUTOINCREMENT, book_id TEXT NOT NULL, from_shelf TEXT NOT NULL, to_shelf TEXT NOT NULL, from_slot INTEGER NOT NULL, to_slot INTEGER NOT NULL, before_digest TEXT NOT NULL, after_digest TEXT NOT NULL, undone INTEGER NOT NULL DEFAULT 0);", "CREATE TABLE plan_runs(plan_id TEXT PRIMARY KEY, start_digest TEXT NOT NULL, final_digest TEXT NOT NULL, move_count INTEGER NOT NULL);", "CREATE TABLE plan_steps(plan_id TEXT NOT NULL, step_index INTEGER NOT NULL, history_id INTEGER NOT NULL, after_digest TEXT NOT NULL, PRIMARY KEY(plan_id, step_index), UNIQUE(plan_id, history_id));", "CREATE TABLE batch_runs(batch_id TEXT PRIMARY KEY, start_digest TEXT NOT NULL, final_digest TEXT NOT NULL, step_count INTEGER NOT NULL);", "CREATE TABLE batch_steps(batch_id TEXT NOT NULL, step_index INTEGER NOT NULL, operation_id TEXT NOT NULL, history_id INTEGER NOT NULL, after_digest TEXT NOT NULL, PRIMARY KEY(batch_id, step_index), UNIQUE(batch_id, operation_id));")
	}
	stmts = append(stmts,
		"INSERT INTO meta VALUES ("+sqlQuote(level)+");",
		"INSERT INTO shelves SELECT shelf_id, position, capacity, required_genre, UPPER(sort_mode) FROM seed.seed_shelves WHERE level_id="+sqlQuote(level)+";",
		"INSERT INTO books SELECT book_id, title, genre, sort_key, shelf_id, slot FROM seed.seed_books WHERE level_id="+sqlQuote(level)+";",
		"INSERT INTO edges SELECT from_shelf, to_shelf FROM seed.seed_edges WHERE level_id="+sqlQuote(level)+";",
	)
	runSQL(db, strings.Join(stmts, "\n"))
}

func commandAudit(args []string) {
	flags := parseFlags(args)
	db := requireFlag(flags, "db")
	seed := requireFlag(flags, "seed-db")
	level := requireFlag(flags, "level")
	temp := filepath.Join(os.TempDir(), "booksort-audit-"+strconv.Itoa(os.Getpid())+".db")
	initializeRuntimeDB(temp, seed, level, false)
	defer os.Remove(temp)

	report := AuditReport{CurrentDigest: boardDigest(loadBoard(db)), Valid: true}
	out := runSQL(db, "SELECT id, book_id, from_shelf, to_shelf, from_slot, to_slot, before_digest, after_digest, undone FROM move_history ORDER BY id ASC;")
	for _, row := range splitRows(out) {
		report.HistoryCount++
		parts := strings.Split(row, "|")
		id := atoi(parts[0])
		bookID, fromShelf, toShelf := parts[1], parts[2], parts[3]
		fromSlot, toSlot := atoi(parts[4]), atoi(parts[5])
		beforeDigest, afterDigest := parts[6], parts[7]
		undone := atoi(parts[8])
		if undone == 1 {
			report.UndoneCount++
		} else {
			report.ActiveCount++
		}
		if report.Valid && boardDigest(loadBoard(temp)) != beforeDigest {
			bad := id
			report.Valid = false
			report.FirstBadHistoryID = &bad
		}
		if report.Valid {
			runSQL(temp, "UPDATE books SET shelf_id="+sqlQuote(toShelf)+", slot="+strconv.Itoa(toSlot)+" WHERE book_id="+sqlQuote(bookID)+";")
			if boardDigest(loadBoard(temp)) != afterDigest {
				bad := id
				report.Valid = false
				report.FirstBadHistoryID = &bad
			}
		}
		if undone == 1 {
			runSQL(temp, "UPDATE books SET shelf_id="+sqlQuote(fromShelf)+", slot="+strconv.Itoa(fromSlot)+" WHERE book_id="+sqlQuote(bookID)+";")
		}
	}
	report.ReplayedDigest = boardDigest(loadBoard(temp))
	if report.Valid && report.CurrentDigest != report.ReplayedDigest {
		bad := 0
		report.Valid = false
		report.FirstBadHistoryID = &bad
	}
	encoded, err := json.Marshal(report)
	if err != nil {
		die(err.Error())
	}
	fmt.Println(string(encoded))
}

func commandHistory(args []string) {
	flags := parseFlags(args)
	db := requireFlag(flags, "db")
	out := runSQL(db, "SELECT id, book_id, from_shelf, to_shelf, from_slot, to_slot, before_digest, after_digest, undone FROM move_history ORDER BY id ASC;")
	rows := []HistoryRow{}
	for _, row := range splitRows(out) {
		parts := strings.Split(row, "|")
		rows = append(rows, HistoryRow{ID: atoi(parts[0]), BookID: parts[1], FromShelf: parts[2], ToShelf: parts[3], FromSlot: atoi(parts[4]), ToSlot: atoi(parts[5]), BeforeDigest: parts[6], AfterDigest: parts[7], Undone: atoi(parts[8])})
	}
	encoded, err := json.Marshal(rows)
	if err != nil {
		die(err.Error())
	}
	fmt.Println(string(encoded))
}

func commandStatus(args []string) {
	flags := parseFlags(args)
	db := requireFlag(flags, "db")
	if boardWin(loadBoard(db)) {
		fmt.Println("WIN")
	} else {
		fmt.Println("IN_PROGRESS")
	}
}

func legalMoves(b Board) []Move {
	shelves := shelfMap(b)
	moves := []Move{}
	for _, edge := range b.Edges {
		target, ok := shelves[edge.To]
		if !ok {
			continue
		}
		sourceBooks := booksOnShelf(b, edge.From)
		if len(sourceBooks) == 0 {
			continue
		}
		book := sourceBooks[len(sourceBooks)-1]
		targetBooks := booksOnShelf(b, edge.To)
		if len(targetBooks) >= target.Capacity {
			continue
		}
		if target.Genre != "ANY" && book.Genre != target.Genre {
			continue
		}
		candidate := book
		candidate.Shelf = edge.To
		candidate.Slot = 0
		if len(targetBooks) > 0 {
			candidate.Slot = targetBooks[len(targetBooks)-1].Slot + 1
		}
		merged := append(append([]Book{}, targetBooks...), candidate)
		okOrder := true
		for i := 1; i < len(merged); i++ {
			if target.Sort == "ASC" && merged[i-1].SortKey > merged[i].SortKey {
				okOrder = false
			}
			if target.Sort == "DESC" && merged[i-1].SortKey < merged[i].SortKey {
				okOrder = false
			}
		}
		if okOrder {
			moves = append(moves, Move{From: edge.From, To: edge.To, Book: book})
		}
	}
	return moves
}

func applyMove(b Board, m Move) Board {
	next := Board{Shelves: append([]Shelf{}, b.Shelves...), Edges: append([]Edge{}, b.Edges...), Books: map[string]Book{}}
	for id, book := range b.Books {
		next.Books[id] = book
	}
	targetBooks := booksOnShelf(b, m.To)
	toSlot := 0
	if len(targetBooks) > 0 {
		toSlot = targetBooks[len(targetBooks)-1].Slot + 1
	}
	moved := next.Books[m.Book.ID]
	moved.Shelf = m.To
	moved.Slot = toSlot
	next.Books[m.Book.ID] = moved
	return next
}

func boardKey(b Board) string {
	ids := make([]string, 0, len(b.Books))
	for id := range b.Books {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	parts := make([]string, 0, len(ids))
	for _, id := range ids {
		book := b.Books[id]
		parts = append(parts, id+"@"+book.Shelf+":"+strconv.Itoa(book.Slot))
	}
	return strings.Join(parts, ";")
}

func boardDigest(b Board) string {
	shelvemap := shelfMap(b)
	var parts []string
	parts = append(parts, "SHELVES")
	for _, shelf := range b.Shelves {
		parts = append(parts, shelf.ID+"|"+strconv.Itoa(shelf.Position)+"|"+strconv.Itoa(shelf.Capacity)+"|"+shelf.Genre+"|"+shelf.Sort)
	}
	parts = append(parts, "BOOKS")
	books := make([]Book, 0, len(b.Books))
	for _, book := range b.Books {
		books = append(books, book)
	}
	sort.Slice(books, func(i, j int) bool {
		si, sj := shelvemap[books[i].Shelf], shelvemap[books[j].Shelf]
		if si.Position != sj.Position {
			return si.Position < sj.Position
		}
		if books[i].Shelf != books[j].Shelf {
			return books[i].Shelf < books[j].Shelf
		}
		if books[i].Slot != books[j].Slot {
			return books[i].Slot < books[j].Slot
		}
		return books[i].ID < books[j].ID
	})
	for _, book := range books {
		parts = append(parts, book.ID+"|"+book.Title+"|"+book.Genre+"|"+strconv.Itoa(book.SortKey)+"|"+book.Shelf+"|"+strconv.Itoa(book.Slot))
	}
	parts = append(parts, "EDGES")
	for _, edge := range b.Edges {
		parts = append(parts, edge.From+"|"+edge.To)
	}
	sum := sha256.Sum256([]byte(strings.Join(parts, "\n") + "\n"))
	return hex.EncodeToString(sum[:])
}

func printMove(m Move) {
	fmt.Printf("MOVE %s %s %s\n", m.From, m.To, m.Book.ID)
}

func commandHint(args []string) {
	flags := parseFlags(args)
	db := requireFlag(flags, "db")
	moves := legalMoves(loadBoard(db))
	if len(moves) == 0 {
		fmt.Println("NO_MOVE")
		return
	}
	printMove(moves[0])
}

func commandSolve(args []string) {
	flags := parseFlags(args)
	db := requireFlag(flags, "db")
	maxDepth := optionalInt(flags, "max-depth", 8)
	start := loadBoard(db)
	if boardWin(start) {
		fmt.Println("ALREADY_SOLVED")
		return
	}
	type Node struct {
		Board Board
		Plan  []Move
	}
	queue := []Node{{Board: start}}
	seen := map[string]bool{boardKey(start): true}
	for len(queue) > 0 {
		node := queue[0]
		queue = queue[1:]
		if len(node.Plan) >= maxDepth {
			continue
		}
		for _, move := range legalMoves(node.Board) {
			nb := applyMove(node.Board, move)
			key := boardKey(nb)
			if seen[key] {
				continue
			}
			seen[key] = true
			plan := append(append([]Move{}, node.Plan...), move)
			if boardWin(nb) {
				for _, step := range plan {
					printMove(step)
				}
				return
			}
			queue = append(queue, Node{Board: nb, Plan: plan})
		}
	}
	fmt.Println("NO_SOLUTION")
}

type PlanMove struct {
	From   string `json:"from"`
	To     string `json:"to"`
	BookID string `json:"book_id"`
}

type PlanFile struct {
	ExpectedStartDigest string     `json:"expected_start_digest"`
	ExpectedFinalDigest string     `json:"expected_final_digest"`
	Moves               []PlanMove `json:"moves"`
}

type PlanReport struct {
	PlanID      string `json:"plan_id"`
	StartDigest string `json:"start_digest"`
	FinalDigest string `json:"final_digest"`
	MoveCount   int    `json:"move_count"`
}

func isLowerHex64(value string) bool {
	if len(value) != 64 {
		return false
	}
	for _, ch := range value {
		if !((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f')) {
			return false
		}
	}
	return true
}

func planID(plan PlanFile) string {
	var b strings.Builder
	b.WriteString(plan.ExpectedStartDigest)
	b.WriteByte('\n')
	b.WriteString(plan.ExpectedFinalDigest)
	b.WriteByte('\n')
	for _, m := range plan.Moves {
		b.WriteString(m.From)
		b.WriteByte('|')
		b.WriteString(m.To)
		b.WriteByte('|')
		b.WriteString(m.BookID)
		b.WriteByte('\n')
	}
	sum := sha256.Sum256([]byte(b.String()))
	return hex.EncodeToString(sum[:])
}

func findLegalMove(b Board, from, to, bookID string) (Move, error) {
	if from == to {
		return Move{}, fmt.Errorf("source and target shelves must differ")
	}
	sourceBooks := booksOnShelf(b, from)
	if len(sourceBooks) == 0 {
		return Move{}, fmt.Errorf("source shelf is empty")
	}
	top := sourceBooks[len(sourceBooks)-1]
	if top.ID != bookID {
		return Move{}, fmt.Errorf("book_id is not the source top book")
	}
	for _, m := range legalMoves(b) {
		if m.From == from && m.To == to && m.Book.ID == bookID {
			return m, nil
		}
	}
	return Move{}, fmt.Errorf("move is not legal")
}

func commandApplyPlan(args []string) {
	flags := parseFlags(args)
	db := requireFlag(flags, "db")
	file := requireFlag(flags, "file")
	raw, err := os.ReadFile(file)
	if err != nil {
		die(err.Error())
	}
	var plan PlanFile
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&plan); err != nil {
		die("invalid plan JSON")
	}
	if err := dec.Decode(&struct{}{}); err != io.EOF {
		die("invalid plan JSON")
	}
	if len(plan.Moves) == 0 || !isLowerHex64(plan.ExpectedStartDigest) || !isLowerHex64(plan.ExpectedFinalDigest) {
		die("invalid plan contract")
	}
	start := loadBoard(db)
	startDigest := boardDigest(start)
	if startDigest != plan.ExpectedStartDigest {
		die("plan start digest mismatch")
	}
	current := start
	type applied struct {
		Move   Move
		Before string
		After  string
		ToSlot int
	}
	steps := make([]applied, 0, len(plan.Moves))
	for _, requested := range plan.Moves {
		before := boardDigest(current)
		move, err := findLegalMove(current, requested.From, requested.To, requested.BookID)
		if err != nil {
			die(err.Error())
		}
		next := applyMove(current, move)
		moved := next.Books[requested.BookID]
		after := boardDigest(next)
		steps = append(steps, applied{Move: move, Before: before, After: after, ToSlot: moved.Slot})
		current = next
	}
	finalDigest := boardDigest(current)
	if finalDigest != plan.ExpectedFinalDigest {
		die("plan final digest mismatch")
	}
	id := planID(plan)
	var sql strings.Builder
	sql.WriteString("BEGIN IMMEDIATE;\n")
	sql.WriteString("INSERT INTO plan_runs(plan_id,start_digest,final_digest,move_count) VALUES (" + sqlQuote(id) + "," + sqlQuote(startDigest) + "," + sqlQuote(finalDigest) + "," + strconv.Itoa(len(steps)) + ");\n")
	for i, step := range steps {
		sql.WriteString("UPDATE books SET shelf_id=" + sqlQuote(step.Move.To) + ", slot=" + strconv.Itoa(step.ToSlot) + " WHERE book_id=" + sqlQuote(step.Move.Book.ID) + ";\n")
		sql.WriteString("INSERT INTO move_history(book_id, from_shelf, to_shelf, from_slot, to_slot, before_digest, after_digest, undone) VALUES (" + sqlQuote(step.Move.Book.ID) + "," + sqlQuote(step.Move.From) + "," + sqlQuote(step.Move.To) + "," + strconv.Itoa(step.Move.Book.Slot) + "," + strconv.Itoa(step.ToSlot) + "," + sqlQuote(step.Before) + "," + sqlQuote(step.After) + ",0);\n")
		sql.WriteString("INSERT INTO plan_steps(plan_id,step_index,history_id,after_digest) VALUES (" + sqlQuote(id) + "," + strconv.Itoa(i) + ",last_insert_rowid()," + sqlQuote(step.After) + ");\n")
	}
	sql.WriteString("COMMIT;")
	runSQL(db, sql.String())
	encoded, err := json.Marshal(PlanReport{PlanID: id, StartDigest: startDigest, FinalDigest: finalDigest, MoveCount: len(steps)})
	if err != nil {
		die(err.Error())
	}
	fmt.Println(string(encoded))
}


type BatchOperation struct {
	ID                  string   `json:"id"`
	From                string   `json:"from"`
	To                  string   `json:"to"`
	BookID              string   `json:"book_id"`
	ExpectedAfterDigest string   `json:"expected_after_digest"`
	DependsOn           []string `json:"depends_on"`
}

type BatchFile struct {
	ExpectedStartDigest string           `json:"expected_start_digest"`
	ExpectedFinalDigest string           `json:"expected_final_digest"`
	Operations          []BatchOperation `json:"operations"`
}

type BatchReport struct {
	BatchID      string   `json:"batch_id"`
	StartDigest  string   `json:"start_digest"`
	FinalDigest  string   `json:"final_digest"`
	StepCount    int      `json:"step_count"`
	ExecutionIDs []string `json:"execution_ids"`
}

func validOperationID(value string) bool {
	if value == "" {
		return false
	}
	for _, ch := range value {
		if !((ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9') || ch == '-' || ch == '_') {
			return false
		}
	}
	return true
}

func batchID(batch BatchFile, execution []BatchOperation) string {
	var b strings.Builder
	b.WriteString(batch.ExpectedStartDigest)
	b.WriteByte('\n')
	b.WriteString(batch.ExpectedFinalDigest)
	b.WriteByte('\n')
	for _, op := range execution {
		deps := append([]string(nil), op.DependsOn...)
		sort.Strings(deps)
		b.WriteString(op.ID)
		b.WriteByte('|')
		b.WriteString(op.From)
		b.WriteByte('|')
		b.WriteString(op.To)
		b.WriteByte('|')
		b.WriteString(op.BookID)
		b.WriteByte('|')
		b.WriteString(op.ExpectedAfterDigest)
		b.WriteByte('|')
		b.WriteString(strings.Join(deps, ","))
		b.WriteByte('\n')
	}
	sum := sha256.Sum256([]byte(b.String()))
	return hex.EncodeToString(sum[:])
}

func orderBatchOperations(ops []BatchOperation) ([]BatchOperation, error) {
	byID := make(map[string]BatchOperation, len(ops))
	for _, op := range ops {
		if !validOperationID(op.ID) || !isLowerHex64(op.ExpectedAfterDigest) {
			return nil, fmt.Errorf("invalid batch operation")
		}
		if _, exists := byID[op.ID]; exists {
			return nil, fmt.Errorf("duplicate operation id")
		}
		seenDeps := map[string]bool{}
		for _, dep := range op.DependsOn {
			if dep == op.ID || seenDeps[dep] {
				return nil, fmt.Errorf("invalid dependency list")
			}
			seenDeps[dep] = true
		}
		byID[op.ID] = op
	}
	for _, op := range ops {
		for _, dep := range op.DependsOn {
			if _, ok := byID[dep]; !ok {
				return nil, fmt.Errorf("unknown dependency")
			}
		}
	}
	done := map[string]bool{}
	ordered := make([]BatchOperation, 0, len(ops))
	for len(ordered) < len(ops) {
		ready := make([]string, 0)
		for id, op := range byID {
			if done[id] {
				continue
			}
			ok := true
			for _, dep := range op.DependsOn {
				if !done[dep] {
					ok = false
					break
				}
			}
			if ok {
				ready = append(ready, id)
			}
		}
		if len(ready) == 0 {
			return nil, fmt.Errorf("dependency cycle")
		}
		sort.Strings(ready)
		id := ready[0]
		ordered = append(ordered, byID[id])
		done[id] = true
	}
	return ordered, nil
}

func commandApplyBatch(args []string) {
	flags := parseFlags(args)
	db := requireFlag(flags, "db")
	file := requireFlag(flags, "file")
	raw, err := os.ReadFile(file)
	if err != nil {
		die(err.Error())
	}
	var batch BatchFile
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&batch); err != nil {
		die("invalid batch JSON")
	}
	if err := dec.Decode(&struct{}{}); err != io.EOF {
		die("invalid batch JSON")
	}
	if len(batch.Operations) == 0 || !isLowerHex64(batch.ExpectedStartDigest) || !isLowerHex64(batch.ExpectedFinalDigest) {
		die("invalid batch contract")
	}
	execution, err := orderBatchOperations(batch.Operations)
	if err != nil {
		die(err.Error())
	}
	start := loadBoard(db)
	startDigest := boardDigest(start)
	if startDigest != batch.ExpectedStartDigest {
		die("batch start digest mismatch")
	}
	type applied struct {
		Operation BatchOperation
		Move      Move
		Before    string
		After     string
		ToSlot    int
	}
	current := start
	steps := make([]applied, 0, len(execution))
	for _, op := range execution {
		before := boardDigest(current)
		move, err := findLegalMove(current, op.From, op.To, op.BookID)
		if err != nil {
			die("operation " + op.ID + ": " + err.Error())
		}
		next := applyMove(current, move)
		after := boardDigest(next)
		if after != op.ExpectedAfterDigest {
			die("operation " + op.ID + ": after digest mismatch")
		}
		steps = append(steps, applied{Operation: op, Move: move, Before: before, After: after, ToSlot: next.Books[op.BookID].Slot})
		current = next
	}
	finalDigest := boardDigest(current)
	if finalDigest != batch.ExpectedFinalDigest {
		die("batch final digest mismatch")
	}
	id := batchID(batch, execution)
	var sql strings.Builder
	sql.WriteString("BEGIN IMMEDIATE;\n")
	sql.WriteString("INSERT INTO batch_runs(batch_id,start_digest,final_digest,step_count) VALUES (" + sqlQuote(id) + "," + sqlQuote(startDigest) + "," + sqlQuote(finalDigest) + "," + strconv.Itoa(len(steps)) + ");\n")
	for i, step := range steps {
		sql.WriteString("UPDATE books SET shelf_id=" + sqlQuote(step.Move.To) + ", slot=" + strconv.Itoa(step.ToSlot) + " WHERE book_id=" + sqlQuote(step.Move.Book.ID) + ";\n")
		sql.WriteString("INSERT INTO move_history(book_id, from_shelf, to_shelf, from_slot, to_slot, before_digest, after_digest, undone) VALUES (" + sqlQuote(step.Move.Book.ID) + "," + sqlQuote(step.Move.From) + "," + sqlQuote(step.Move.To) + "," + strconv.Itoa(step.Move.Book.Slot) + "," + strconv.Itoa(step.ToSlot) + "," + sqlQuote(step.Before) + "," + sqlQuote(step.After) + ",0);\n")
		sql.WriteString("INSERT INTO batch_steps(batch_id,step_index,operation_id,history_id,after_digest) VALUES (" + sqlQuote(id) + "," + strconv.Itoa(i) + "," + sqlQuote(step.Operation.ID) + ",last_insert_rowid()," + sqlQuote(step.After) + ");\n")
	}
	sql.WriteString("COMMIT;")
	runSQL(db, sql.String())
	ids := make([]string, len(execution))
	for i, op := range execution {
		ids[i] = op.ID
	}
	encoded, err := json.Marshal(BatchReport{BatchID: id, StartDigest: startDigest, FinalDigest: finalDigest, StepCount: len(steps), ExecutionIDs: ids})
	if err != nil {
		die(err.Error())
	}
	fmt.Println(string(encoded))
}


type LedgerReport struct {
	CurrentDigest  string  `json:"current_digest"`
	ReplayedDigest string  `json:"replayed_digest"`
	HistoryRoot    string  `json:"history_root"`
	HistoryCount   int     `json:"history_count"`
	PlanCount      int     `json:"plan_count"`
	BatchCount     int     `json:"batch_count"`
	Valid          bool    `json:"valid"`
	FirstError     *string `json:"first_error"`
}

func ledgerErrorKey(value string) (int, string) {
	if strings.HasPrefix(value, "history:") { return 0, strings.TrimPrefix(value, "history:") }
	if strings.HasPrefix(value, "plan:") { return 1, strings.TrimPrefix(value, "plan:") }
	if strings.HasPrefix(value, "batch:") { return 2, strings.TrimPrefix(value, "batch:") }
	return 3, value
}

func setLedgerError(report *LedgerReport, value string) {
	replace := report.FirstError == nil
	if report.FirstError != nil {
		oldRank, oldKey := ledgerErrorKey(*report.FirstError)
		newRank, newKey := ledgerErrorKey(value)
		replace = newRank < oldRank || (newRank == oldRank && newKey < oldKey)
	}
	report.Valid = false
	if replace { report.FirstError = &value }
}

func commandVerifyLedger(args []string) {
	flags := parseFlags(args)
	db := requireFlag(flags, "db")
	seed := requireFlag(flags, "seed-db")
	level := requireFlag(flags, "level")
	temp := filepath.Join(os.TempDir(), "booksort-ledger-"+strconv.Itoa(os.Getpid())+".db")
	initializeRuntimeDB(temp, seed, level, false)
	defer os.Remove(temp)

	report := LedgerReport{CurrentDigest: boardDigest(loadBoard(db)), Valid: true}
	rootSeed := sha256.Sum256([]byte("booksort-ledger-v1\n"))
	rootHex := hex.EncodeToString(rootSeed[:])
	historyOut := runSQL(db, "SELECT id, book_id, from_shelf, to_shelf, from_slot, to_slot, before_digest, after_digest, undone FROM move_history ORDER BY id ASC;")
	for _, row := range splitRows(historyOut) {
		report.HistoryCount++
		parts := strings.Split(row, "|")
		if len(parts) != 9 {
			setLedgerError(&report, "history:0")
			continue
		}
		line := strings.Join(parts, "|") + "\n"
		nextRoot := sha256.Sum256([]byte(rootHex + "\n" + line))
		rootHex = hex.EncodeToString(nextRoot[:])
		id := atoi(parts[0])
		bookID, fromShelf, toShelf := parts[1], parts[2], parts[3]
		fromSlot, toSlot := atoi(parts[4]), atoi(parts[5])
		beforeDigest, afterDigest, undone := parts[6], parts[7], atoi(parts[8])
		if report.Valid && boardDigest(loadBoard(temp)) != beforeDigest {
			setLedgerError(&report, "history:"+strconv.Itoa(id))
		}
		if report.Valid {
			book, ok := loadBoard(temp).Books[bookID]
			if !ok || book.Shelf != fromShelf || book.Slot != fromSlot {
				setLedgerError(&report, "history:"+strconv.Itoa(id))
			} else {
				runSQL(temp, "UPDATE books SET shelf_id="+sqlQuote(toShelf)+", slot="+strconv.Itoa(toSlot)+" WHERE book_id="+sqlQuote(bookID)+";")
				if boardDigest(loadBoard(temp)) != afterDigest {
					setLedgerError(&report, "history:"+strconv.Itoa(id))
				}
			}
		}
		if undone == 1 {
			runSQL(temp, "UPDATE books SET shelf_id="+sqlQuote(fromShelf)+", slot="+strconv.Itoa(fromSlot)+" WHERE book_id="+sqlQuote(bookID)+";")
		}
	}
	report.HistoryRoot = rootHex
	report.ReplayedDigest = boardDigest(loadBoard(temp))

	claimed := map[int]string{}
	planOut := runSQL(db, "SELECT plan_id,start_digest,final_digest,move_count FROM plan_runs ORDER BY plan_id;")
	for _, row := range splitRows(planOut) {
		report.PlanCount++
		p := strings.Split(row, "|")
		if len(p) != 4 { setLedgerError(&report, "plan:unknown"); continue }
		id, startDigest, finalDigest, count := p[0], p[1], p[2], atoi(p[3])
		steps := splitRows(runSQL(db, "SELECT ps.step_index,ps.history_id,ps.after_digest,mh.before_digest,mh.after_digest FROM plan_steps ps LEFT JOIN move_history mh ON mh.id=ps.history_id WHERE ps.plan_id="+sqlQuote(id)+" ORDER BY ps.step_index;"))
		bad := len(steps) != count || count < 1
		prev := startDigest
		for i, step := range steps {
			sp := strings.Split(step, "|")
			if len(sp) != 5 || atoi(sp[0]) != i || sp[3] == "" || sp[4] == "" { bad = true; continue }
			hid := atoi(sp[1])
			if owner, exists := claimed[hid]; exists && owner != "plan:"+id { bad = true }
			claimed[hid] = "plan:"+id
			if sp[2] != sp[4] || sp[3] != prev { bad = true }
			prev = sp[4]
		}
		if prev != finalDigest { bad = true }
		if bad { setLedgerError(&report, "plan:"+id) }
	}
	orphanPlans := splitRows(runSQL(db, "SELECT DISTINCT ps.plan_id FROM plan_steps ps LEFT JOIN plan_runs pr ON pr.plan_id=ps.plan_id WHERE pr.plan_id IS NULL ORDER BY ps.plan_id;"))
	if len(orphanPlans) > 0 { setLedgerError(&report, "plan:"+orphanPlans[0]) }

	batchOut := runSQL(db, "SELECT batch_id,start_digest,final_digest,step_count FROM batch_runs ORDER BY batch_id;")
	for _, row := range splitRows(batchOut) {
		report.BatchCount++
		p := strings.Split(row, "|")
		if len(p) != 4 { setLedgerError(&report, "batch:unknown"); continue }
		id, startDigest, finalDigest, count := p[0], p[1], p[2], atoi(p[3])
		steps := splitRows(runSQL(db, "SELECT bs.step_index,bs.history_id,bs.after_digest,mh.before_digest,mh.after_digest FROM batch_steps bs LEFT JOIN move_history mh ON mh.id=bs.history_id WHERE bs.batch_id="+sqlQuote(id)+" ORDER BY bs.step_index;"))
		bad := len(steps) != count || count < 1
		prev := startDigest
		for i, step := range steps {
			sp := strings.Split(step, "|")
			if len(sp) != 5 || atoi(sp[0]) != i || sp[3] == "" || sp[4] == "" { bad = true; continue }
			hid := atoi(sp[1])
			if owner, exists := claimed[hid]; exists && owner != "batch:"+id { bad = true }
			claimed[hid] = "batch:"+id
			if sp[2] != sp[4] || sp[3] != prev { bad = true }
			prev = sp[4]
		}
		if prev != finalDigest { bad = true }
		if bad { setLedgerError(&report, "batch:"+id) }
	}
	orphanBatches := splitRows(runSQL(db, "SELECT DISTINCT bs.batch_id FROM batch_steps bs LEFT JOIN batch_runs br ON br.batch_id=bs.batch_id WHERE br.batch_id IS NULL ORDER BY bs.batch_id;"))
	if len(orphanBatches) > 0 { setLedgerError(&report, "batch:"+orphanBatches[0]) }

	if report.Valid && report.CurrentDigest != report.ReplayedDigest {
		setLedgerError(&report, "board")
	}
	encoded, err := json.Marshal(report)
	if err != nil { die(err.Error()) }
	fmt.Println(string(encoded))
}

func commandRedo(args []string) {
	flags := parseFlags(args)
	db := requireFlag(flags, "db")
	out := runSQL(db, "SELECT id, book_id, from_shelf, to_shelf, from_slot, to_slot, before_digest, after_digest FROM move_history WHERE undone=1 ORDER BY id DESC LIMIT 1;")
	rows := splitRows(out)
	if len(rows) == 0 {
		die("no move to redo")
	}
	parts := strings.Split(rows[0], "|")
	id := parts[0]
	bookID, fromShelf, toShelf := parts[1], parts[2], parts[3]
	fromSlot, toSlot := atoi(parts[4]), atoi(parts[5])
	beforeDigest, afterDigest := parts[6], parts[7]
	current := loadBoard(db)
	if boardDigest(current) != beforeDigest {
		die("history is stale")
	}
	move, err := findLegalMove(current, fromShelf, toShelf, bookID)
	if err != nil || move.Book.Slot != fromSlot {
		die("redo move is no longer legal")
	}
	next := applyMove(current, move)
	if next.Books[bookID].Slot != toSlot || boardDigest(next) != afterDigest {
		die("redo digest mismatch")
	}
	script := "BEGIN IMMEDIATE;\n" +
		"UPDATE books SET shelf_id=" + sqlQuote(toShelf) + ", slot=" + strconv.Itoa(toSlot) + " WHERE book_id=" + sqlQuote(bookID) + ";\n" +
		"UPDATE move_history SET undone=0 WHERE id=" + id + ";\n" +
		"COMMIT;"
	runSQL(db, script)
	fmt.Printf("OK redone %s\n", bookID)
}

func main() {
	if len(os.Args) < 2 {
		usage()
	}
	switch os.Args[1] {
	case "new":
		commandNew(os.Args[2:])
	case "show":
		commandShow(os.Args[2:])
	case "move":
		commandMove(os.Args[2:])
	case "undo":
		commandUndo(os.Args[2:])
	case "redo":
		commandRedo(os.Args[2:])
	case "status":
		commandStatus(os.Args[2:])
	case "history":
		commandHistory(os.Args[2:])
	case "hint":
		commandHint(os.Args[2:])
	case "solve":
		commandSolve(os.Args[2:])
	case "audit":
		commandAudit(os.Args[2:])
	case "apply-plan":
		commandApplyPlan(os.Args[2:])
	case "apply-batch":
		commandApplyBatch(os.Args[2:])
	case "verify-ledger":
		commandVerifyLedger(os.Args[2:])
	default:
		usage()
	}
}

GO

gofmt -w /app/cmd/booksort/main.go
go build -o /app/bin/booksort ./cmd/booksort
