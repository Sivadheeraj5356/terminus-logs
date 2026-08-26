// Keeper for a short series of hidden two-stretch sheaf rounds with a bounded garbled reply.
//
// The keeper is a long-lived job that root starts from the container entrypoint, separate from the
// unprivileged `agent` user that issues the tally commands. It owns the hidden per-round data
// (each round's two secret stretches and the hidden index of the one reply it will garble), which
// are root-owned and unreadable by the agent. It answers a small command grammar over a Unix
// domain endpoint in a root-owned directory (/run/ryebank). A client dials that endpoint but
// cannot read the stretches, the garble indices, the keeper binary, the keeper's environment, or
// the ledger before it is published. There is no network at all, so a filesystem endpoint is the
// only channel.
//
// Each round the keeper holds a hidden pair of stretches over the N numbered sheaves 1..N. A
// stretch is an inclusive run of consecutive sheaves. The two stretches never touch (there is
// always at least one loose sheaf between them), so the binding is genuinely two separate runs of
// bound sheaves, not one. The tally names a handful, a set of distinct sheaf numbers, and the
// keeper replies with ONE count only: how many of the handful's sheaves are bound, i.e. how many
// fall inside either stretch. In exactly ONE reply per round, at a fixed hidden handful index
// baked per round, the keeper returns a garbled count instead of the truth: the count shifted by
// the minimal legal amount (down one if that stays in the structural range 0..handful-size, else
// up one) so the reply is still a well-formed count that is not the truth. Everything else is
// answered honestly. A round is won when the tally submits the exact two-stretch binding with the
// one-shot `bind` command within the per-round handful budget; a wrong binding loses the round
// immediately. When every round has been resolved the keeper publishes a ledger with the per-round
// outcome and handful count, never the stretches or the garble indices, so the grader can confirm
// the outcome without trusting the tally and without any secret leaking.
//
// Implemented on the Go standard library `net` package: a UnixListener with one goroutine per
// connection, guarded by a single mutex so the series state stays consistent across concurrent
// dials.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// The per-round secrets for the whole series. Generated once per session at container start by the
// root secret generator (/opt/keeper/generate.py), which draws the three two-stretch bindings and
// their garble indices from OS randomness constrained to the hard regime by rejection sampling and
// writes the root-only secret file before this keeper reads it. No answer literal ships anywhere in
// the image. That file is root-owned 0400 in a 0700 directory; the agent user cannot read it and no
// command ever prints the stretches.
func secretPath() string {
	if v := os.Getenv("RB_KEEPER_SECRET"); v != "" {
		return v
	}
	return "/opt/keeper/secret.json"
}

func endpointPath() string {
	if v := os.Getenv("RB_KEEPER_ENDPOINT"); v != "" {
		return v
	}
	return "/run/ryebank/ryebank.sock"
}

func ledgerPath() string {
	if v := os.Getenv("RB_KEEPER_LEDGER"); v != "" {
		return v
	}
	return "/run/ryebank/ledger.json"
}

// A stretch is an inclusive sheaf run [Lo,Hi] with 1<=Lo<=Hi<=N.
type stretch struct {
	Lo int `json:"lo"`
	Hi int `json:"hi"`
}

// One baked round: the two secret stretches (always disjoint and non-adjacent, the left one first)
// and garbleAt, the zero-based handful index whose reply this round garbles.
type round struct {
	Stretches []stretch `json:"stretches"`
	GarbleAt  int       `json:"garbleAt"`
}

// spec mirrors secret.json: the number of sheaves N, the per-round handful budget, and the baked
// rounds.
type spec struct {
	N      int     `json:"n"`
	Budget int     `json:"budget"`
	Rounds []round `json:"rounds"`
}

type roundRecord struct {
	Index      int  `json:"index"`
	Won        bool `json:"won"`
	NamesUsed  int  `json:"names_used"`
}

// bound counts how many handful sheaves are bound: how many fall inside either stretch. handful is
// a set of distinct sheaf numbers.
func bound(hand []int, stretches []stretch) int {
	n := 0
	for _, p := range hand {
		for _, c := range stretches {
			if p >= c.Lo && p <= c.Hi {
				n++
				break
			}
		}
	}
	return n
}

