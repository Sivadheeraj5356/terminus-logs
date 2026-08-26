package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

type Pair struct {
	Amber  string `json:"amber"`
	Cobalt string `json:"cobalt"`
}

type Edge struct {
	ID        string `json:"id"`
	Actor     string `json:"actor"`
	From      string `json:"from"`
	To        string `json:"to"`
	Cost      int    `json:"cost"`
	PhaseMask string `json:"phase_mask"`
	Boostable bool   `json:"boostable"`
	Gate      string `json:"gate"`
	Tone      int    `json:"tone"`
}

type Beacon struct {
	ID         string `json:"id"`
	Room       string `json:"room"`
	ListenCost int    `json:"listen_cost"`
	Tone       int    `json:"tone"`
}

type HiddenState struct {
	ID         string              `json:"id"`
	World      string              `json:"world"`
	OpenGates  []string            `json:"open_gates"`
	Accepting  bool                `json:"accepting"`
	Signals    map[string]string   `json:"signals"`
	NextByTone map[string][]string `json:"next_by_tone"`
}

type Board struct {
	SchemaVersion  string        `json:"schema_version"`
	BoardID        string        `json:"board_id"`
	Period         int           `json:"period"`
	MaxTurns       int           `json:"max_turns"`
	PhaseCharges   int           `json:"phase_charges"`
	ChargeCap      int           `json:"charge_cap"`
	BoostSurcharge int           `json:"boost_surcharge"`
	BlockedCost    int           `json:"blocked_cost"`
	TetherLimit    int           `json:"tether_limit"`
	ToneModulus    int           `json:"tone_modulus"`
	Rooms          []string      `json:"rooms"`
	Start          Pair          `json:"start"`
	Goals          Pair          `json:"goals"`
	Edges          []Edge        `json:"edges"`
	TetherLinks    [][]string    `json:"tether_links"`
	Beacons        []Beacon      `json:"beacons"`
	HiddenStates   []HiddenState `json:"hidden_states"`
	InitialStates  []string      `json:"initial_states"`
}

type ActionOut struct {
	Amber  string `json:"amber"`
	Cobalt string `json:"cobalt"`
}

type BranchOut struct {
	Observation string `json:"observation"`
	Next        string `json:"next"`
}

type NodeOut struct {
	ID          string      `json:"id"`
	Tick        int         `json:"tick"`
	Amber       string      `json:"amber"`
	Cobalt      string      `json:"cobalt"`
	ChargesLeft int         `json:"charges_left"`
	BoostsUsed  int         `json:"boosts_used"`
	Energy      int         `json:"energy"`
	Belief      []string    `json:"belief"`
	Terminal    bool        `json:"terminal"`
	Action      *ActionOut  `json:"action"`
	Branches    []BranchOut `json:"branches"`
}

type PolicyOut struct {
	SchemaVersion string    `json:"schema_version"`
	BoardID       string    `json:"board_id"`
	Status        string    `json:"status"`
	WorstTurns    int       `json:"worst_turns"`
	WorstBoosts   int       `json:"worst_boosts"`
	WorstEnergy   int       `json:"worst_energy"`
	TotalTurns    int       `json:"total_turns"`
	PolicyNodes   int       `json:"policy_nodes"`
	Root          string    `json:"root"`
	Nodes         []NodeOut `json:"nodes"`
}

type compiledBoard struct {
	board         Board
	roomIndex     map[string]int
	edgeByID      map[string]Edge
	beaconByID    map[string]Beacon
	hiddenByID    map[string]HiddenState
	openGates     map[string]map[string]bool
	outgoing      [2]map[string][]Edge
	beaconsAtRoom map[string][]Beacon
	dist          [][]int
}

type actionOption struct {
	Label    string
	Kind     int
	ID       string
	To       string
	Cost     int
	Tone     int
	Boost    int
	Edge     *Edge
	Beacon   *Beacon
	SortRank int
}

type infoState struct {
	Tick        int
	Amber       string
	Cobalt      string
	ChargesLeft int
	BoostsUsed  int
	Energy      int
	Belief      []string
}

type branchPlan struct {
	Observation string
	State       infoState
	Child       *plan
}

type plan struct {
	Terminal     bool
	AmberAction  string
	CobaltAction string
	Branches     []branchPlan
	WorstTurns   int
	WorstBoosts  int
	WorstEnergy  int
	TotalTurns   int
	WorldTurns   map[string]int
}

type memoEntry struct {
	Done  bool
	Plans []*plan
}

type simulator struct {
	cb   *compiledBoard
	memo map[string]memoEntry
}

type pieceResult struct {
	Room        string
	Component   string
	Energy      int
	Tone        int
	Boosts      int
	ActionLabel string
}

type groupedOutcome struct {
	Amber       string
	Cobalt      string
	ChargesLeft int
	BoostsUsed  int
	Energy      int
	Belief      []string
}

var (
	tokenPattern   = regexp.MustCompile(`^[A-Za-z0-9._-]+$`)
	integerPattern = regexp.MustCompile(`^-?(0|[1-9][0-9]*)$`)
)

