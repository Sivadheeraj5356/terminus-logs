package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"fmt"
	"math"
	"os"
	"sort"
	"strings"

	_ "modernc.org/sqlite"
)

const defaultHMACKey = "support-queue-secret-2026"

func getHMACKey() string {
	if k := os.Getenv("HMAC_SECRET"); k != "" {
		return k
	}
	return defaultHMACKey
}

func openDB(path string) (*sql.DB, error) {
	return sql.Open("sqlite", path)
}

func run(args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("no command given")
	}
	switch args[0] {
	case "init":
		return cmdInit(args[1:])
	case "add-agent":
		return cmdAddAgent(args[1:])
	case "open-ticket":
		return cmdOpenTicket(args[1:])
	case "list-tickets":
		return cmdListTickets(args[1:])
	case "resolve-ticket":
		return cmdResolveTicket(args[1:])
	case "priority-report":
		return cmdPriorityReport(args[1:])
	case "agent-stats":
		return cmdAgentStats(args[1:])
	case "chain-verify":
		return cmdChainVerify(args[1:])
	case "sla-report":
		return cmdSLAReport(args[1:])
	case "priority-stats":
		return cmdPriorityStats(args[1:])
	case "ticket-analytics":
		return cmdTicketAnalytics(args[1:])
	case "workload-balance":
		return cmdWorkloadBalance(args[1:])
	case "dispersion-report":
		return cmdDispersionReport(args[1:])
	case "escalation-audit":
		return cmdEscalationAudit(args[1:])
	case "queue-lint":
		return cmdQueueLint(args[1:])
	default:
		return fmt.Errorf("unknown command: %s", args[0])
	}
}

func initSchema(db *sql.DB) error {
	stmts := []string{
		`CREATE TABLE IF NOT EXISTS agents (
			agent_id TEXT PRIMARY KEY,
			name     TEXT NOT NULL,
			tier     TEXT NOT NULL CHECK(tier IN ('L1','L2','L3'))
		)`,
		`CREATE TABLE IF NOT EXISTS tickets (
			ticket_id         TEXT PRIMARY KEY,
			title             TEXT NOT NULL,
			priority          TEXT NOT NULL CHECK(priority IN ('low','medium','high','critical')),
			status            TEXT NOT NULL DEFAULT 'open',
			assigned_agent_id TEXT,
			opened_at         TEXT NOT NULL DEFAULT (datetime('now'))
		)`,
		`CREATE TABLE IF NOT EXISTS resolutions (
			resolution_id      INTEGER PRIMARY KEY AUTOINCREMENT,
			ticket_id          TEXT NOT NULL,
			agent_id           TEXT NOT NULL,
			resolution_minutes INTEGER NOT NULL,
			sla_met            INTEGER NOT NULL,
			resolved_at        TEXT NOT NULL
		)`,
		`CREATE TABLE IF NOT EXISTS resolution_chain (
			chain_id           INTEGER PRIMARY KEY AUTOINCREMENT,
			ticket_id          TEXT NOT NULL,
			agent_id           TEXT NOT NULL,
			resolution_minutes INTEGER NOT NULL,
			sla_met            TEXT NOT NULL,
			resolved_at        TEXT NOT NULL,
			prev_hash          TEXT NOT NULL,
			current_hash       TEXT NOT NULL
		)`,
	}
	for _, s := range stmts {
		if _, err := db.Exec(s); err != nil {
			return err
		}
	}
	return nil
}

func cmdInit(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: init <db>")
	}
	db, err := openDB(args[0])
	if err != nil {
		return err
	}
	defer db.Close()
	return initSchema(db)
}

func cmdAddAgent(args []string) error {
	if len(args) < 4 {
		return fmt.Errorf("usage: add-agent <db> <agent_id> <name> <tier>")
	}
	dbPath, agentID, name, tier := args[0], args[1], args[2], args[3]
	if tier != "L1" && tier != "L2" && tier != "L3" {
		fmt.Printf("invalid tier: %s\n", tier)
		os.Exit(1)
	}
	db, err := openDB(dbPath)
	if err != nil {
		return err
	}
	defer db.Close()
	_, err = db.Exec(`INSERT INTO agents (agent_id, name, tier) VALUES (?, ?, ?)`, agentID, name, tier)
	if err != nil {
		if strings.Contains(err.Error(), "UNIQUE") {
			fmt.Printf("agent already exists: %s\n", agentID)
			os.Exit(1)
		}
		return err
	}
	fmt.Printf("OK agent=%s\n", agentID)
	return nil
}

