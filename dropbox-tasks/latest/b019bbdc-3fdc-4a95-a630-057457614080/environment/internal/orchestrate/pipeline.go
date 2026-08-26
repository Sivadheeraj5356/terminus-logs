package orchestrate

import (
	"fmt"
	"os/exec"
	"sort"
	"strconv"
	"strings"

	"splicekit/internal/cap"
	"splicekit/internal/lane"
	"splicekit/internal/ledger"
	"splicekit/internal/peers"
	"splicekit/internal/route"
	"splicekit/internal/triage"
	"splicekit/pkg/model"
)

type edge struct {
	span model.Span
	to   string
}

func buildAdj(sc *model.Scenario) map[string][]edge {
	cut := map[string]bool{}
	for _, c := range sc.Cuts {
		cut[c] = true
	}
	adj := map[string][]edge{}
	for _, sp := range sc.Spans {
		if cut[sp.ID] {
			continue
		}
		adj[sp.A] = append(adj[sp.A], edge{span: sp, to: sp.B})
		adj[sp.B] = append(adj[sp.B], edge{span: sp, to: sp.A})
	}
	for k := range adj {
		sort.SliceStable(adj[k], func(i, j int) bool {
			return adj[k][i].span.ID < adj[k][j].span.ID
		})
	}
	return adj
}

func regenOf(sc *model.Scenario) map[string]bool {
	m := map[string]bool{}
	for _, n := range sc.Nodes {
		m[n.ID] = n.Regen
	}
	return m
}

func shortest(adj map[string][]edge, src, dst string) []model.Span {
	type item struct {
		node string
		path []model.Span
	}
	q := []item{{node: src, path: nil}}
	dist := map[string]int{src: 0}
	var cands [][]model.Span
	best := -1
	for len(q) > 0 {
		cur := q[0]
		q = q[1:]
		if best >= 0 && len(cur.path) > best {
			continue
		}
		if cur.node == dst && len(cur.path) > 0 {
			if best < 0 || len(cur.path) < best {
				best = len(cur.path)
				cands = [][]model.Span{append([]model.Span{}, cur.path...)}
			} else if len(cur.path) == best {
				cands = append(cands, append([]model.Span{}, cur.path...))
			}
			continue
		}
		for _, e := range adj[cur.node] {
			nd := len(cur.path) + 1
			if best >= 0 && nd > best {
				continue
			}
			prev, ok := dist[e.to]
			if ok && prev < nd {
				continue
			}
			if !ok || prev > nd {
				dist[e.to] = nd
			}
			np := append(append([]model.Span{}, cur.path...), e.span)
			q = append(q, item{node: e.to, path: np})
		}
	}
	return route.Pick(cands)
}

func knit(oxk string, prev int, atRegen bool, free []int) (int, bool, error) {
	parts := make([]string, len(free))
	for i, v := range free {
		parts[i] = strconv.Itoa(v)
	}
	flag := "0"
	if atRegen {
		flag = "1"
	}
	out, err := exec.Command(oxk, "knit", strconv.Itoa(prev), flag, strings.Join(parts, ",")).CombinedOutput()
	if err != nil {
		return 0, false, fmt.Errorf("knit: %v %s", err, string(out))
	}
	s := strings.TrimSpace(string(out))
	if s == "none" {
		return 0, false, nil
	}
	v, err := strconv.Atoi(s)
	if err != nil {
		return 0, false, err
	}
	return v, true, nil
}

func draw(oxk string, cool float64, channels int, perCh, cap float64) (float64, bool, error) {
	out, err := exec.Command(
		oxk, "draw",
		fmt.Sprintf("%.10f", cool),
		strconv.Itoa(channels),
		fmt.Sprintf("%.10f", perCh),
		fmt.Sprintf("%.10f", cap),
	).CombinedOutput()
	if err != nil {
		return 0, false, fmt.Errorf("draw: %v %s", err, string(out))
	}
	fields := strings.Fields(strings.TrimSpace(string(out)))
	if len(fields) != 2 {
		return 0, false, fmt.Errorf("bad draw output: %q", string(out))
	}
	used, err := strconv.ParseFloat(fields[0], 64)
	if err != nil {
		return 0, false, err
	}
	ok := fields[1] == "1"
	return used, ok, nil
}