func main() {
	boardPath := flag.String("board", "", "path to a Phaseglass board JSON file")
	outputPath := flag.String("output", "", "path for the policy JSON file")
	flag.Parse()
	if *boardPath == "" || *outputPath == "" {
		fmt.Fprintln(os.Stderr, "invalid board: --board and --output are required")
		os.Exit(2)
	}
	samePath, err := pathsResolveToSameFile(*boardPath, *outputPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "invalid board: %v\n", err)
		os.Exit(1)
	}
	if samePath {
		fmt.Fprintln(os.Stderr, "invalid board: board and output resolve to the same file")
		os.Exit(1)
	}
	board, err := loadBoard(*boardPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "invalid board: %v\n", err)
		os.Exit(1)
	}
	cb, err := compileBoard(board)
	if err != nil {
		fmt.Fprintf(os.Stderr, "invalid board: %v\n", err)
		os.Exit(1)
	}
	result := solve(cb)
	if err := writePolicy(*outputPath, result); err != nil {
		fmt.Fprintf(os.Stderr, "output error: %v\n", err)
		os.Exit(1)
	}
}

func resolvePathForComparison(path string) (string, error) {
	absolute, err := filepath.Abs(path)
	if err != nil {
		return "", err
	}
	absolute = filepath.Clean(absolute)
	if resolved, err := filepath.EvalSymlinks(absolute); err == nil {
		return filepath.Clean(resolved), nil
	}
	current := absolute
	var suffix []string
	for {
		if _, err := os.Lstat(current); err == nil {
			resolved, err := filepath.EvalSymlinks(current)
			if err != nil {
				return "", err
			}
			for index := len(suffix) - 1; index >= 0; index-- {
				resolved = filepath.Join(resolved, suffix[index])
			}
			return filepath.Clean(resolved), nil
		} else if !os.IsNotExist(err) {
			return "", err
		}
		parent := filepath.Dir(current)
		if parent == current {
			return "", errors.New("cannot resolve path")
		}
		suffix = append(suffix, filepath.Base(current))
		current = parent
	}
}

func pathsResolveToSameFile(boardPath, outputPath string) (bool, error) {
	boardResolved, err := resolvePathForComparison(boardPath)
	if err != nil {
		return false, err
	}
	outputResolved, err := resolvePathForComparison(outputPath)
	if err != nil {
		return false, err
	}
	if boardResolved == outputResolved {
		return true, nil
	}
	boardInfo, err := os.Stat(boardPath)
	if err != nil {
		return false, err
	}
	outputInfo, err := os.Stat(outputPath)
	if err == nil {
		return os.SameFile(boardInfo, outputInfo), nil
	}
	if !os.IsNotExist(err) {
		return false, err
	}
	return false, nil
}

func loadBoard(path string) (Board, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Board{}, err
	}
	if err := checkRequiredShape(data); err != nil {
		return Board{}, err
	}
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	var board Board
	if err := dec.Decode(&board); err != nil {
		return Board{}, err
	}
	var extra json.RawMessage
	if err := dec.Decode(&extra); err == nil {
		return Board{}, errors.New("multiple JSON values")
	} else if !errors.Is(err, io.EOF) {
		return Board{}, err
	}
	return board, nil
}

func exactKeys(obj map[string]json.RawMessage, expected []string) error {
	if len(obj) != len(expected) {
		return errors.New("wrong object member set")
	}
	for _, key := range expected {
		if _, ok := obj[key]; !ok {
			return fmt.Errorf("missing %s", key)
		}
	}
	return nil
}

func jsonKind(raw json.RawMessage, marker byte) bool {
	trimmed := bytes.TrimSpace(raw)
	return len(trimmed) > 0 && trimmed[0] == marker
}

func requireJSONString(raw json.RawMessage, label string) error {
	if !jsonKind(raw, '"') {
		return fmt.Errorf("%s must be a string", label)
	}
	var value string
	if err := json.Unmarshal(raw, &value); err != nil {
		return fmt.Errorf("%s must be a string", label)
	}
	return nil
}

func requireJSONInteger(raw json.RawMessage, label string) error {
	trimmed := strings.TrimSpace(string(raw))
	if !integerPattern.MatchString(trimmed) {
		return fmt.Errorf("%s must be an integer", label)
	}
	return nil
}

func requireJSONBool(raw json.RawMessage, label string) error {
	if !bytes.Equal(bytes.TrimSpace(raw), []byte("true")) && !bytes.Equal(bytes.TrimSpace(raw), []byte("false")) {
		return fmt.Errorf("%s must be boolean", label)
	}
	return nil
}

func decodeJSONObject(raw json.RawMessage, label string) (map[string]json.RawMessage, error) {
	if !jsonKind(raw, '{') {
		return nil, fmt.Errorf("%s must be an object", label)
	}
	var object map[string]json.RawMessage
	if err := json.Unmarshal(raw, &object); err != nil || object == nil {
		return nil, fmt.Errorf("%s must be an object", label)
	}
	return object, nil
}

func decodeJSONArray(raw json.RawMessage, label string) ([]json.RawMessage, error) {
	if !jsonKind(raw, '[') {
		return nil, fmt.Errorf("%s must be an array", label)
	}
	var items []json.RawMessage
	if err := json.Unmarshal(raw, &items); err != nil || items == nil {
		return nil, fmt.Errorf("%s must be an array", label)
	}
	return items, nil
}