func cmdOpenTicket(args []string) error {
	if len(args) < 4 {
		return fmt.Errorf("usage: open-ticket <db> <ticket_id> <title> <priority>")
	}
	dbPath, ticketID, title, priority := args[0], args[1], args[2], args[3]
	valid := map[string]bool{"low": true, "medium": true, "high": true, "critical": true}
	if !valid[priority] {
		fmt.Printf("invalid priority: %s\n", priority)
		os.Exit(1)
	}
	db, err := openDB(dbPath)
	if err != nil {
		return err
	}
	defer db.Close()
	_, err = db.Exec(`INSERT INTO tickets (ticket_id, title, priority) VALUES (?, ?, ?)`, ticketID, title, priority)
	if err != nil {
		if strings.Contains(err.Error(), "UNIQUE") {
			fmt.Printf("ticket already exists: %s\n", ticketID)
			os.Exit(1)
		}
		return err
	}
	fmt.Printf("OK ticket=%s\n", ticketID)
	return nil
}

func cmdListTickets(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: list-tickets <db>")
	}
	db, err := openDB(args[0])
	if err != nil {
		return err
	}
	defer db.Close()
	rows, err := db.Query(`SELECT ticket_id, status, COALESCE(assigned_agent_id, '') FROM tickets ORDER BY CASE priority WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'medium' THEN 2 WHEN 'low' THEN 1 ELSE 0 END DESC, opened_at ASC, ticket_id ASC`)
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var tid, status, agentID string
		if err := rows.Scan(&tid, &status, &agentID); err != nil {
			return err
		}
		fmt.Printf("%s\t%s\t%s\n", tid, status, agentID)
	}
	return rows.Err()
}

func cmdResolveTicket(args []string) error {
	if len(args) < 3 {
		return fmt.Errorf("usage: resolve-ticket <db> <ticket_id> <agent_id>")
	}
	dbPath, ticketID, agentID := args[0], args[1], args[2]

	db, err := openDB(dbPath)
	if err != nil {
		return err
	}
	defer db.Close()

	var priority, status, openedAt string
	err = db.QueryRow(`SELECT priority, status, opened_at FROM tickets WHERE ticket_id=?`, ticketID).Scan(&priority, &status, &openedAt)
	if err == sql.ErrNoRows {
		fmt.Printf("ticket not found: %s\n", ticketID)
		os.Exit(1)
	} else if err != nil {
		return err
	}
	if status != "open" {
		fmt.Printf("ticket already resolved: %s\n", ticketID)
		os.Exit(1)
	}

	var exists int
	db.QueryRow(`SELECT COUNT(*) FROM agents WHERE agent_id=?`, agentID).Scan(&exists)
	if exists == 0 {
		fmt.Printf("agent not found: %s\n", agentID)
		os.Exit(1)
	}

	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	var resolvedAt string
	tx.QueryRow(`SELECT datetime('now')`).Scan(&resolvedAt)

	var resMinutes int64
	tx.QueryRow(`SELECT CAST((strftime('%s', ?) - strftime('%s', ?)) / 60 AS INTEGER)`, resolvedAt, openedAt).Scan(&resMinutes)
	if resMinutes < 0 {
		resMinutes = 0
	}

	slaMet := false
	switch priority {
	case "critical":
		slaMet = resMinutes <= 60
	case "high":
		slaMet = resMinutes <= 240
	case "medium":
		slaMet = resMinutes <= 1440
	case "low":
		slaMet = resMinutes <= 4320
	}

	slaMetStr := "false"
	if slaMet {
		slaMetStr = "true"
	}
	slaMetInt := 0
	if slaMet {
		slaMetInt = 1
	}

	if _, err := tx.Exec(`UPDATE tickets SET status='resolved', assigned_agent_id=? WHERE ticket_id=?`, agentID, ticketID); err != nil {
		return err
	}

	if _, err := tx.Exec(`INSERT INTO resolutions (ticket_id, agent_id, resolution_minutes, sla_met, resolved_at) VALUES (?, ?, ?, ?, ?)`,
		ticketID, agentID, resMinutes, slaMetInt, resolvedAt); err != nil {
		return err
	}

	var prevHash string
	tx.QueryRow(`SELECT current_hash FROM resolution_chain ORDER BY chain_id DESC LIMIT 1`).Scan(&prevHash)

	res, err := tx.Exec(`INSERT INTO resolution_chain (ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, prev_hash, current_hash) VALUES (?, ?, ?, ?, ?, ?, '')`,
		ticketID, agentID, resMinutes, slaMetStr, resolvedAt, prevHash)
	if err != nil {
		return err
	}
	chainID, _ := res.LastInsertId()

	data := fmt.Sprintf("%d|RESOLVE|%s|%s|%d|%s|%s|%s", chainID, ticketID, agentID, resMinutes, slaMetStr, resolvedAt, prevHash)
	mac := hmac.New(sha256.New, []byte(getHMACKey()))
	mac.Write([]byte(data))
	hash := hex.EncodeToString(mac.Sum(nil))

	if _, err := tx.Exec(`UPDATE resolution_chain SET current_hash=? WHERE chain_id=?`, hash, chainID); err != nil {
		return err
	}
	if err := tx.Commit(); err != nil {
		return err
	}

	fmt.Printf("OK resolved ticket=%s sla_met=%s\n", ticketID, slaMetStr)
	return nil
}