type Result struct {
	Hops     []model.Hop
	Served   []string
	Rejected []string
	PeakMW   float64
}

func gauge_s(oxk string, pl *ledger.PumpLedger, sc *model.Scenario, bk *lane.Book, path []model.Span) (float64, bool, error) {
	chAdd := map[string]int{}
	for _, sp := range path {
		chAdd[sp.ID]++
	}
	peak := 0.0
	for sid, add := range chAdd {
		sp := spanByID(sc, sid)
		cool := pl.Cool[sid]
		ch := bk.ChannelCount(sid)
		used, ok, err := draw(oxk, cool, ch, sc.MwPerChannel, sp.PumpMW)
		if err != nil {
			return 0, false, err
		}
		if used > peak {
			peak = used
		}
		if !ok {
			return peak, false, nil
		}
		_ = add
	}
	return peak, true, nil
}

func PlanR(oxk string, sc *model.Scenario, pl *ledger.PumpLedger, bk *lane.Book) (Result, error) {
	adj := buildAdj(sc)
	regen := regenOf(sc)
	ordered := triage.Rank(sc.Demands)
	var hops []model.Hop
	var served []string
	var rejected []string
	peak := 0.0

	for _, d := range ordered {
		path := shortest(adj, d.Src, d.Dst)
		if path == nil {
			rejected = append(rejected, d.ID)
			continue
		}
		if !cap.Pass(path, d.Gbps, bk) {
			rejected = append(rejected, d.ID)
			continue
		}

		prev := -1
		at := d.Src
		tentLams := []int{}
		tentHops := []model.Hop{}
		okPath := true
		for i, sp := range path {
			free := bk.FreeOn(sp)
			atRegen := regen[at]
			lam, ok, err := knit(oxk, prev, atRegen, free)
			if err != nil {
				return Result{}, err
			}
			if !ok {
				okPath = false
				break
			}
			tentLams = append(tentLams, lam)
			tentHops = append(tentHops, model.Hop{
				DemandID: d.ID,
				Hop:      i,
				SpanID:   sp.ID,
				Lambda:   lam,
				Gbps:     d.Gbps,
			})
			bk.Stage(sp.ID, lam)
			if sp.A == at {
				at = sp.B
			} else {
				at = sp.A
			}
			prev = lam
		}
		if !okPath {
			bk.DropDraft(path, tentLams)
			rejected = append(rejected, d.ID)
			continue
		}

		pk, okPump, err := gauge_s(oxk, pl, sc, bk, path)
		if err != nil {
			return Result{}, err
		}
		if pk > peak {
			peak = pk
		}
		if !okPump {
			bk.DropDraft(path, tentLams)
			rejected = append(rejected, d.ID)
			continue
		}

		bk.CommitDemand(path, tentLams, d.Gbps)
		hops = append(hops, tentHops...)
		served = append(served, d.ID)
	}

	return Result{Hops: hops, Served: served, Rejected: rejected, PeakMW: peak}, nil
}

func SealT(oxk string, pl *ledger.PumpLedger, sc *model.Scenario, bk *lane.Book, res Result) (float64, error) {
	peak := res.PeakMW
	for sid, ch := range bk.UsedChannels() {
		sp := spanByID(sc, sid)
		cool := pl.Cool[sid]
		used, _, err := draw(oxk, cool, ch, sc.MwPerChannel, sp.PumpMW)
		if err != nil {
			return peak, err
		}
		if used > peak {
			peak = used
		}
		pl.Cool[sid] = ledger.Carry(sc.CoolFactor, used)
	}
	ledger.PruneIdle(pl, bk.UsedChannels())
	if err := pl.Save(); err != nil {
		return peak, err
	}
	return peak, nil
}

func spanByID(sc *model.Scenario, id string) model.Span {
	for _, sp := range sc.Spans {
		if sp.ID == id {
			return sp
		}
	}
	return model.Span{}
}

func Settle(sc *model.Scenario, served []string) ([][]string, float64) {
	return peers.Rows(sc, served)
}