func requireStringArray(raw json.RawMessage, label string) error {
	items, err := decodeJSONArray(raw, label)
	if err != nil {
		return err
	}
	for index, item := range items {
		if err := requireJSONString(item, fmt.Sprintf("%s[%d]", label, index)); err != nil {
			return err
		}
	}
	return nil
}

func checkRequiredShape(data []byte) error {
	var rootRaw json.RawMessage = data
	root, err := decodeJSONObject(rootRaw, "board")
	if err != nil {
		return err
	}
	rootKeys := []string{
		"schema_version", "board_id", "period", "max_turns", "phase_charges",
		"charge_cap", "boost_surcharge", "blocked_cost", "tether_limit",
		"tone_modulus", "rooms", "start", "goals", "edges", "tether_links",
		"beacons", "hidden_states", "initial_states",
	}
	if err := exactKeys(root, rootKeys); err != nil {
		return err
	}
	for _, name := range []string{"schema_version", "board_id"} {
		if err := requireJSONString(root[name], name); err != nil {
			return err
		}
	}
	for _, name := range []string{"period", "max_turns", "phase_charges", "charge_cap", "boost_surcharge", "blocked_cost", "tether_limit", "tone_modulus"} {
		if err := requireJSONInteger(root[name], name); err != nil {
			return err
		}
	}
	if err := requireStringArray(root["rooms"], "rooms"); err != nil {
		return err
	}
	if err := requireStringArray(root["initial_states"], "initial_states"); err != nil {
		return err
	}

	for _, name := range []string{"start", "goals"} {
		object, err := decodeJSONObject(root[name], name)
		if err != nil {
			return err
		}
		if err := exactKeys(object, []string{"amber", "cobalt"}); err != nil {
			return fmt.Errorf("%s: %w", name, err)
		}
		for _, field := range []string{"amber", "cobalt"} {
			if err := requireJSONString(object[field], name+"."+field); err != nil {
				return err
			}
		}
	}

	edges, err := decodeJSONArray(root["edges"], "edges")
	if err != nil {
		return err
	}
	for index, raw := range edges {
		label := fmt.Sprintf("edge %d", index)
		object, err := decodeJSONObject(raw, label)
		if err != nil {
			return err
		}
		if err := exactKeys(object, []string{"id", "actor", "from", "to", "cost", "phase_mask", "boostable", "gate", "tone"}); err != nil {
			return fmt.Errorf("%s: %w", label, err)
		}
		for _, field := range []string{"id", "actor", "from", "to", "phase_mask", "gate"} {
			if err := requireJSONString(object[field], label+"."+field); err != nil {
				return err
			}
		}
		for _, field := range []string{"cost", "tone"} {
			if err := requireJSONInteger(object[field], label+"."+field); err != nil {
				return err
			}
		}
		if err := requireJSONBool(object["boostable"], label+".boostable"); err != nil {
			return err
		}
	}

	links, err := decodeJSONArray(root["tether_links"], "tether_links")
	if err != nil {
		return err
	}
	for index, raw := range links {
		label := fmt.Sprintf("tether_links[%d]", index)
		items, err := decodeJSONArray(raw, label)
		if err != nil {
			return err
		}
		if len(items) != 2 {
			return fmt.Errorf("%s must contain two rooms", label)
		}
		for itemIndex, item := range items {
			if err := requireJSONString(item, fmt.Sprintf("%s[%d]", label, itemIndex)); err != nil {
				return err
			}
		}
	}

	beacons, err := decodeJSONArray(root["beacons"], "beacons")
	if err != nil {
		return err
	}
	for index, raw := range beacons {
		label := fmt.Sprintf("beacon %d", index)
		object, err := decodeJSONObject(raw, label)
		if err != nil {
			return err
		}
		if err := exactKeys(object, []string{"id", "room", "listen_cost", "tone"}); err != nil {
			return fmt.Errorf("%s: %w", label, err)
		}
		for _, field := range []string{"id", "room"} {
			if err := requireJSONString(object[field], label+"."+field); err != nil {
				return err
			}
		}
		for _, field := range []string{"listen_cost", "tone"} {
			if err := requireJSONInteger(object[field], label+"."+field); err != nil {
				return err
			}
		}
	}

	hiddenStates, err := decodeJSONArray(root["hidden_states"], "hidden_states")
	if err != nil {
		return err
	}
	for index, raw := range hiddenStates {
		label := fmt.Sprintf("hidden state %d", index)
		object, err := decodeJSONObject(raw, label)
		if err != nil {
			return err
		}
		if err := exactKeys(object, []string{"id", "world", "open_gates", "accepting", "signals", "next_by_tone"}); err != nil {
			return fmt.Errorf("%s: %w", label, err)
		}
		for _, field := range []string{"id", "world"} {
			if err := requireJSONString(object[field], label+"."+field); err != nil {
				return err
			}
		}
		if err := requireStringArray(object["open_gates"], label+".open_gates"); err != nil {
			return err
		}
		if err := requireJSONBool(object["accepting"], label+".accepting"); err != nil {
			return err
		}
		signals, err := decodeJSONObject(object["signals"], label+".signals")
		if err != nil {
			return err
		}
		for key, value := range signals {
			if err := requireJSONString(value, label+".signals."+key); err != nil {
				return err
			}
		}
		transitions, err := decodeJSONObject(object["next_by_tone"], label+".next_by_tone")
		if err != nil {
			return err
		}
		for key, value := range transitions {
			if err := requireStringArray(value, label+".next_by_tone."+key); err != nil {
				return err
			}
		}
	}
	return nil
}