func nearestRank(sorted []float64, q float64) float64 {
	n := len(sorted)
	if n == 0 {
		return 0
	}
	rank := int(math.Ceil(q * float64(n)))
	if rank < 1 {
		rank = 1
	}
	if rank > n {
		rank = n
	}
	return sorted[rank-1]
}

func cmdSLAReport(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: sla-report <db>")
	}
	db, err := openDB(args[0])
	if err != nil {
		return err
	}
	defer db.Close()

	var total int
	db.QueryRow(`SELECT COUNT(*) FROM tickets`).Scan(&total)

	rows, err := db.Query(`SELECT resolution_minutes, sla_met FROM resolutions ORDER BY resolution_minutes ASC`)
	if err != nil {
		return err
	}
	defer rows.Close()

	var resMins []float64
	var slaMets int
	for rows.Next() {
		var mins int64
		var slaMetVal int
		rows.Scan(&mins, &slaMetVal)
		resMins = append(resMins, float64(mins))
		if slaMetVal == 1 {
			slaMets++
		}
	}

	n := len(resMins)
	slaMetPct := 0.0
	if n > 0 {
		slaMetPct = float64(slaMets) / float64(n) * 100.0
	}

	sort.Float64s(resMins)
	p50 := nearestRank(resMins, 0.50)
	p75 := nearestRank(resMins, 0.75)
	p95 := nearestRank(resMins, 0.95)

	stdRes := 0.0
	if n > 0 {
		var sum float64
		for _, v := range resMins {
			sum += v
		}
		mean := sum / float64(n)
		var variance float64
		for _, v := range resMins {
			d := v - mean
			variance += d * d
		}
		variance /= float64(n)
		stdRes = math.Sqrt(variance)
	}

	avgRes := 0.0
	if n > 0 {
		var sum float64
		for _, v := range resMins {
			sum += v
		}
		avgRes = sum / float64(n)
	}

	fmt.Printf("total_tickets=%d\n", total)
	fmt.Printf("sla_met_pct=%.4f\n", slaMetPct)
	fmt.Printf("p50_resolution_minutes=%.0f\n", p50)
	fmt.Printf("p75_resolution_minutes=%.0f\n", p75)
	fmt.Printf("p95_resolution_minutes=%.0f\n", p95)
	fmt.Printf("std_resolution=%.4f\n", stdRes)
	fmt.Printf("avg_resolution_minutes=%.4f\n", avgRes)
	return nil
}

func cmdAgentStats(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: agent-stats <db>")
	}
	db, err := openDB(args[0])
	if err != nil {
		return err
	}
	defer db.Close()

	type agentStat struct {
		agentID  string
		tier     string
		resolved int
		avgMin   float64
		breaches int
	}

	rows, err := db.Query(`
		SELECT a.agent_id, a.tier,
			COUNT(r.resolution_id),
			COALESCE(CAST(SUM(r.resolution_minutes) AS REAL) / NULLIF(COUNT(r.resolution_id), 0), 0.0),
			COALESCE(SUM(CASE WHEN r.sla_met = 0 THEN 1 ELSE 0 END), 0)
		FROM agents a
		LEFT JOIN resolutions r ON a.agent_id = r.agent_id
		GROUP BY a.agent_id, a.tier
		ORDER BY COUNT(r.resolution_id) DESC,
			COALESCE(CAST(SUM(r.resolution_minutes) AS REAL) / NULLIF(COUNT(r.resolution_id), 0), 0.0) ASC,
			a.agent_id ASC
	`)
	if err != nil {
		return err
	}
	defer rows.Close()

	var stats []agentStat
	for rows.Next() {
		var s agentStat
		if err := rows.Scan(&s.agentID, &s.tier, &s.resolved, &s.avgMin, &s.breaches); err != nil {
			return err
		}
		stats = append(stats, s)
	}
	if err := rows.Err(); err != nil {
		return err
	}

	for _, s := range stats {
		digest, err := agentQueueDigest(db, s.agentID)
		if err != nil {
			return err
		}
		fmt.Printf("%s tier=%s resolved=%d avg_minutes=%.4f breaches=%d queue_digest=%s\n",
			s.agentID, s.tier, s.resolved, s.avgMin, s.breaches, digest)
	}
	return nil
}

// agentQueueDigest computes an HMAC-SHA256 digest over that agent's own
// resolved ticket_ids (sorted ascending, comma-joined), signed with the same
// HMAC_SECRET-derived key the resolution_chain audit trail uses, and
// truncated to the first 8 hex characters. Unlike resolution_chain (one
// global chain covering every agent), this is a per-entity digest computed
// fresh from resolutions.ticket_id at query time rather than read back from
// any stored column, so an agent that hardcodes or caches the digest instead
// of recomputing it from the current resolved-ticket set will produce a
// stale value the moment tickets are added between commands.
func agentQueueDigest(db *sql.DB, agentID string) (string, error) {
	rows, err := db.Query(`
		SELECT ticket_id FROM resolutions WHERE agent_id = ? ORDER BY ticket_id ASC
	`, agentID)
	if err != nil {
		return "", err
	}
	defer rows.Close()

	var ticketIDs []string
	for rows.Next() {
		var tid string
		if err := rows.Scan(&tid); err != nil {
			return "", err
		}
		ticketIDs = append(ticketIDs, tid)
	}
	if err := rows.Err(); err != nil {
		return "", err
	}

	data := agentID + ":" + strings.Join(ticketIDs, ",")
	mac := hmac.New(sha256.New, []byte(getHMACKey()))
	mac.Write([]byte(data))
	full := hex.EncodeToString(mac.Sum(nil))
	return full[:8], nil
}

