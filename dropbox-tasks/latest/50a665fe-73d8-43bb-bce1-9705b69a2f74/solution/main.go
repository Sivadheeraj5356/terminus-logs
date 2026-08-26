package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"regexp"
	"sort"
	"strings"
)

type SiteIn struct {
	ID         string `json:"id"`
	Attunement string `json:"attunement"`
	Power      int    `json:"power"`
	Ward       int    `json:"ward"`
	Strain     int    `json:"strain"`
	Curse      int    `json:"curse"`
	Threshold  int    `json:"threshold"`
	Value      int    `json:"value"`
}

type CardIn struct {
	ID     string `json:"id"`
	School string `json:"school"`
	Style  string `json:"style"`
	Power  int    `json:"power"`
	Cost   int    `json:"cost"`
}

type OmenIn struct {
	ID        string   `json:"id"`
	Kind      string   `json:"kind"`
	Magnitude int      `json:"magnitude"`
	Targets   []string `json:"targets"`
}

type Position struct {
	Version       int        `json:"version"`
	Rounds        int        `json:"rounds"`
	Energy        int        `json:"energy"`
	EnergyCap     int        `json:"energy_cap"`
	ChannelTokens int        `json:"channel_tokens"`
	RotateTokens  int        `json:"rotate_tokens"`
	FocusTokens   int        `json:"focus_tokens"`
	StrainLimit   int        `json:"strain_limit"`
	Sites         []SiteIn   `json:"sites"`
	Edges         [][]string `json:"edges"`
	Cards         []CardIn   `json:"cards"`
	Omens         []OmenIn   `json:"omens"`
}

type siteRule struct {
	id        string
	threshold int
	value     int
}

type cardRule struct {
	id     string
	school int
	style  string
	power  int
	cost   int
}

type omenRule struct {
	id        string
	kind      string
	magnitude int
	targets   []int
}

type siteState struct {
	attunement int
	power      int
	ward       int
	strain     int
	curse      int
}

type state struct {
	round     int
	energy    int
	channels  int
	rotates   int
	focuses   int
	previous  int
	usedCards uint64
	usedOmens uint64
	sites     []siteState
}

type playerMove struct {
	kind string
	card int
	site int
	a    int
	b    int
	key  string
}

type rivalMove struct {
	kind string
	omen int
	site int
	key  string
}

type PlayerJSON struct {
	Kind string   `json:"kind"`
	Card *string  `json:"card"`
	Site *string  `json:"site"`
	Edge []string `json:"edge"`
}

type RivalJSON struct {
	Kind string  `json:"kind"`
	Omen *string `json:"omen"`
	Site *string `json:"site"`
}

type StepJSON struct {
	Round  int        `json:"round"`
	Player PlayerJSON `json:"player"`
	Rival  RivalJSON  `json:"rival"`
}

type FinalSiteJSON struct {
	ID         string `json:"id"`
	Attunement string `json:"attunement"`
	Power      int    `json:"power"`
	Ward       int    `json:"ward"`
	Strain     int    `json:"strain"`
	Curse      int    `json:"curse"`
	Controlled bool   `json:"controlled"`
}

type FinalJSON struct {
	Energy     int             `json:"energy"`
	Controlled []string        `json:"controlled"`
	Sites      []FinalSiteJSON `json:"sites"`
}

type Output struct {
	GuaranteedScore int        `json:"guaranteed_score"`
	Line            []StepJSON `json:"line"`
	Final           FinalJSON  `json:"final"`
}

type result struct {
	score int
	line  []StepJSON
	final FinalJSON
}

type game struct {
	rounds      int
	energyCap   int
	strainLimit int
	siteRules   []siteRule
	cards       []cardRule
	omens       []omenRule
	edges       [][2]int
	adjacent    [][]int
	memo        map[string]result
}

var validID = regexp.MustCompile(`^[A-Za-z0-9_-]+$`)

func attIndex(v string) (int, bool) {
	switch v {
	case "sun":
		return 0, true
	case "moon":
		return 1, true
	case "star":
		return 2, true
	default:
		return 0, false
	}
}

func attName(v int) string {
	return []string{"sun", "moon", "star"}[v%3]
}

func inRange(v, lo, hi int) bool { return v >= lo && v <= hi }