func validToken(value string) bool {
	return tokenPattern.MatchString(value)
}

func compileBoard(board Board) (*compiledBoard, error) {
	if board.SchemaVersion != "phaseglass.board.v3" {
		return nil, errors.New("wrong schema_version")
	}
	if !validToken(board.BoardID) {
		return nil, errors.New("invalid board_id")
	}
	if board.Period < 2 || board.Period > 6 || board.MaxTurns < 0 || board.MaxTurns > 12 {
		return nil, errors.New("invalid period or max_turns")
	}
	if board.ChargeCap < 0 || board.ChargeCap > 6 || board.PhaseCharges < 0 || board.PhaseCharges > board.ChargeCap {
		return nil, errors.New("invalid charge values")
	}
	if board.BoostSurcharge < 0 || board.BlockedCost < 0 || board.TetherLimit <= 0 {
		return nil, errors.New("invalid cost or tether values")
	}
	if board.ToneModulus < 2 || board.ToneModulus > 4 {
		return nil, errors.New("invalid tone_modulus")
	}
	if len(board.Rooms) == 0 || len(board.Rooms) > 20 || len(board.HiddenStates) == 0 || len(board.HiddenStates) > 24 {
		return nil, errors.New("invalid room or hidden-state count")
	}
	roomIndex := make(map[string]int, len(board.Rooms))
	for i, room := range board.Rooms {
		if !validToken(room) {
			return nil, errors.New("invalid room ID")
		}
		if _, exists := roomIndex[room]; exists {
			return nil, errors.New("duplicate room ID")
		}
		roomIndex[room] = i
	}
	roomExists := func(room string) bool { _, ok := roomIndex[room]; return ok }
	for _, pair := range []Pair{board.Start, board.Goals} {
		if !roomExists(pair.Amber) || !roomExists(pair.Cobalt) || pair.Amber == pair.Cobalt {
			return nil, errors.New("invalid start or goal pair")
		}
	}
	for _, link := range board.TetherLinks {
		if len(link) != 2 || !roomExists(link[0]) || !roomExists(link[1]) || link[0] == link[1] {
			return nil, errors.New("invalid tether link")
		}
	}

	edgeByID := make(map[string]Edge)
	gateSet := make(map[string]bool)
	outgoing := [2]map[string][]Edge{make(map[string][]Edge), make(map[string][]Edge)}
	for _, edge := range board.Edges {
		if !validToken(edge.ID) || edgeByID[edge.ID].ID != "" {
			return nil, errors.New("invalid or duplicate edge ID")
		}
		if edge.Actor != "amber" && edge.Actor != "cobalt" && edge.Actor != "either" {
			return nil, errors.New("invalid edge actor")
		}
		if !roomExists(edge.From) || !roomExists(edge.To) || edge.From == edge.To || edge.Cost <= 0 {
			return nil, errors.New("invalid edge rooms or cost")
		}
		if len(edge.PhaseMask) != board.Period || strings.Trim(edge.PhaseMask, "01") != "" {
			return nil, errors.New("invalid phase_mask")
		}
		if edge.Gate != "" && !validToken(edge.Gate) {
			return nil, errors.New("invalid gate token")
		}
		if edge.Tone < 0 || edge.Tone >= board.ToneModulus {
			return nil, errors.New("invalid edge tone")
		}
		edgeByID[edge.ID] = edge
		if edge.Gate != "" {
			gateSet[edge.Gate] = true
		}
		if edge.Actor == "amber" || edge.Actor == "either" {
			outgoing[0][edge.From] = append(outgoing[0][edge.From], edge)
		}
		if edge.Actor == "cobalt" || edge.Actor == "either" {
			outgoing[1][edge.From] = append(outgoing[1][edge.From], edge)
		}
	}
	for actor := 0; actor < 2; actor++ {
		for room := range outgoing[actor] {
			sort.Slice(outgoing[actor][room], func(i, j int) bool { return outgoing[actor][room][i].ID < outgoing[actor][room][j].ID })
		}
	}

	beaconByID := make(map[string]Beacon)
	beaconsAtRoom := make(map[string][]Beacon)
	for _, beacon := range board.Beacons {
		if !validToken(beacon.ID) || beaconByID[beacon.ID].ID != "" || !roomExists(beacon.Room) || beacon.ListenCost < 0 || beacon.Tone < 0 || beacon.Tone >= board.ToneModulus {
			return nil, errors.New("invalid or duplicate beacon")
		}
		beaconByID[beacon.ID] = beacon
		beaconsAtRoom[beacon.Room] = append(beaconsAtRoom[beacon.Room], beacon)
	}
	for room := range beaconsAtRoom {
		sort.Slice(beaconsAtRoom[room], func(i, j int) bool { return beaconsAtRoom[room][i].ID < beaconsAtRoom[room][j].ID })
	}

	hiddenByID := make(map[string]HiddenState)
	worlds := make(map[string]bool)
	openGates := make(map[string]map[string]bool)
	for _, state := range board.HiddenStates {
		if !validToken(state.ID) || !validToken(state.World) || hiddenByID[state.ID].ID != "" {
			return nil, errors.New("invalid or duplicate hidden-state ID")
		}
		if len(state.Signals) != len(beaconByID) || len(state.NextByTone) != board.ToneModulus {
			return nil, errors.New("wrong hidden-state signal or transition key set")
		}
		for beaconID := range beaconByID {
			symbol, ok := state.Signals[beaconID]
			if !ok || !validToken(symbol) {
				return nil, errors.New("invalid or missing beacon signal")
			}
		}
		for key := range state.Signals {
			if _, ok := beaconByID[key]; !ok {
				return nil, errors.New("unknown beacon signal key")
			}
		}
		seenGate := make(map[string]bool)
		openGates[state.ID] = make(map[string]bool)
		for _, gate := range state.OpenGates {
			if !gateSet[gate] || seenGate[gate] {
				return nil, errors.New("unknown or duplicate open gate")
			}
			seenGate[gate] = true
			openGates[state.ID][gate] = true
		}
		for tone := 0; tone < board.ToneModulus; tone++ {
			if _, ok := state.NextByTone[strconv.Itoa(tone)]; !ok {
				return nil, errors.New("missing tone transition")
			}
		}
		for key := range state.NextByTone {
			value, err := strconv.Atoi(key)
			if err != nil || value < 0 || value >= board.ToneModulus {
				return nil, errors.New("invalid tone transition key")
			}
		}
		hiddenByID[state.ID] = state
		worlds[state.World] = true
	}
	for _, state := range board.HiddenStates {
		for tone := 0; tone < board.ToneModulus; tone++ {
			targetIDs := state.NextByTone[strconv.Itoa(tone)]
			if len(targetIDs) == 0 {
				return nil, errors.New("empty hidden transition set")
			}
			seenTarget := make(map[string]bool)
			for _, targetID := range targetIDs {
				target, ok := hiddenByID[targetID]
				if !ok || target.World != state.World || seenTarget[targetID] {
					return nil, errors.New("unknown, duplicate, or cross-world hidden transition")
				}
				seenTarget[targetID] = true
			}
		}
	}
	if len(board.InitialStates) != len(worlds) {
		return nil, errors.New("initial_states must contain one state per world")
	}
	initialSeen := make(map[string]bool)
	worldSeen := make(map[string]bool)
	for _, stateID := range board.InitialStates {
		state, ok := hiddenByID[stateID]
		if !ok || initialSeen[stateID] || worldSeen[state.World] {
			return nil, errors.New("invalid initial_states")
		}
		initialSeen[stateID] = true
		worldSeen[state.World] = true
	}
	for world := range worlds {
		if !worldSeen[world] {
			return nil, errors.New("missing initial world")
		}
	}

	dist := makeDistances(board, roomIndex)
	if dist[roomIndex[board.Start.Amber]][roomIndex[board.Start.Cobalt]] > board.TetherLimit {
		return nil, errors.New("initial tether violation")
	}
	initial := append([]string(nil), board.InitialStates...)
	sort.Strings(initial)
	board.InitialStates = initial
	return &compiledBoard{
		board:         board,
		roomIndex:     roomIndex,
		edgeByID:      edgeByID,
		beaconByID:    beaconByID,
		hiddenByID:    hiddenByID,
		openGates:     openGates,
		outgoing:      outgoing,
		beaconsAtRoom: beaconsAtRoom,
		dist:          dist,
	}, nil
}