// garble returns the single garbled count the keeper emits at a round's baked handful index: the
// truthful count shifted by the minimal legal amount, preferring down-one then up-one so the result
// is deterministic. A handful of m sheaves can truthfully bind anywhere in 0..m, and the shift
// stays inside that range, so the reply is always a well-formed count that is not the truth. A
// handful of at least one sheaf always has a legal shift.
func garble(o, m int) int {
	for _, cand := range []int{o - 1, o + 1} {
		if cand >= 0 && cand <= m && cand != o {
			return cand
		}
	}
	return o
}

type Series struct {
	n         int
	budget    int
	rounds    []round
	idx       int
	namesUsed int
	roundDone bool
	roundWon  bool
	finished  bool
	records   []roundRecord
}

func newSeries(s spec) *Series {
	return &Series{n: s.N, budget: s.Budget, rounds: s.Rounds}
}

func (se *Series) recordRound() {
	se.records = append(se.records, roundRecord{Index: se.idx, Won: se.roundWon, NamesUsed: se.namesUsed})
	if se.idx+1 >= len(se.rounds) {
		se.finished = true
		se.publish()
	}
}

func (se *Series) publish() {
	redacted := map[string]interface{}{
		"n":        se.n,
		"budget":   se.budget,
		"finished": true,
		"rounds":   se.records,
	}
	p := ledgerPath()
	_ = os.MkdirAll(filepath.Dir(p), 0o755)
	data, err := json.Marshal(redacted)
	if err != nil {
		return
	}
	tmp := p + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return
	}
	_ = os.Rename(tmp, p)
}

func (se *Series) handle(line string) string {
	parts := strings.Fields(strings.TrimSpace(line))
	if len(parts) == 0 {
		return "error empty command"
	}
	cmd := strings.ToLower(parts[0])
	if cmd == "help" {
		return helpText
	}
	if se.finished {
		return "series over: every round is resolved. no further commands accepted."
	}
	switch cmd {
	case "read", "status":
		return se.status()
	case "name":
		return se.name(parts[1:])
	case "bind":
		return se.bind(parts[1:])
	case "next", "advance":
		return se.next()
	default:
		return fmt.Sprintf("error unknown command %q. type help for the command list.", cmd)
	}
}

func (se *Series) status() string {
	var stateLine string
	if se.roundDone {
		outcome := "lost"
		if se.roundWon {
			outcome = "won"
		}
		if se.idx+1 < len(se.rounds) {
			stateLine = fmt.Sprintf("round %d of %d %s; type next to begin round %d of %d",
				se.idx+1, len(se.rounds), outcome, se.idx+2, len(se.rounds))
		} else {
			stateLine = fmt.Sprintf("round %d of %d %s; series complete", se.idx+1, len(se.rounds), outcome)
		}
	} else {
		stateLine = "in progress"
	}
	return fmt.Sprintf(
		"round %d of %d\n"+
			"sheaves 1..%d\n"+
			"binding: two disjoint stretches, never touching (at least one loose sheaf between them)\n"+
			"names used %d of budget %d\n"+
			"exactly one of your replies this round is garbled: one count, at a hidden position fixed "+
			"before you name anything and never changed in response to your play, is off by one; every "+
			"other reply is truthful\n"+
			"objective: name handfuls, hear how many are bound, work out the two stretches, and win with "+
			"one bind within the name budget\n"+
			"state: %s",
		se.idx+1, len(se.rounds), se.n, se.namesUsed, se.budget, stateLine)
}

// parseHandful parses a comma-separated list of distinct sheaf numbers in 1..N, leaving out at
// least one sheaf. Returns the sorted distinct list or an error string.
func (se *Series) parseHandful(raw string) ([]int, string) {
	fields := strings.Split(raw, ",")
	seen := map[int]bool{}
	var out []int
	for _, f := range fields {
		f = strings.TrimSpace(f)
		if f == "" {
			return nil, "error a handful is a comma-separated list of sheaf numbers, e.g. name 1,2,3"
		}
		v, err := strconv.Atoi(f)
		if err != nil {
			return nil, fmt.Sprintf("error %q is not a sheaf number", f)
		}
		if v < 1 || v > se.n {
			return nil, fmt.Sprintf("error sheaf %d is out of range; sheaves are 1..%d", v, se.n)
		}
		if seen[v] {
			return nil, "error a handful may not name the same sheaf twice"
		}
		seen[v] = true
		out = append(out, v)
	}
	if len(out) == 0 {
		return nil, "error a handful must name at least one sheaf"
	}
	if len(out) >= se.n {
		return nil, "error a handful must leave out at least one sheaf"
	}
	sort.Ints(out)
	return out, ""
}