func cmdPriorityReport(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: priority-report <db>")
	}
	db, err := openDB(args[0])
	if err != nil {
		return err
	}
	defer db.Close()

	type pStat struct {
		total      int
		breached   int
		metCount   int64
		marginSum  int64
	}

	priorities := []string{"critical", "high", "medium", "low"}
	stats := map[string]*pStat{}
	for _, p := range priorities {
		stats[p] = &pStat{}
	}

	rows, err := db.Query(`
		SELECT t.priority, COUNT(*), SUM(CASE WHEN r.sla_met = 0 THEN 1 ELSE 0 END)
		FROM resolutions r
		JOIN tickets t ON r.ticket_id = t.ticket_id
		GROUP BY t.priority
	`)
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var prio string
		var total, breached int
		rows.Scan(&prio, &total, &breached)
		if s, ok := stats[prio]; ok {
			s.total = total
			s.breached = breached
		}
	}
	if err := rows.Err(); err != nil {
		return err
	}

	// sla_margin_avg only considers SLA-met resolutions (sla_met = 1). The
	// margin for each such resolution is (threshold - resolution_minutes),
	// which is always >= 0 since sla_met = 1 implies resolution_minutes <=
	// threshold. Breached resolutions are excluded entirely, not counted as
	// a zero or negative margin.
	marginRows, err := db.Query(`
		SELECT t.priority, r.resolution_minutes
		FROM resolutions r
		JOIN tickets t ON r.ticket_id = t.ticket_id
		WHERE r.sla_met = 1
	`)
	if err != nil {
		return err
	}
	defer marginRows.Close()
	for marginRows.Next() {
		var prio string
		var resMin int64
		marginRows.Scan(&prio, &resMin)
		if s, ok := stats[prio]; ok {
			threshold := slaThresholdMinutes(prio)
			margin := threshold - resMin
			if margin < 0 {
				margin = 0
			}
			s.marginSum += margin
			s.metCount++
		}
	}
	if err := marginRows.Err(); err != nil {
		return err
	}

	for _, p := range priorities {
		s := stats[p]
		breachRate := halfUpRatio4dp(int64(s.breached), int64(s.total))
		marginAvg := ceilRatio2dp(s.marginSum, s.metCount)
		fmt.Printf("%s total=%d breached=%d breach_rate=%.4f sla_margin_avg=%.2f\n",
			p, s.total, s.breached, breachRate, marginAvg)
	}
	return nil
}

func cmdChainVerify(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: chain-verify <db>")
	}
	db, err := openDB(args[0])
	if err != nil {
		return err
	}
	defer db.Close()

	rows, err := db.Query(`
		SELECT chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, prev_hash, current_hash
		FROM resolution_chain
		ORDER BY chain_id ASC
	`)
	if err != nil {
		return err
	}
	defer rows.Close()

	tampered := false
	var prevHash string

	for rows.Next() {
		var chainID int64
		var resMinutes int64
		var ticketID, agentID, slaMet, resolvedAt, storedPrev, currentHash string
		rows.Scan(&chainID, &ticketID, &agentID, &resMinutes, &slaMet, &resolvedAt, &storedPrev, &currentHash)

		if storedPrev != prevHash {
			fmt.Printf("TAMPERED %d\n", chainID)
			tampered = true
			prevHash = currentHash
			continue
		}

		data := fmt.Sprintf("%d|RESOLVE|%s|%s|%d|%s|%s|%s", chainID, ticketID, agentID, resMinutes, slaMet, resolvedAt, storedPrev)
		mac := hmac.New(sha256.New, []byte(getHMACKey()))
		mac.Write([]byte(data))
		expected := hex.EncodeToString(mac.Sum(nil))

		if expected != currentHash {
			fmt.Printf("TAMPERED %d\n", chainID)
			tampered = true
		}
		prevHash = currentHash
	}
	if err := rows.Err(); err != nil {
		return err
	}

	if tampered {
		os.Exit(1)
	}
	fmt.Println("OK")
	return nil
}

// halfUpRatio4dp performs genuine HALF_UP (round-half-away-from-zero) rounding
// of numerator/denominator to 4 decimal places, using pure integer arithmetic
// so there is no floating-point tie-breaking ambiguity. A tie (remainder exactly
// half the denominator) always rounds up, unlike round-half-to-even/"banker's"
// rounding which %.4f formatting of a raw float64 can silently fall back to.
func halfUpRatio4dp(numerator, denominator int64) float64 {
	if denominator == 0 {
		return 0.0
	}
	scaled := numerator * 10000
	q := scaled / denominator
	r := scaled % denominator
	if 2*r >= denominator {
		q++
	}
	return float64(q) / 10000.0
}