func makeDistances(board Board, roomIndex map[string]int) [][]int {
	const inf = int(1e9)
	n := len(board.Rooms)
	dist := make([][]int, n)
	for i := range dist {
		dist[i] = make([]int, n)
		for j := range dist[i] {
			if i == j {
				dist[i][j] = 0
			} else {
				dist[i][j] = inf
			}
		}
	}
	for _, edge := range board.Edges {
		i, j := roomIndex[edge.From], roomIndex[edge.To]
		dist[i][j], dist[j][i] = 1, 1
	}
	for _, link := range board.TetherLinks {
		if len(link) != 2 {
			continue
		}
		i, okI := roomIndex[link[0]]
		j, okJ := roomIndex[link[1]]
		if okI && okJ && i != j {
			dist[i][j], dist[j][i] = 1, 1
		}
	}
	for k := 0; k < n; k++ {
		for i := 0; i < n; i++ {
			for j := 0; j < n; j++ {
				if dist[i][k]+dist[k][j] < dist[i][j] {
					dist[i][j] = dist[i][k] + dist[k][j]
				}
			}
		}
	}
	return dist
}

func solve(cb *compiledBoard) PolicyOut {
	initial := infoState{
		Tick:        0,
		Amber:       cb.board.Start.Amber,
		Cobalt:      cb.board.Start.Cobalt,
		ChargesLeft: cb.board.PhaseCharges,
		BoostsUsed:  0,
		Energy:      0,
		Belief:      append([]string(nil), cb.board.InitialStates...),
	}
	sim := &simulator{cb: cb, memo: make(map[string]memoEntry)}
	plans := sim.search(initial)
	var best *plan
	for _, candidate := range plans {
		if best == nil || betterPlan(candidate, best) {
			best = candidate
		}
	}
	if best == nil {
		return PolicyOut{
			SchemaVersion: "phaseglass.policy.v3",
			BoardID:       cb.board.BoardID,
			Status:        "unsolved",
			WorstTurns:    0,
			WorstBoosts:   0,
			WorstEnergy:   0,
			TotalTurns:    0,
			PolicyNodes:   0,
			Root:          "",
			Nodes:         []NodeOut{},
		}
	}
	nodes := buildNodes(initial, best)
	return PolicyOut{
		SchemaVersion: "phaseglass.policy.v3",
		BoardID:       cb.board.BoardID,
		Status:        "solved",
		WorstTurns:    best.WorstTurns,
		WorstBoosts:   best.WorstBoosts,
		WorstEnergy:   best.WorstEnergy,
		TotalTurns:    best.TotalTurns,
		PolicyNodes:   len(nodes),
		Root:          "N0",
		Nodes:         nodes,
	}
}