func loadPosition(path string) (Position, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return Position{}, err
	}

	var raw map[string]json.RawMessage
	if err := json.Unmarshal(b, &raw); err != nil {
		return Position{}, err
	}
	if !hasExactKeys(raw, "version", "rounds", "energy", "energy_cap", "channel_tokens", "rotate_tokens", "focus_tokens", "strain_limit", "sites", "edges", "cards", "omens") {
		return Position{}, errors.New("invalid top-level fields")
	}
	if err := validateObjectArray(raw["sites"], "id", "attunement", "power", "ward", "strain", "curse", "threshold", "value"); err != nil {
		return Position{}, fmt.Errorf("sites: %w", err)
	}
	if err := validateObjectArray(raw["cards"], "id", "school", "style", "power", "cost"); err != nil {
		return Position{}, fmt.Errorf("cards: %w", err)
	}
	if err := validateObjectArray(raw["omens"], "id", "kind", "magnitude", "targets"); err != nil {
		return Position{}, fmt.Errorf("omens: %w", err)
	}

	dec := json.NewDecoder(strings.NewReader(string(b)))
	dec.DisallowUnknownFields()
	var p Position
	if err := dec.Decode(&p); err != nil {
		return Position{}, err
	}
	var extra any
	if err := dec.Decode(&extra); !errors.Is(err, io.EOF) {
		return Position{}, errors.New("trailing JSON")
	}
	return p, nil
}

func hasExactKeys(got map[string]json.RawMessage, want ...string) bool {
	if len(got) != len(want) {
		return false
	}
	for _, key := range want {
		if _, ok := got[key]; !ok {
			return false
		}
	}
	return true
}

func validateObjectArray(raw json.RawMessage, keys ...string) error {
	var objects []map[string]json.RawMessage
	if err := json.Unmarshal(raw, &objects); err != nil {
		return err
	}
	for _, object := range objects {
		if !hasExactKeys(object, keys...) {
			return errors.New("invalid object fields")
		}
	}
	return nil
}

func buildGame(p Position) (*game, state, error) {
	if p.Version != 1 || !inRange(p.Rounds, 1, 5) || !inRange(p.Energy, 0, 12) ||
		!inRange(p.EnergyCap, 0, 12) || p.Energy > p.EnergyCap ||
		!inRange(p.ChannelTokens, 0, 2) || !inRange(p.RotateTokens, 0, 2) || !inRange(p.FocusTokens, 0, 2) ||
		!inRange(p.StrainLimit, 1, 6) || !inRange(len(p.Sites), 2, 4) ||
		!inRange(len(p.Cards), 1, 6) || !inRange(len(p.Omens), 0, 5) {
		return nil, state{}, errors.New("invalid bounds")
	}

	sites := append([]SiteIn(nil), p.Sites...)
	sort.Slice(sites, func(i, j int) bool { return sites[i].ID < sites[j].ID })
	index := make(map[string]int, len(sites))
	rules := make([]siteRule, len(sites))
	states := make([]siteState, len(sites))
	for i, s := range sites {
		if !validID.MatchString(s.ID) || (i > 0 && sites[i-1].ID == s.ID) ||
			!inRange(s.Power, 0, 12) || !inRange(s.Ward, 0, 12) || !inRange(s.Strain, 0, 12) || !inRange(s.Curse, 0, 4) ||
			!inRange(s.Threshold, 1, 12) || !inRange(s.Value, 1, 12) {
			return nil, state{}, errors.New("invalid site")
		}
		att, ok := attIndex(s.Attunement)
		if !ok {
			return nil, state{}, errors.New("invalid attunement")
		}
		index[s.ID] = i
		rules[i] = siteRule{id: s.ID, threshold: s.Threshold, value: s.Value}
		states[i] = siteState{attunement: att, power: s.Power, ward: s.Ward, strain: s.Strain, curse: s.Curse}
	}

	edges := make([][2]int, 0, len(p.Edges))
	seenEdges := map[[2]int]bool{}
	adj := make([][]int, len(sites))
	for _, e := range p.Edges {
		if len(e) != 2 || e[0] == e[1] {
			return nil, state{}, errors.New("invalid edge")
		}
		a, oka := index[e[0]]
		b, okb := index[e[1]]
		if !oka || !okb {
			return nil, state{}, errors.New("unknown edge site")
		}
		if a > b {
			a, b = b, a
		}
		pair := [2]int{a, b}
		if seenEdges[pair] {
			return nil, state{}, errors.New("duplicate edge")
		}
		seenEdges[pair] = true
		edges = append(edges, pair)
		adj[a] = append(adj[a], b)
		adj[b] = append(adj[b], a)
	}
	if len(edges) == 0 {
		return nil, state{}, errors.New("disconnected board")
	}
	visited := make([]bool, len(sites))
	queue := []int{0}
	visited[0] = true
	for len(queue) > 0 {
		v := queue[0]
		queue = queue[1:]
		for _, n := range adj[v] {
			if !visited[n] {
				visited[n] = true
				queue = append(queue, n)
			}
		}
	}
	for _, ok := range visited {
		if !ok {
			return nil, state{}, errors.New("disconnected board")
		}
	}
	sort.Slice(edges, func(i, j int) bool {
		if edges[i][0] != edges[j][0] {
			return edges[i][0] < edges[j][0]
		}
		return edges[i][1] < edges[j][1]
	})

	cardsIn := append([]CardIn(nil), p.Cards...)
	sort.Slice(cardsIn, func(i, j int) bool { return cardsIn[i].ID < cardsIn[j].ID })
	cards := make([]cardRule, len(cardsIn))
	for i, c := range cardsIn {
		sch, ok := attIndex(c.School)
		if !validID.MatchString(c.ID) || (i > 0 && cardsIn[i-1].ID == c.ID) || !ok ||
			(c.Style != "strike" && c.Style != "aegis" && c.Style != "link") ||
			!inRange(c.Power, 1, 8) || !inRange(c.Cost, 0, 8) {
			return nil, state{}, errors.New("invalid card")
		}
		cards[i] = cardRule{id: c.ID, school: sch, style: c.Style, power: c.Power, cost: c.Cost}
	}

	omensIn := append([]OmenIn(nil), p.Omens...)
	sort.Slice(omensIn, func(i, j int) bool { return omensIn[i].ID < omensIn[j].ID })
	omens := make([]omenRule, len(omensIn))
	for i, o := range omensIn {
		if !validID.MatchString(o.ID) || (i > 0 && omensIn[i-1].ID == o.ID) || !inRange(o.Magnitude, 1, 4) ||
			(o.Kind != "drain" && o.Kind != "fracture" && o.Kind != "eclipse" && o.Kind != "curse" && o.Kind != "tax") {
			return nil, state{}, errors.New("invalid omen")
		}
		if (o.Kind == "tax" && len(o.Targets) != 0) || (o.Kind != "tax" && !inRange(len(o.Targets), 1, 4)) {
			return nil, state{}, errors.New("invalid omen targets")
		}
		seenTargets := map[int]bool{}
		var targets []int
		for _, id := range o.Targets {
			v, ok := index[id]
			if !ok || seenTargets[v] {
				return nil, state{}, errors.New("invalid omen target")
			}
			seenTargets[v] = true
			targets = append(targets, v)
		}
		sort.Ints(targets)
		omens[i] = omenRule{id: o.ID, kind: o.Kind, magnitude: o.Magnitude, targets: targets}
	}

	g := &game{rounds: p.Rounds, energyCap: p.EnergyCap, strainLimit: p.StrainLimit,
		siteRules: rules, cards: cards, omens: omens, edges: edges, adjacent: adj, memo: map[string]result{}}
	initial := state{energy: p.Energy, channels: p.ChannelTokens, rotates: p.RotateTokens, focuses: p.FocusTokens, previous: -1, sites: states}
	return g, initial, nil
}