func bankersRound2(numerator, denominator int64) int64 {
	q := numerator / denominator
	r := numerator % denominator
	doubled := r * 2
	if doubled > denominator {
		q++
	} else if doubled == denominator {
		if q%2 != 0 {
			q++
		}
	}
	return q
}

// truncateRatio4dpStr truncates numerator/denominator toward zero to 4 decimal
// places using pure integer arithmetic and returns the formatted string
// directly. This is a third, distinct rounding convention alongside
// halfUpRatio4dp (HALF_UP, used by priority-report's breach_rate) and
// bankersRound2 (HALF_EVEN, used by priority-stats' avg_resolution_minutes):
// escalation-audit's ratio field always truncates the dropped digits, it
// never rounds up regardless of what the 5th decimal digit is. For example
// 157/60 = 2.616666... truncates to 2.6166, while HALF_UP on that same value
// would round up to 2.6167.
func truncateRatio4dpStr(numerator, denominator int64) string {
	if denominator == 0 {
		return "0.0000"
	}
	scaled := (numerator * 10000) / denominator
	whole := scaled / 10000
	frac := scaled % 10000
	if frac < 0 {
		frac = -frac
	}
	return fmt.Sprintf("%d.%04d", whole, frac)
}

// ceilRatio2dp performs CEILING rounding (round toward positive infinity) of
// numerator/denominator to 2 decimal places, using pure integer arithmetic.
// This is a fourth distinct rounding convention alongside halfUpRatio4dp
// (HALF_UP, priority-report's breach_rate), bankersRound2 (HALF_EVEN,
// priority-stats' avg_resolution_minutes), and truncateRatio4dpStr
// (truncate-toward-zero, escalation-audit's ratio field): CEILING rounds up
// on ANY nonzero remainder, not only a remainder at or past the halfway
// point. For example 7/8 = 0.875 rounds HALF_UP to 0.88 same as CEILING, but
// 701/800 = 0.87625 rounds HALF_UP to 0.88 while CEILING also gives 0.88 —
// the divergence shows up whenever the true fractional remainder is small
// but nonzero, e.g. 801/1000 = 0.801 rounds HALF_UP to 0.80 (5th-decimal-and
// -beyond digits are 01, below half) but CEILING still rounds up to 0.81
// since any leftover remainder at all pushes the result up.
func ceilRatio2dp(numerator, denominator int64) float64 {
	if denominator == 0 {
		return 0.0
	}
	scaled := numerator * 100
	q := scaled / denominator
	r := scaled % denominator
	if r > 0 {
		q++
	}
	return float64(q) / 100.0
}

func cmdPriorityStats(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: priority-stats <db>")
	}
	db, err := openDB(args[0])
	if err != nil {
		return err
	}
	defer db.Close()

	catRows, err := db.Query(`SELECT DISTINCT t.priority FROM tickets t
		INNER JOIN resolutions r ON t.ticket_id = r.ticket_id
		ORDER BY t.priority ASC`)
	if err != nil {
		return err
	}
	var categories []string
	for catRows.Next() {
		var cat string
		catRows.Scan(&cat)
		categories = append(categories, cat)
	}
	catRows.Close()

	fmt.Println("priority\tresolution_count\tavg_resolution_minutes\tstddev_resolution\tp75_resolution_minutes")

	for _, cat := range categories {
		vRows, err := db.Query(
			`SELECT r.resolution_minutes FROM resolutions r
			INNER JOIN tickets t ON r.ticket_id = t.ticket_id
			WHERE t.priority = ? ORDER BY r.resolution_minutes ASC`, cat)
		if err != nil {
			return err
		}
		var values []int64
		for vRows.Next() {
			var v int64
			vRows.Scan(&v)
			values = append(values, v)
		}
		vRows.Close()

		count := int64(len(values))

		var sumValues int64
		for _, v := range values {
			sumValues += v
		}
		avgScaled := int64(0)
		if count > 0 {
			avgScaled = bankersRound2(sumValues*100, count)
		}
		avgStr := fmt.Sprintf("%.2f", float64(avgScaled)/100.0)

		var stddevStr string
		if count > 0 {
			mean := float64(sumValues) / float64(count)
			variance := 0.0
			for _, v := range values {
				diff := float64(v) - mean
				variance += diff * diff
			}
			variance /= float64(count)
			stddevStr = fmt.Sprintf("%.4f", math.Sqrt(variance))
		} else {
			stddevStr = "0.0000"
		}

		var p75Str string
		if count > 0 {
			rank := int(math.Ceil(0.75 * float64(count)))
			p75Str = fmt.Sprintf("%.4f", float64(values[rank-1]))
		} else {
			p75Str = "0.0000"
		}

		fmt.Printf("%s\t%d\t%s\t%s\t%s\n", cat, count, avgStr, stddevStr, p75Str)
	}
	return nil
}

