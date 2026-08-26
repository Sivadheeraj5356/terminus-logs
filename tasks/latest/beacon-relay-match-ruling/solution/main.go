package main

import (
	"encoding/json"
	"os"
	"sort"
)

type Cell struct {
	ID        string   `json:"id"`
	Neighbors []string `json:"neighbors"`
	MoveCost  int64    `json:"move_cost"`
	Beacon    int64    `json:"beacon"`
	Recharge  int64    `json:"recharge"`
}
type Unit struct {
	ID        string `json:"id"`
	Player    string `json:"player"`
	Cell      string `json:"cell"`
	Health    int64  `json:"health"`
	Energy    int64  `json:"energy"`
	MaxEnergy int64  `json:"max_energy"`
	Strength  int64  `json:"strength"`
	Alive     bool   `json:"-"`
}
type Action struct {
	Unit   string `json:"unit"`
	Type   string `json:"type"`
	To     string `json:"to"`
	Target string `json:"target"`
}
type Ruling struct {
	ID          string     `json:"id"`
	Cost        int64      `json:"cost"`
	RequiresAll []string   `json:"requires_all"`
	RequiresAny [][]string `json:"requires_any"`
	Conflicts   []string   `json:"conflicts"`
	Round       int        `json:"round"`
	Unit        string     `json:"unit"`
	Action      Action     `json:"action"`
}
type RelayRequirement struct {
	ID          string   `json:"id"`
	Rulings     []string `json:"rulings"`
	MinSelected int      `json:"min_selected"`
	MaxSelected int      `json:"max_selected"`
}
type CoordinationCost struct {
	Rulings []string `json:"rulings"`
	Cost    int64    `json:"cost"`
}
type Match struct {
	Players           []string           `json:"players"`
	Claimant          string             `json:"claimant"`
	Budget            int64              `json:"budget"`
	RelayRequirements []RelayRequirement `json:"relay_requirements"`
	CoordinationCosts []CoordinationCost  `json:"coordination_costs"`
	Cells             []Cell             `json:"cells"`
	Units             []Unit             `json:"units"`
	Rounds            [][]Action         `json:"rounds"`
	Rulings           []Ruling           `json:"rulings"`
	Dockets           [][]string         `json:"dockets"`
}
type ScoreOutput struct {
	Player string `json:"player"`
	Score  int64  `json:"score"`
}
type UnitOutput struct {
	ID     string `json:"id"`
	Player string `json:"player"`
	Cell   string `json:"cell"`
	Health int64  `json:"health"`
	Energy int64  `json:"energy"`
}
type Output struct {
	Status   string        `json:"status"`
	Selected []string      `json:"selected"`
	Scores   []ScoreOutput `json:"scores"`
	Units    []UnitOutput  `json:"units"`
	Winner   *string       `json:"winner"`
}
type rank struct{ score, survivors, health int64 }
type candidate struct {
	out     Output
	quality [5]int64
	cost    int64
	found   bool
}
type actionSlot struct {
	round int
	unit  string
}

func adjacent(cells map[string]Cell, from, to string) bool {
	for _, n := range cells[from].Neighbors {
		if n == to {
			return true
		}
	}
	return false
}