func (g *game) controlled(s state, i int) bool {
	return s.sites[i].power >= g.siteRules[i].threshold && s.sites[i].strain < g.strainLimit
}

func cloneState(s state) state {
	n := s
	n.sites = append([]siteState(nil), s.sites...)
	return n
}

func (g *game) playerActions(s state) []playerMove {
	var out []playerMove
	for ci, c := range g.cards {
		if s.usedCards&(uint64(1)<<ci) != 0 || c.cost > s.energy {
			continue
		}
		for si, site := range g.siteRules {
			out = append(out, playerMove{kind: "deploy", card: ci, site: si, key: "deploy|" + c.id + "|" + site.id})
		}
	}
	if s.channels > 0 {
		for si, site := range g.siteRules {
			out = append(out, playerMove{kind: "channel", site: si, card: -1, a: -1, b: -1, key: "channel|" + site.id})
		}
	}
	if s.rotates > 0 && s.energy >= 1 {
		for _, edge := range g.edges {
			out = append(out, playerMove{kind: "rotate", card: -1, site: -1, a: edge[0], b: edge[1],
				key: "rotate|" + g.siteRules[edge[0]].id + "|" + g.siteRules[edge[1]].id})
		}
	}
	if s.focuses > 0 && s.energy >= 1 {
		for _, edge := range g.edges {
			a, b := edge[0], edge[1]
			out = append(out,
				playerMove{kind: "focus", card: -1, site: -1, a: a, b: b,
					key: "focus|" + g.siteRules[a].id + "|" + g.siteRules[b].id},
				playerMove{kind: "focus", card: -1, site: -1, a: b, b: a,
					key: "focus|" + g.siteRules[b].id + "|" + g.siteRules[a].id})
		}
	}
	out = append(out, playerMove{kind: "rest", card: -1, site: -1, a: -1, b: -1, key: "rest"})
	sort.Slice(out, func(i, j int) bool { return out[i].key < out[j].key })
	return out
}