func cmdTicketAnalytics(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: ticket-analytics <db>")
	}
	db, err := openDB(args[0])
	if err != nil {
		return err
	}
	defer db.Close()

	valRows, err := db.Query(`SELECT resolution_minutes FROM resolutions ORDER BY resolution_minutes ASC`)
	if err != nil {
		return err
	}
	defer valRows.Close()

	var vals []float64
	for valRows.Next() {
		var v int64
		valRows.Scan(&v)
		vals = append(vals, float64(v))
	}
	valRows.Close()

	n := len(vals)
	if n == 0 {
		fmt.Printf("total_resolved=0\n")
		fmt.Printf("p25_resolution_minutes=0\n")
		fmt.Printf("iqr_resolution_minutes=0\n")
		fmt.Printf("sample_std_resolution=0.0000\n")
		fmt.Printf("cv_resolution=0.0000\n")
		return nil
	}

	sort.Float64s(vals)

	p25 := nearestRank(vals, 0.25)
	p75 := nearestRank(vals, 0.75)
	iqr := p75 - p25

	var sum float64
	for _, v := range vals {
		sum += v
	}
	mean := sum / float64(n)

	sampleStd := 0.0
	if n > 1 {
		var variance float64
		for _, v := range vals {
			d := v - mean
			variance += d * d
		}
		variance /= float64(n - 1)
		sampleStd = math.Sqrt(variance)
	}

	cv := 0.0
	if mean != 0 {
		cv = sampleStd / mean * 100
	}

	fmt.Printf("total_resolved=%d\n", n)
	fmt.Printf("p25_resolution_minutes=%.0f\n", p25)
	fmt.Printf("iqr_resolution_minutes=%.0f\n", iqr)
	fmt.Printf("sample_std_resolution=%.4f\n", sampleStd)
	fmt.Printf("cv_resolution=%.4f\n", cv)
	return nil
}

func cmdWorkloadBalance(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: workload-balance <db>")
	}
	db, err := openDB(args[0])
	if err != nil {
		return err
	}
	defer db.Close()

	tierCapacity := map[string]int{
		"L1": 5,
		"L2": 15,
		"L3": 30,
	}

	type agentWorkload struct {
		agentID     string
		tier        string
		openCount   int
		utilization float64
	}

	rows, err := db.Query(`
		SELECT a.agent_id, a.tier,
			COALESCE(COUNT(t.ticket_id), 0)
		FROM agents a
		LEFT JOIN tickets t ON t.assigned_agent_id = a.agent_id AND t.status = 'open'
		GROUP BY a.agent_id, a.tier
	`)
	if err != nil {
		return err
	}
	defer rows.Close()

	var workloads []agentWorkload
	for rows.Next() {
		var w agentWorkload
		if err := rows.Scan(&w.agentID, &w.tier, &w.openCount); err != nil {
			return err
		}
		cap := tierCapacity[w.tier]
		w.utilization = float64(w.openCount) / float64(cap) * 100.0
		workloads = append(workloads, w)
	}
	if err := rows.Err(); err != nil {
		return err
	}

	sort.Slice(workloads, func(i, j int) bool {
		if workloads[i].utilization != workloads[j].utilization {
			return workloads[i].utilization > workloads[j].utilization
		}
		return workloads[i].agentID < workloads[j].agentID
	})

	for _, w := range workloads {
		fmt.Printf("%s tier=%s open=%d utilization=%.4f\n", w.agentID, w.tier, w.openCount, w.utilization)
	}
	return nil
}

func slaThresholdMinutes(priority string) int64 {
	switch priority {
	case "critical":
		return 60
	case "high":
		return 240
	case "medium":
		return 1440
	case "low":
		return 4320
	}
	return 0
}

// cmdDispersionReport computes median (nearest-rank) and median-absolute-deviation
// statistics over resolution_minutes. See /docs/statistics-spec.md: the median must
// reuse the exact nearest-rank formula used for percentiles, not the textbook
// average-of-two-middle-values definition, and MAD reapplies that same formula to
// the sorted absolute deviations before scaling by the 1.4826 consistency constant.
func cmdDispersionReport(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: dispersion-report <db>")
	}
	db, err := openDB(args[0])
	if err != nil {
		return err
	}
	defer db.Close()

	rows, err := db.Query(`SELECT resolution_minutes FROM resolutions`)
	if err != nil {
		return err
	}
	defer rows.Close()

	var vals []float64
	for rows.Next() {
		var v int64
		if err := rows.Scan(&v); err != nil {
			return err
		}
		vals = append(vals, float64(v))
	}
	if err := rows.Err(); err != nil {
		return err
	}

	n := len(vals)
	if n == 0 {
		fmt.Printf("n=0\n")
		fmt.Printf("median_resolution_minutes=0\n")
		fmt.Printf("mad_resolution_minutes=0.0000\n")
		fmt.Printf("mad_normalized=0.0000\n")
		return nil
	}

	sort.Float64s(vals)
	median := nearestRank(vals, 0.50)

	deviations := make([]float64, n)
	for i, v := range vals {
		d := v - median
		if d < 0 {
			d = -d
		}
		deviations[i] = d
	}
	sort.Float64s(deviations)
	mad := nearestRank(deviations, 0.50)
	madNormalized := mad * 1.4826

	fmt.Printf("n=%d\n", n)
	fmt.Printf("median_resolution_minutes=%.0f\n", median)
	fmt.Printf("mad_resolution_minutes=%.4f\n", mad)
	fmt.Printf("mad_normalized=%.4f\n", madNormalized)
	return nil
}