func replay(m Match, chosen []*Ruling) (Output, map[string]rank) {
	cells := map[string]Cell{}
	for _, c := range m.Cells {
		cells[c.ID] = c
	}
	units := map[string]*Unit{}
	for i := range m.Units {
		u := m.Units[i]
		u.Alive = true
		units[u.ID] = &u
	}
	scores := map[string]int64{}
	for _, p := range m.Players {
		scores[p] = 0
	}
	patches := map[int]map[string]Action{}
	for _, r := range chosen {
		if patches[r.Round] == nil {
			patches[r.Round] = map[string]Action{}
		}
		patches[r.Round][r.Unit] = r.Action
	}

	for roundIndex, baseline := range m.Rounds {
		commands := map[string]Action{}
		for _, a := range baseline {
			commands[a.Unit] = a
		}
		for id, a := range patches[roundIndex] {
			commands[id] = a
		}
		positions := map[string]string{}
		for id, u := range units {
			if u.Alive {
				positions[u.Cell] = id
			}
		}
		intents := map[string]string{}
		counts := map[string]int{}
		for id, u := range units {
			if !u.Alive {
				continue
			}
			a, ok := commands[id]
			if !ok || a.Type != "move" {
				continue
			}
			destination, ok := cells[a.To]
			if !ok || !adjacent(cells, u.Cell, a.To) || u.Energy < destination.MoveCost {
				continue
			}
			u.Energy -= destination.MoveCost
			intents[id] = a.To
			counts[a.To]++
		}
		unique := map[string]bool{}
		for id, to := range intents {
			unique[id] = counts[to] == 1
		}
		state := map[string]int{}
		success := map[string]bool{}
		var resolve func(string) bool
		resolve = func(id string) bool {
			if !unique[id] {
				return false
			}
			if state[id] == 1 {
				return true
			}
			if state[id] == 2 {
				return success[id]
			}
			state[id] = 1
			occupant, occupied := positions[intents[id]]
			ok := !occupied || (unique[occupant] && resolve(occupant))
			state[id] = 2
			success[id] = ok
			return ok
		}
		for id := range intents {
			resolve(id)
		}
		for id, ok := range success {
			if ok {
				units[id].Cell = intents[id]
			}
		}

		shields := map[string]int64{}
		for id, u := range units {
			if u.Alive {
				if a, ok := commands[id]; ok && a.Type == "guard" && u.Energy >= 1 {
					u.Energy--
					shields[id] = u.Strength
				}
			}
		}
		damage := map[string]int64{}
		for id, u := range units {
			if !u.Alive {
				continue
			}
			a, ok := commands[id]
			if !ok || a.Type != "strike" || u.Energy < 1 {
				continue
			}
			t, ok := units[a.Target]
			if !ok || !t.Alive || t.Player == u.Player || !adjacent(cells, u.Cell, t.Cell) {
				continue
			}
			u.Energy--
			damage[t.ID] += u.Strength
		}
		for id, incoming := range damage {
			dealt := incoming - shields[id]
			if dealt < 0 {
				dealt = 0
			}
			units[id].Health -= dealt
		}
		for _, u := range units {
			if u.Alive && u.Health <= 0 {
				u.Alive = false
			}
		}
		for _, u := range units {
			if u.Alive {
				c := cells[u.Cell]
				scores[u.Player] += c.Beacon
				u.Energy += c.Recharge
				if u.Energy > u.MaxEnergy {
					u.Energy = u.MaxEnergy
				}
			}
		}
	}

	players := append([]string{}, m.Players...)
	sort.Strings(players)
	scoreOut := make([]ScoreOutput, 0, 2)
	ranks := map[string]rank{}
	for _, p := range players {
		scoreOut = append(scoreOut, ScoreOutput{p, scores[p]})
		ranks[p] = rank{score: scores[p]}
	}
	ids := []string{}
	for id, u := range units {
		if u.Alive {
			ids = append(ids, id)
			r := ranks[u.Player]
			r.survivors++
			r.health += u.Health
			ranks[u.Player] = r
		}
	}
	sort.Strings(ids)
	unitOut := make([]UnitOutput, 0, len(ids))
	for _, id := range ids {
		u := units[id]
		unitOut = append(unitOut, UnitOutput{u.ID, u.Player, u.Cell, u.Health, u.Energy})
	}
	better := func(a, b rank) int {
		if a.score != b.score {
			if a.score > b.score {
				return 1
			}
			return -1
		}
		if a.survivors != b.survivors {
			if a.survivors > b.survivors {
				return 1
			}
			return -1
		}
		if a.health != b.health {
			if a.health > b.health {
				return 1
			}
			return -1
		}
		return 0
	}
	var winner *string
	if better(ranks[players[0]], ranks[players[1]]) != 0 {
		w := players[0]
		if better(ranks[players[0]], ranks[players[1]]) < 0 {
			w = players[1]
		}
		winner = &w
	}
	return Output{Status: "complete", Selected: []string{}, Scores: scoreOut, Units: unitOut, Winner: winner}, ranks
}