func (g *game) applyPlayer(s state, m playerMove) state {
	n := cloneState(s)
	switch m.kind {
	case "deploy":
		c := g.cards[m.card]
		wasControlled := g.controlled(s, m.site)
		n.energy -= c.cost
		gain := c.power
		if c.school == n.sites[m.site].attunement {
			gain += 2
		}
		if s.previous == c.school {
			gain++
		}
		n.sites[m.site].power += gain
		if wasControlled {
			n.sites[m.site].strain++
		}
		if c.style == "aegis" {
			n.sites[m.site].ward += 2
		} else if c.style == "link" {
			for _, other := range g.adjacent[m.site] {
				n.sites[other].power++
			}
		}
		n.previous = c.school
		n.usedCards |= uint64(1) << m.card
	case "channel":
		n.channels--
		n.energy += 2
		if n.energy > g.energyCap {
			n.energy = g.energyCap
		}
		n.sites[m.site].ward++
		n.sites[m.site].strain++
		n.previous = -1
	case "rotate":
		n.rotates--
		n.energy--
		n.sites[m.a].attunement, n.sites[m.b].attunement = n.sites[m.b].attunement, n.sites[m.a].attunement
		n.previous = -1
	case "focus":
		n.focuses--
		n.energy--
		movedWard := n.sites[m.a].ward
		if movedWard > 2 {
			movedWard = 2
		}
		n.sites[m.a].ward -= movedWard
		n.sites[m.b].ward += movedWard
		if n.sites[m.a].power > 0 {
			n.sites[m.a].power--
			n.sites[m.b].power++
		}
		n.sites[m.b].strain++
		n.previous = -1
	case "rest":
		n.energy++
		if n.energy > g.energyCap {
			n.energy = g.energyCap
		}
		n.previous = -1
	}
	return n
}

func (g *game) rivalActions(s state) []rivalMove {
	var out []rivalMove
	for oi, o := range g.omens {
		if s.usedOmens&(uint64(1)<<oi) != 0 {
			continue
		}
		if o.kind == "tax" {
			out = append(out, rivalMove{kind: "omen", omen: oi, site: -1, key: "omen|" + o.id + "|-"})
		} else {
			for _, si := range o.targets {
				out = append(out, rivalMove{kind: "omen", omen: oi, site: si, key: "omen|" + o.id + "|" + g.siteRules[si].id})
			}
		}
	}
	if len(out) == 0 {
		out = append(out, rivalMove{kind: "pass", omen: -1, site: -1, key: "pass"})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].key < out[j].key })
	return out
}

func absorb(site *siteState, magnitude int) int {
	blocked := magnitude
	if blocked > site.ward {
		blocked = site.ward
	}
	site.ward -= blocked
	return magnitude - blocked
}

func (g *game) applyRival(s state, m rivalMove) state {
	n := cloneState(s)
	if m.kind == "omen" {
		o := g.omens[m.omen]
		n.usedOmens |= uint64(1) << m.omen
		switch o.kind {
		case "drain":
			left := absorb(&n.sites[m.site], o.magnitude)
			n.sites[m.site].power -= left
			if n.sites[m.site].power < 0 {
				n.sites[m.site].power = 0
			}
		case "fracture":
			left := absorb(&n.sites[m.site], o.magnitude)
			n.sites[m.site].strain += left
		case "eclipse":
			if n.sites[m.site].ward > 0 {
				n.sites[m.site].ward--
			} else {
				n.sites[m.site].attunement = (n.sites[m.site].attunement + o.magnitude) % 3
			}
		case "curse":
			n.sites[m.site].curse += o.magnitude
		case "tax":
			n.energy -= o.magnitude
			if n.energy < 0 {
				n.energy = 0
			}
		}
	}
	for i := range n.sites {
		if n.sites[i].curse > 0 {
			if n.sites[i].power > 0 {
				n.sites[i].power--
			}
			n.sites[i].curse--
		}
		if n.sites[i].strain >= g.strainLimit && n.sites[i].power > 0 {
			n.sites[i].power--
		}
	}
	income := 0
	for i := range n.sites {
		if g.controlled(n, i) {
			income++
		}
	}
	n.energy += income
	if n.energy > g.energyCap {
		n.energy = g.energyCap
	}
	n.round++
	return n
}