type escalationRow struct {
	ticketID       string
	priority       string
	band           string
	bandRank       int
	elapsedMinutes int64
	threshold      int64
	ratioStr       string
}

// cmdEscalationAudit lists open tickets that have breached escalation severity
// bands relative to their priority's SLA window. It captures "now" exactly once
// and reuses that value for every row, mirroring the single-timestamp discipline
// resolve-ticket must follow for resolved_at. See /docs/API_SPEC.md.
func cmdEscalationAudit(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: escalation-audit <db>")
	}
	db, err := openDB(args[0])
	if err != nil {
		return err
	}
	defer db.Close()

	var now string
	if err := db.QueryRow(`SELECT datetime('now')`).Scan(&now); err != nil {
		return err
	}

	rows, err := db.Query(
		`SELECT ticket_id, priority,
			MAX(0, CAST((strftime('%s', ?) - strftime('%s', opened_at)) / 60 AS INTEGER))
		FROM tickets
		WHERE status = 'open'`, now)
	if err != nil {
		return err
	}
	defer rows.Close()

	var results []escalationRow
	for rows.Next() {
		var ticketID, priority string
		var elapsed int64
		if err := rows.Scan(&ticketID, &priority, &elapsed); err != nil {
			return err
		}
		threshold := slaThresholdMinutes(priority)
		if threshold <= 0 {
			continue
		}
		ratio := float64(elapsed) / float64(threshold)

		var band string
		var bandRank int
		switch {
		case ratio <= 1.0:
			continue // on_track: never printed
		case ratio <= 2.0:
			band, bandRank = "at_risk", 1
		case ratio <= 4.0:
			band, bandRank = "escalated", 2
		default:
			band, bandRank = "critical_escalation", 3
		}

		results = append(results, escalationRow{
			ticketID:       ticketID,
			priority:       priority,
			band:           band,
			bandRank:       bandRank,
			elapsedMinutes: elapsed,
			threshold:      threshold,
			ratioStr:       truncateRatio4dpStr(elapsed, threshold),
		})
	}
	if err := rows.Err(); err != nil {
		return err
	}

	sort.Slice(results, func(i, j int) bool {
		if results[i].bandRank != results[j].bandRank {
			return results[i].bandRank > results[j].bandRank
		}
		if results[i].elapsedMinutes != results[j].elapsedMinutes {
			return results[i].elapsedMinutes > results[j].elapsedMinutes
		}
		return results[i].ticketID < results[j].ticketID
	})

	for _, r := range results {
		fmt.Printf("%s\tpriority=%s\tband=%s\telapsed_minutes=%d\tthreshold=%d\tratio=%s\n",
			r.ticketID, r.priority, r.band, r.elapsedMinutes, r.threshold, r.ratioStr)
	}
	return nil
}