func stateKey(state infoState) string {
	return fmt.Sprintf("%d\x00%s\x00%s\x00%d\x00%d\x00%d\x00%s", state.Tick, state.Amber, state.Cobalt, state.ChargesLeft, state.BoostsUsed, state.Energy, strings.Join(state.Belief, "\x1f"))
}

func (sim *simulator) search(state infoState) []*plan {
	key := stateKey(state)
	if entry, ok := sim.memo[key]; ok && entry.Done {
		return entry.Plans
	}
	if sim.isTerminal(state) {
		worldTurns := make(map[string]int)
		for _, hiddenID := range state.Belief {
			worldTurns[sim.cb.hiddenByID[hiddenID].World] = state.Tick
		}
		result := &plan{
			Terminal:    true,
			WorstTurns:  state.Tick,
			WorstBoosts: state.BoostsUsed,
			WorstEnergy: state.Energy,
			TotalTurns:  state.Tick * len(worldTurns),
			WorldTurns:  worldTurns,
		}
		plans := []*plan{result}
		sim.memo[key] = memoEntry{Done: true, Plans: plans}
		return plans
	}
	if state.Tick >= sim.cb.board.MaxTurns {
		sim.memo[key] = memoEntry{Done: true, Plans: nil}
		return nil
	}

	amberOptions := sim.options(0, state.Amber, state.Tick%sim.cb.board.Period)
	cobaltOptions := sim.options(1, state.Cobalt, state.Tick%sim.cb.board.Period)
	frontier := []*plan{}
	for _, amberAction := range amberOptions {
		for _, cobaltAction := range cobaltOptions {
			if amberAction.Boost+cobaltAction.Boost > state.ChargesLeft {
				continue
			}
			groups, safe := sim.applyPair(state, amberAction, cobaltAction)
			if !safe {
				continue
			}
			observations := make([]string, 0, len(groups))
			for observation := range groups {
				observations = append(observations, observation)
			}
			sort.Strings(observations)

			type nextGroup struct {
				Key      string
				State    infoState
				Plans    []*plan
				Branches []string
			}
			unique := []nextGroup{}
			indexByKey := make(map[string]int)
			branchStates := make(map[string]infoState)
			valid := true
			for _, observation := range observations {
				outcome := groups[observation]
				next := infoState{
					Tick:        state.Tick + 1,
					Amber:       outcome.Amber,
					Cobalt:      outcome.Cobalt,
					ChargesLeft: outcome.ChargesLeft,
					BoostsUsed:  outcome.BoostsUsed,
					Energy:      outcome.Energy,
					Belief:      outcome.Belief,
				}
				branchStates[observation] = next
				nextKey := stateKey(next)
				if groupIndex, exists := indexByKey[nextKey]; exists {
					unique[groupIndex].Branches = append(unique[groupIndex].Branches, observation)
					continue
				}
				childPlans := sim.search(next)
				if len(childPlans) == 0 {
					valid = false
					break
				}
				indexByKey[nextKey] = len(unique)
				unique = append(unique, nextGroup{Key: nextKey, State: next, Plans: childPlans, Branches: []string{observation}})
			}
			if !valid {
				continue
			}

			selected := make(map[string]*plan)
			var enumerate func(int)
			enumerate = func(index int) {
				if index < len(unique) {
					group := unique[index]
					for _, child := range group.Plans {
						selected[group.Key] = child
						enumerate(index + 1)
					}
					delete(selected, group.Key)
					return
				}

				candidate := &plan{
					AmberAction:  amberAction.Label,
					CobaltAction: cobaltAction.Label,
					WorldTurns:   make(map[string]int),
				}
				for _, observation := range observations {
					next := branchStates[observation]
					child := selected[stateKey(next)]
					candidate.Branches = append(candidate.Branches, branchPlan{Observation: observation, State: next, Child: child})
					if child.WorstTurns > candidate.WorstTurns {
						candidate.WorstTurns = child.WorstTurns
					}
					if child.WorstBoosts > candidate.WorstBoosts {
						candidate.WorstBoosts = child.WorstBoosts
					}
					if child.WorstEnergy > candidate.WorstEnergy {
						candidate.WorstEnergy = child.WorstEnergy
					}
					for world, turn := range child.WorldTurns {
						if turn > candidate.WorldTurns[world] {
							candidate.WorldTurns[world] = turn
						}
					}
				}
				for _, turn := range candidate.WorldTurns {
					candidate.TotalTurns += turn
				}
				frontier = addPlanToFrontier(frontier, candidate)
			}
			enumerate(0)
		}
	}
	sim.memo[key] = memoEntry{Done: true, Plans: frontier}
	return frontier
}