func playerJSON(g *game, m playerMove) PlayerJSON {
	out := PlayerJSON{Kind: m.kind}
	switch m.kind {
	case "deploy":
		card, site := g.cards[m.card].id, g.siteRules[m.site].id
		out.Card, out.Site = &card, &site
	case "channel":
		site := g.siteRules[m.site].id
		out.Site = &site
	case "rotate", "focus":
		out.Edge = []string{g.siteRules[m.a].id, g.siteRules[m.b].id}
	}
	return out
}

func rivalJSON(g *game, m rivalMove) RivalJSON {
	out := RivalJSON{Kind: m.kind}
	if m.kind == "omen" {
		omen := g.omens[m.omen].id
		out.Omen = &omen
		if m.site >= 0 {
			site := g.siteRules[m.site].id
			out.Site = &site
		}
	}
	return out
}

func (g *game) terminal(s state) result {
	score := s.energy
	controlled := make([]string, 0, len(s.sites))
	attSeen := [3]bool{}
	finalSites := make([]FinalSiteJSON, len(s.sites))
	for i, site := range s.sites {
		ctrl := g.controlled(s, i)
		if ctrl {
			score += g.siteRules[i].value
			controlled = append(controlled, g.siteRules[i].id)
			attSeen[site.attunement] = true
		}
		score -= site.strain
		finalSites[i] = FinalSiteJSON{ID: g.siteRules[i].id, Attunement: attName(site.attunement),
			Power: site.power, Ward: site.ward, Strain: site.strain, Curse: site.curse, Controlled: ctrl}
	}
	for _, seen := range attSeen {
		if seen {
			score += 2
		}
	}
	if len(controlled) == len(s.sites) {
		score += 4
	}
	return result{score: score, line: []StepJSON{}, final: FinalJSON{Energy: s.energy, Controlled: controlled, Sites: finalSites}}
}

func stateKey(s state) string {
	var b strings.Builder
	fmt.Fprintf(&b, "%d/%d/%d/%d/%d/%d/%d/%d", s.round, s.energy, s.channels, s.rotates, s.focuses, s.previous, s.usedCards, s.usedOmens)
	for _, site := range s.sites {
		fmt.Fprintf(&b, "/%d,%d,%d,%d,%d", site.attunement, site.power, site.ward, site.strain, site.curse)
	}
	return b.String()
}

func prepend(step StepJSON, tail []StepJSON) []StepJSON {
	out := make([]StepJSON, 1, len(tail)+1)
	out[0] = step
	out = append(out, tail...)
	return out
}

func (g *game) solve(s state) result {
	if s.round == g.rounds {
		return g.terminal(s)
	}
	key := stateKey(s)
	if cached, ok := g.memo[key]; ok {
		return cached
	}
	var best result
	bestSet := false
	bestPlayerKey := ""
	for _, pm := range g.playerActions(s) {
		afterPlayer := g.applyPlayer(s, pm)
		var worst result
		worstSet := false
		worstRivalKey := ""
		for _, rm := range g.rivalActions(afterPlayer) {
			child := g.solve(g.applyRival(afterPlayer, rm))
			candidate := result{score: child.score,
				line:  prepend(StepJSON{Round: s.round + 1, Player: playerJSON(g, pm), Rival: rivalJSON(g, rm)}, child.line),
				final: child.final}
			if !worstSet || candidate.score < worst.score || (candidate.score == worst.score && rm.key < worstRivalKey) {
				worst, worstSet, worstRivalKey = candidate, true, rm.key
			}
		}
		if !bestSet || worst.score > best.score || (worst.score == best.score && pm.key < bestPlayerKey) {
			best, bestSet, bestPlayerKey = worst, true, pm.key
		}
	}
	g.memo[key] = best
	return best
}

func run(input, output string) error {
	p, err := loadPosition(input)
	if err != nil {
		return err
	}
	g, initial, err := buildGame(p)
	if err != nil {
		return err
	}
	r := g.solve(initial)
	doc := Output{GuaranteedScore: r.score, Line: r.line, Final: r.final}
	tmp := output + ".tmp"
	f, err := os.Create(tmp)
	if err != nil {
		return err
	}
	enc := json.NewEncoder(f)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(doc); err != nil {
		f.Close()
		os.Remove(tmp)
		return err
	}
	if err := f.Close(); err != nil {
		os.Remove(tmp)
		return err
	}
	if err := os.Rename(tmp, output); err != nil {
		os.Remove(tmp)
		return err
	}
	return nil
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: conclave INPUT OUTPUT")
		os.Exit(2)
	}
	if err := run(os.Args[1], os.Args[2]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
}