// cmdQueueLint runs six fixed-order domain integrity rules against the
// current database state. Every rule always runs, in the fixed order below
// (not alphabetical, mirroring escalation-audit's fixed severity order
// instead of priority-stats' alphabetical one), and prints one summary line
// per rule plus one indented line per violating identifier. See
// /docs/lint-spec.md for the exact rule definitions and output contract.
func cmdQueueLint(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: queue-lint <db>")
	}
	db, err := openDB(args[0])
	if err != nil {
		return err
	}
	defer db.Close()

	overallPass := true

	printRule := func(name string, violations []string) {
		status := "PASS"
		if len(violations) > 0 {
			status = "FAIL"
			overallPass = false
		}
		fmt.Printf("%s %s violations=%d\n", name, status, len(violations))
		for _, v := range violations {
			fmt.Printf("\t%s\n", v)
		}
	}

	// TIER_CAPACITY: an agent's open+assigned ticket count must not exceed
	// their tier's capacity (same capacities as workload-balance).
	{
		tierCapacity := map[string]int{"L1": 5, "L2": 15, "L3": 30}
		var violations []string
		rows, err := db.Query(`
			SELECT a.agent_id, a.tier, COALESCE(COUNT(t.ticket_id), 0)
			FROM agents a
			LEFT JOIN tickets t ON t.assigned_agent_id = a.agent_id AND t.status = 'open'
			GROUP BY a.agent_id, a.tier
			ORDER BY a.agent_id ASC
		`)
		if err != nil {
			return err
		}
		for rows.Next() {
			var agentID, tier string
			var openCount int
			if err := rows.Scan(&agentID, &tier, &openCount); err != nil {
				rows.Close()
				return err
			}
			if openCount > tierCapacity[tier] {
				violations = append(violations, agentID)
			}
		}
		if err := rows.Err(); err != nil {
			rows.Close()
			return err
		}
		rows.Close()
		printRule("TIER_CAPACITY", violations)
	}

	// STATUS_VALID: every ticket's status must be one of 'open' or
	// 'resolved' (there is no CHECK constraint on status, unlike tier or
	// priority, so this is the only thing that catches a directly
	// tampered/corrupted status value).
	{
		validStatuses := map[string]bool{"open": true, "resolved": true}
		var violations []string
		rows, err := db.Query(`SELECT ticket_id, status FROM tickets ORDER BY ticket_id ASC`)
		if err != nil {
			return err
		}
		for rows.Next() {
			var ticketID, status string
			if err := rows.Scan(&ticketID, &status); err != nil {
				rows.Close()
				return err
			}
			if !validStatuses[status] {
				violations = append(violations, ticketID)
			}
		}
		if err := rows.Err(); err != nil {
			rows.Close()
			return err
		}
		rows.Close()
		printRule("STATUS_VALID", violations)
	}

	// DUPLICATE_RESOLUTION: no ticket_id may appear more than once in
	// resolutions.
	{
		var violations []string
		rows, err := db.Query(`
			SELECT ticket_id FROM resolutions
			GROUP BY ticket_id HAVING COUNT(*) > 1
			ORDER BY ticket_id ASC
		`)
		if err != nil {
			return err
		}
		for rows.Next() {
			var ticketID string
			if err := rows.Scan(&ticketID); err != nil {
				rows.Close()
				return err
			}
			violations = append(violations, ticketID)
		}
		if err := rows.Err(); err != nil {
			rows.Close()
			return err
		}
		rows.Close()
		printRule("DUPLICATE_RESOLUTION", violations)
	}

	// ORPHAN_RESOLUTION: every resolutions row must reference an existing
	// ticket whose status is 'resolved'.
	{
		var violations []string
		rows, err := db.Query(`
			SELECT r.ticket_id
			FROM resolutions r
			LEFT JOIN tickets t ON t.ticket_id = r.ticket_id
			WHERE t.ticket_id IS NULL OR t.status != 'resolved'
			ORDER BY r.ticket_id ASC
		`)
		if err != nil {
			return err
		}
		for rows.Next() {
			var ticketID string
			if err := rows.Scan(&ticketID); err != nil {
				rows.Close()
				return err
			}
			violations = append(violations, ticketID)
		}
		if err := rows.Err(); err != nil {
			rows.Close()
			return err
		}
		rows.Close()
		printRule("ORPHAN_RESOLUTION", violations)
	}

	// SLA_CONSISTENCY: sla_met is recomputed independently from
	// resolution_minutes and the ticket's priority threshold rather than
	// trusted at face value, the same "recompute rather than trust"
	// principle chain-verify applies to the audit chain.
	{
		var violations []string
		rows, err := db.Query(`
			SELECT r.ticket_id, r.resolution_minutes, r.sla_met, t.priority
			FROM resolutions r
			JOIN tickets t ON t.ticket_id = r.ticket_id
			ORDER BY r.ticket_id ASC
		`)
		if err != nil {
			return err
		}
		for rows.Next() {
			var ticketID, priority string
			var resMinutes int64
			var slaMetStored int
			if err := rows.Scan(&ticketID, &resMinutes, &slaMetStored, &priority); err != nil {
				rows.Close()
				return err
			}
			threshold := slaThresholdMinutes(priority)
			expected := resMinutes <= threshold
			actual := slaMetStored != 0
			if expected != actual {
				violations = append(violations, ticketID)
			}
		}
		if err := rows.Err(); err != nil {
			rows.Close()
			return err
		}
		rows.Close()
		printRule("SLA_CONSISTENCY", violations)
	}

	// CHAIN_SEQUENCE: walking resolution_chain in chain_id ASC order with a
	// 1-indexed running counter, every chain_id must equal the counter. This
	// catches any deleted or non-contiguous row anywhere in the chain, not
	// only a deleted head entry (which chain-verify already catches
	// separately via prev_hash linkage).
	{
		var violations []string
		rows, err := db.Query(`SELECT chain_id FROM resolution_chain ORDER BY chain_id ASC`)
		if err != nil {
			return err
		}
		counter := int64(1)
		for rows.Next() {
			var chainID int64
			if err := rows.Scan(&chainID); err != nil {
				rows.Close()
				return err
			}
			if chainID != counter {
				violations = append(violations, fmt.Sprintf("%d", chainID))
			}
			counter++
		}
		if err := rows.Err(); err != nil {
			rows.Close()
			return err
		}
		rows.Close()
		printRule("CHAIN_SEQUENCE", violations)
	}

	overallStatus := "PASS"
	if !overallPass {
		overallStatus = "FAIL"
	}
	fmt.Printf("OVERALL %s\n", overallStatus)
	if !overallPass {
		os.Exit(1)
	}
	return nil
}