// planDominates is deliberately profile-based instead of selecting one child-local
// winner. Parent branches aggregate maxima, so a locally slower child can still
// belong to the exact best complete root policy when another branch already sets
// the root limit. World-specific turn values preserve total_turns tradeoffs.
func planDominates(left, right *plan) bool {
	if left.WorstBoosts > right.WorstBoosts || left.WorstEnergy > right.WorstEnergy {
		return false
	}
	for world, rightTurn := range right.WorldTurns {
		leftTurn, exists := left.WorldTurns[world]
		if !exists || leftTurn > rightTurn {
			return false
		}
	}
	for world := range left.WorldTurns {
		if _, exists := right.WorldTurns[world]; !exists {
			return false
		}
	}
	return comparePolicy(left, right) <= 0
}

func addPlanToFrontier(frontier []*plan, candidate *plan) []*plan {
	for _, existing := range frontier {
		if planDominates(existing, candidate) {
			return frontier
		}
	}
	kept := frontier[:0]
	for _, existing := range frontier {
		if !planDominates(candidate, existing) {
			kept = append(kept, existing)
		}
	}
	return append(kept, candidate)
}

func (sim *simulator) isTerminal(state infoState) bool {
	if state.Amber != sim.cb.board.Goals.Amber || state.Cobalt != sim.cb.board.Goals.Cobalt {
		return false
	}
	for _, hiddenID := range state.Belief {
		if !sim.cb.hiddenByID[hiddenID].Accepting {
			return false
		}
	}
	return true
}

func actionRank(label string) (int, string) {
	if label == "wait" {
		return 0, ""
	}
	kind, id, _ := strings.Cut(label, ":")
	switch kind {
	case "listen":
		return 1, id
	case "move":
		return 2, id
	case "boost":
		return 3, id
	default:
		return 9, label
	}
}

func compareAction(left, right string) int {
	lr, li := actionRank(left)
	rr, ri := actionRank(right)
	if lr < rr {
		return -1
	}
	if lr > rr {
		return 1
	}
	return strings.Compare(li, ri)
}

func comparePolicy(left, right *plan) int {
	if left.Terminal || right.Terminal {
		if left.Terminal && right.Terminal {
			return 0
		}
		if left.Terminal {
			return -1
		}
		return 1
	}
	if cmp := compareAction(left.AmberAction, right.AmberAction); cmp != 0 {
		return cmp
	}
	if cmp := compareAction(left.CobaltAction, right.CobaltAction); cmp != 0 {
		return cmp
	}
	limit := len(left.Branches)
	if len(right.Branches) < limit {
		limit = len(right.Branches)
	}
	for i := 0; i < limit; i++ {
		if cmp := strings.Compare(left.Branches[i].Observation, right.Branches[i].Observation); cmp != 0 {
			return cmp
		}
		if cmp := comparePolicy(left.Branches[i].Child, right.Branches[i].Child); cmp != 0 {
			return cmp
		}
	}
	if len(left.Branches) < len(right.Branches) {
		return -1
	}
	if len(left.Branches) > len(right.Branches) {
		return 1
	}
	return 0
}

func betterPlan(candidate, incumbent *plan) bool {
	if candidate.WorstTurns != incumbent.WorstTurns {
		return candidate.WorstTurns < incumbent.WorstTurns
	}
	if candidate.WorstBoosts != incumbent.WorstBoosts {
		return candidate.WorstBoosts < incumbent.WorstBoosts
	}
	if candidate.WorstEnergy != incumbent.WorstEnergy {
		return candidate.WorstEnergy < incumbent.WorstEnergy
	}
	if candidate.TotalTurns != incumbent.TotalTurns {
		return candidate.TotalTurns < incumbent.TotalTurns
	}
	return comparePolicy(candidate, incumbent) < 0
}

func (sim *simulator) options(actor int, room string, phase int) []actionOption {
	options := []actionOption{{Label: "wait", Kind: 0, Tone: 0, SortRank: 0}}
	for _, beaconValue := range sim.cb.beaconsAtRoom[room] {
		beacon := beaconValue
		options = append(options, actionOption{Label: "listen:" + beacon.ID, Kind: 1, ID: beacon.ID, Tone: beacon.Tone, Beacon: &beacon, SortRank: 1})
	}
	for _, edgeValue := range sim.cb.outgoing[actor][room] {
		edge := edgeValue
		if edge.PhaseMask[phase] == '1' {
			options = append(options, actionOption{Label: "move:" + edge.ID, Kind: 2, ID: edge.ID, To: edge.To, Cost: edge.Cost, Tone: edge.Tone, Edge: &edge, SortRank: 2})
		} else if edge.Boostable {
			options = append(options, actionOption{Label: "boost:" + edge.ID, Kind: 3, ID: edge.ID, To: edge.To, Cost: edge.Cost, Tone: edge.Tone, Boost: 1, Edge: &edge, SortRank: 3})
		}
	}
	sort.Slice(options, func(i, j int) bool {
		if options[i].SortRank != options[j].SortRank {
			return options[i].SortRank < options[j].SortRank
		}
		return options[i].ID < options[j].ID
	})
	return options
}