func (se *Series) name(args []string) string {
	if se.roundDone {
		return "error this round is over; type next for the following round"
	}
	if len(args) != 1 {
		return "error usage: name <sheaves>, a comma-separated list, e.g. name 1,4,7"
	}
	pts, bad := se.parseHandful(args[0])
	if bad != "" {
		return bad
	}
	if se.namesUsed >= se.budget {
		return "error no names remain this round; submit your answer with bind <lo1-hi1,lo2-hi2>"
	}
	o := bound(pts, se.rounds[se.idx].Stretches)
	if se.namesUsed == se.rounds[se.idx].GarbleAt {
		o = garble(o, len(pts))
	}
	se.namesUsed++
	remaining := se.budget - se.namesUsed
	if remaining > 0 {
		return fmt.Sprintf("bound %d\nnames remaining %d", o, remaining)
	}
	return fmt.Sprintf("bound %d\nno names remain; submit your answer with bind <lo1-hi1,lo2-hi2>", o)
}

// parseBind parses a two-stretch answer "lo1-hi1,lo2-hi2" into a normalised pair of stretches (left
// stretch first). Enforces valid ranges, disjointness, and the non-adjacency the binding always
// obeys, so a well-formed answer is required.
func (se *Series) parseBind(raw string) ([]stretch, string) {
	fields := strings.Split(raw, ",")
	if len(fields) != 2 {
		return nil, "error a bind gives exactly two stretches, e.g. bind 2-4,8-11"
	}
	var stretches []stretch
	for _, f := range fields {
		f = strings.TrimSpace(f)
		lohi := strings.Split(f, "-")
		if len(lohi) != 2 {
			return nil, fmt.Sprintf("error stretch %q must be written lo-hi, e.g. 2-4", f)
		}
		lo, e1 := strconv.Atoi(strings.TrimSpace(lohi[0]))
		hi, e2 := strconv.Atoi(strings.TrimSpace(lohi[1]))
		if e1 != nil || e2 != nil {
			return nil, fmt.Sprintf("error stretch %q must be two sheaf numbers lo-hi", f)
		}
		if lo < 1 || hi > se.n || lo > hi {
			return nil, fmt.Sprintf("error stretch %d-%d is not a valid run within 1..%d", lo, hi, se.n)
		}
		stretches = append(stretches, stretch{Lo: lo, Hi: hi})
	}
	// Normalise: left stretch first.
	if stretches[0].Lo > stretches[1].Lo {
		stretches[0], stretches[1] = stretches[1], stretches[0]
	}
	// Disjoint and non-adjacent: at least one loose sheaf between them.
	if stretches[0].Hi >= stretches[1].Lo-1 {
		return nil, "error the two stretches must be disjoint and separated by at least one loose sheaf"
	}
	return stretches, ""
}

func stretchesEqual(a, b []stretch) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i].Lo != b[i].Lo || a[i].Hi != b[i].Hi {
			return false
		}
	}
	return true
}

func fmtStretches(cs []stretch) string {
	parts := make([]string, len(cs))
	for i, c := range cs {
		parts[i] = fmt.Sprintf("%d-%d", c.Lo, c.Hi)
	}
	return strings.Join(parts, ",")
}

func (se *Series) bind(args []string) string {
	if se.roundDone {
		return "error this round is over; type next for the following round"
	}
	if len(args) != 1 {
		return "error usage: bind <lo1-hi1,lo2-hi2>, e.g. bind 2-4,8-11"
	}
	stretches, bad := se.parseBind(args[0])
	if bad != "" {
		return bad
	}
	lastRound := se.idx+1 >= len(se.rounds)
	follow := "type next for the following round."
	if lastRound {
		follow = "series complete: every round is resolved."
	}
	se.roundDone = true
	if stretchesEqual(stretches, se.rounds[se.idx].Stretches) {
		se.roundWon = true
		se.recordRound()
		return fmt.Sprintf("correct: the stretches were %s. round %d won in %d names. %s",
			fmtStretches(se.rounds[se.idx].Stretches), se.idx+1, se.namesUsed, follow)
	}
	se.roundWon = false
	se.recordRound()
	return fmt.Sprintf("wrong: that is not the binding. round %d lost. %s", se.idx+1, follow)
}