func lexLess(a, b []string) bool {
	for i := range a {
		if a[i] != b[i] {
			return a[i] < b[i]
		}
	}
	return false
}
func solve(m Match) Output {
	byID := map[string]*Ruling{}
	docketOf := map[string]int{}
	conflicts := map[string]map[string]bool{}
	for i := range m.Rulings {
		r := &m.Rulings[i]
		byID[r.ID] = r
		for _, x := range r.Conflicts {
			if conflicts[r.ID] == nil {
				conflicts[r.ID] = map[string]bool{}
			}
			if conflicts[x] == nil {
				conflicts[x] = map[string]bool{}
			}
			conflicts[r.ID][x] = true
			conflicts[x][r.ID] = true
		}
	}
	for d, ids := range m.Dockets {
		for _, id := range ids {
			docketOf[id] = d
		}
	}
	minSuffix := make([]int64, len(m.Dockets)+1)
	for i := len(m.Dockets) - 1; i >= 0; i-- {
		small := int64(1 << 62)
		for _, id := range m.Dockets[i] {
			if byID[id].Cost < small {
				small = byID[id].Cost
			}
		}
		minSuffix[i] = minSuffix[i+1] + small
	}
	selected := map[string]bool{}
	slots := map[actionSlot]bool{}
	picked := []*Ruling{}
	best := candidate{}
	packageCost := func(base int64) int64 {
		total := base
		for _, link := range m.CoordinationCosts {
			active := true
			for _, id := range link.Rulings {
				if !selected[id] {
					active = false
					break
				}
			}
			if active {
				total += link.Cost
			}
		}
		return total
	}
	partialValid := func(depth int) bool {
		for _, r := range picked {
			for _, id := range r.RequiresAll {
				if docketOf[id] < depth && !selected[id] {
					return false
				}
			}
			for _, group := range r.RequiresAny {
				any := false
				closed := true
				for _, id := range group {
					if selected[id] {
						any = true
					}
					if docketOf[id] >= depth {
						closed = false
					}
				}
				if closed && !any {
					return false
				}
			}
		}
		for _, requirement := range m.RelayRequirements {
			count := 0
			futureDockets := map[int]bool{}
			for _, id := range requirement.Rulings {
				if selected[id] {
					count++
				} else if d := docketOf[id]; d >= depth {
					futureDockets[d] = true
				}
			}
			if count > requirement.MaxSelected || count+len(futureDockets) < requirement.MinSelected {
				return false
			}
			if depth == len(m.Dockets) && count < requirement.MinSelected {
				return false
			}
		}
		return true
	}
	var dfs func(int, int64)
	dfs = func(depth int, baseCost int64) {
		cost := packageCost(baseCost)
		if cost+minSuffix[depth] > m.Budget {
			return
		}
		if depth == len(m.Dockets) {
			if !partialValid(depth) {
				return
			}
			out, ranks := replay(m, picked)
			ids := make([]string, 0, len(picked))
			for _, r := range picked {
				ids = append(ids, r.ID)
			}
			sort.Strings(ids)
			out.Selected = ids
			claim := ranks[m.Claimant]
			oppName := m.Players[0]
			if oppName == m.Claimant {
				oppName = m.Players[1]
			}
			result := int64(1)
			if out.Winner != nil {
				if *out.Winner == m.Claimant {
					result = 2
				} else {
					result = 0
				}
			}
			q := [5]int64{result, claim.score, claim.survivors, claim.health, -ranks[oppName].score}
			better := !best.found
			if !better {
				for i := 0; i < 5; i++ {
					if q[i] != best.quality[i] {
						better = q[i] > best.quality[i]
						break
					}
				}
				if q == best.quality {
					if cost != best.cost {
						better = cost < best.cost
					} else {
						better = lexLess(ids, best.out.Selected)
					}
				}
			}
			if better {
				best = candidate{out: out, quality: q, cost: cost, found: true}
			}
			return
		}
		for _, id := range m.Dockets[depth] {
			r := byID[id]
			if baseCost+r.Cost > m.Budget {
				continue
			}
			bad := false
			for chosen := range selected {
				if conflicts[id][chosen] {
					bad = true
					break
				}
			}
			slot := actionSlot{round: r.Round, unit: r.Unit}
			if bad || slots[slot] {
				continue
			}
			selected[id] = true
			slots[slot] = true
			picked = append(picked, r)
			if partialValid(depth + 1) {
				dfs(depth+1, baseCost+r.Cost)
			}
			picked = picked[:len(picked)-1]
			delete(slots, slot)
			delete(selected, id)
		}
	}
	dfs(0, 0)
	if best.found {
		return best.out
	}
	return Output{Status: "infeasible", Selected: []string{}, Scores: []ScoreOutput{}, Units: []UnitOutput{}, Winner: nil}
}

func main() {
	data, err := os.ReadFile("/app/match.json")
	if err != nil {
		panic(err)
	}
	var m Match
	if err = json.Unmarshal(data, &m); err != nil {
		panic(err)
	}
	out := solve(m)
	if err = os.MkdirAll("/app/output", 0755); err != nil {
		panic(err)
	}
	f, err := os.Create("/app/output/result.json")
	if err != nil {
		panic(err)
	}
	defer f.Close()
	if err = json.NewEncoder(f).Encode(out); err != nil {
		panic(err)
	}
}