func (sim *simulator) applyPiece(hidden HiddenState, option actionOption, room string) pieceResult {
	switch option.Kind {
	case 0:
		return pieceResult{Room: room, Component: "wait", ActionLabel: option.Label}
	case 1:
		symbol := hidden.Signals[option.Beacon.ID]
		return pieceResult{Room: room, Component: "signal:" + option.Beacon.ID + "=" + symbol, Energy: option.Beacon.ListenCost, Tone: option.Beacon.Tone, ActionLabel: option.Label}
	default:
		open := option.Edge.Gate == "" || sim.cb.openGates[hidden.ID][option.Edge.Gate]
		energy := option.Edge.Cost
		component := "moved:" + option.Edge.ID
		nextRoom := option.Edge.To
		if !open {
			energy = sim.cb.board.BlockedCost
			component = "blocked:" + option.Edge.ID
			nextRoom = room
		}
		if option.Boost == 1 {
			energy += sim.cb.board.BoostSurcharge
		}
		return pieceResult{Room: nextRoom, Component: component, Energy: energy, Tone: option.Edge.Tone, Boosts: option.Boost, ActionLabel: option.Label}
	}
}

func (sim *simulator) applyPair(state infoState, amberAction, cobaltAction actionOption) (map[string]groupedOutcome, bool) {
	groups := make(map[string]groupedOutcome)
	for _, hiddenID := range state.Belief {
		hidden := sim.cb.hiddenByID[hiddenID]
		amber := sim.applyPiece(hidden, amberAction, state.Amber)
		cobalt := sim.applyPiece(hidden, cobaltAction, state.Cobalt)
		if amber.Room == cobalt.Room || (amber.Room == state.Cobalt && cobalt.Room == state.Amber) {
			return nil, false
		}
		distance := sim.cb.dist[sim.cb.roomIndex[amber.Room]][sim.cb.roomIndex[cobalt.Room]]
		if distance > sim.cb.board.TetherLimit {
			return nil, false
		}
		jointTone := (amber.Tone + cobalt.Tone) % sim.cb.board.ToneModulus
		nextHiddenSet := hidden.NextByTone[strconv.Itoa(jointTone)]
		observation := "amber=" + amber.Component + ";cobalt=" + cobalt.Component
		outcome, exists := groups[observation]
		if !exists {
			outcome = groupedOutcome{
				Amber:       amber.Room,
				Cobalt:      cobalt.Room,
				ChargesLeft: state.ChargesLeft - amber.Boosts - cobalt.Boosts,
				BoostsUsed:  state.BoostsUsed + amber.Boosts + cobalt.Boosts,
				Energy:      state.Energy + amber.Energy + cobalt.Energy,
				Belief:      []string{},
			}
		} else if outcome.Amber != amber.Room || outcome.Cobalt != cobalt.Room || outcome.ChargesLeft != state.ChargesLeft-amber.Boosts-cobalt.Boosts || outcome.BoostsUsed != state.BoostsUsed+amber.Boosts+cobalt.Boosts || outcome.Energy != state.Energy+amber.Energy+cobalt.Energy {
			panic("observation does not determine visible successor")
		}
		outcome.Belief = append(outcome.Belief, nextHiddenSet...)
		groups[observation] = outcome
	}
	for observation, outcome := range groups {
		sort.Strings(outcome.Belief)
		deduped := outcome.Belief[:0]
		for _, hiddenID := range outcome.Belief {
			if len(deduped) == 0 || deduped[len(deduped)-1] != hiddenID {
				deduped = append(deduped, hiddenID)
			}
		}
		outcome.Belief = deduped
		groups[observation] = outcome
	}
	return groups, true
}

func buildNodes(rootState infoState, rootPlan *plan) []NodeOut {
	type queued struct {
		State infoState
		Plan  *plan
	}
	queue := []queued{{State: rootState, Plan: rootPlan}}
	ids := map[string]string{stateKey(rootState): "N0"}
	nodes := make([]NodeOut, 0)
	for head := 0; head < len(queue); head++ {
		item := queue[head]
		id := ids[stateKey(item.State)]
		node := NodeOut{
			ID:          id,
			Tick:        item.State.Tick,
			Amber:       item.State.Amber,
			Cobalt:      item.State.Cobalt,
			ChargesLeft: item.State.ChargesLeft,
			BoostsUsed:  item.State.BoostsUsed,
			Energy:      item.State.Energy,
			Belief:      append([]string(nil), item.State.Belief...),
			Terminal:    item.Plan.Terminal,
			Branches:    []BranchOut{},
		}
		if !item.Plan.Terminal {
			node.Action = &ActionOut{Amber: item.Plan.AmberAction, Cobalt: item.Plan.CobaltAction}
			for _, branch := range item.Plan.Branches {
				childKey := stateKey(branch.State)
				childID, exists := ids[childKey]
				if !exists {
					childID = "N" + strconv.Itoa(len(ids))
					ids[childKey] = childID
					queue = append(queue, queued{State: branch.State, Plan: branch.Child})
				}
				node.Branches = append(node.Branches, BranchOut{Observation: branch.Observation, Next: childID})
			}
		}
		nodes = append(nodes, node)
	}
	return nodes
}

func writePolicy(path string, policy PolicyOut) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetIndent("", "  ")
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(policy); err != nil {
		return err
	}
	return os.WriteFile(path, buffer.Bytes(), 0o644)
}