func (se *Series) next() string {
	if se.finished {
		return "series complete: every round is resolved."
	}
	if !se.roundDone {
		return "error the round in play is still open; submit your answer with bind <lo1-hi1,lo2-hi2>"
	}
	se.idx++
	if se.idx >= len(se.rounds) {
		se.finished = true
		se.publish()
		return "series complete: every round is resolved."
	}
	se.namesUsed = 0
	se.roundDone = false
	se.roundWon = false
	return "new round started.\n" + se.status()
}

const helpText = "You are recovering a bank's hidden sheaf binding across a series of rounds. " +
	"Each round the keeper holds one secret binding: two disjoint stretches over the numbered " +
	"sheaves, never touching, with at least one loose sheaf between them. You talk to this keeper " +
	"only; the stretches exist only inside the keeper and are never shown to you. Exactly one of " +
	"your replies each round is garbled: one count, at a hidden position the keeper fixes before " +
	"you name anything and never changes in response to your play, is off by one, and every other " +
	"reply is truthful. Commands (case-insensitive, one per line): help - " +
	"show this text. read - the round number in play, the sheaf range, the two-stretch shape, " +
	"names used, the name budget, the one-garbled-reply warning, and the objective. name " +
	"<sheaves> - name a handful, a comma-separated list of distinct sheaf numbers leaving out at " +
	"least one sheaf; the keeper replies bound <n>, how many of the handful's sheaves are bound. " +
	"bind <lo1-hi1,lo2-hi2> - submit your one and only final answer for this round, the two " +
	"stretches; a correct binding wins the round and a wrong one loses it immediately. next - " +
	"after a round is resolved, start the following round. You win a round by binding the exact " +
	"stretches within the name budget; a wrong bind loses at once, and running out of names " +
	"leaves only the one bind. The series is over only when every round has been resolved. There " +
	"is no undo and no hint beyond the bound counts."

// loadSpec reads and parses the per-session secret written by the root generator.
func loadSpec() (spec, error) {
	raw, err := os.ReadFile(secretPath())
	if err != nil {
		return spec{}, err
	}
	var s spec
	if err := json.Unmarshal(raw, &s); err != nil {
		return spec{}, err
	}
	return s, nil
}

// serve binds the agent-facing endpoint FIRST, then waits (in the background) for the root
// generator to publish this session's secret. Binding before the secret is ready is deliberate: the
// harness may reach the endpoint the instant the container is up, and a connection refused there is
// read as a harness-level environment failure (the verifier never runs). So the listener is always
// accepting from t=0; while the secret is not yet on disk the keeper answers a short "warming up"
// line instead of refusing the connection. Generation is fast (well under a second) and the keeper
// picks up the secret the moment it appears.
func serve() error {
	sock := endpointPath()
	_ = os.MkdirAll(filepath.Dir(sock), 0o755)
	_ = os.Remove(sock)
	ln, err := net.Listen("unix", sock)
	if err != nil {
		return err
	}
	if err := os.Chmod(sock, 0o666); err != nil {
		return err
	}
	fmt.Fprintf(os.Stderr, "keeper listening on %s (waiting for secret)\n", sock)

	var mu sync.Mutex
	var series *Series // nil until the secret is loaded

	// Load the secret in the background, retrying until the generator publishes it. Bind-first +
	// background-load means the endpoint is up immediately even if generation is still in flight.
	go func() {
		for {
			s, lerr := loadSpec()
			if lerr == nil {
				mu.Lock()
				series = newSeries(s)
				mu.Unlock()
				fmt.Fprintf(os.Stderr, "keeper ready on %s\n", sock)
				return
			}
			time.Sleep(50 * time.Millisecond)
		}
	}()

	for {
		conn, err := ln.Accept()
		if err != nil {
			continue
		}
		go func(c net.Conn) {
			defer c.Close()
			reader := bufio.NewReader(c)
			line, _ := reader.ReadString('\n')
			line = strings.TrimRight(line, "\n")
			mu.Lock()
			ready := series != nil
			reply := func() (r string) {
				defer func() {
					if rec := recover(); rec != nil {
						r = fmt.Sprintf("error internal keeper fault: %v", rec)
					}
				}()
				if !ready {
					return "warming up: the keeper is preparing this session's binding; retry in a moment"
				}
				return series.handle(line)
			}()
			mu.Unlock()
			_, _ = c.Write([]byte(reply + "\n"))
		}(conn)
	}
}

func main() {
	if err := serve(); err != nil {
		fmt.Fprintf(os.Stderr, "keeper fatal: %v\n", err)
		os.Exit(1)
	}
}
