package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

var identRE = regexp.MustCompile(`^[A-Za-z0-9_.-]+$`)

type Definition struct {
	Symbol  string
	Binding string
	Size    int
}

type Object struct {
	Unit       string
	Archive    string
	Order      int
	Comdat     string
	Defs       []Definition
	StrongRefs []string
	WeakRefs   []string
}

type Command struct {
	Kind string
	Arg  string
}

type Model struct {
	Objects   map[string]*Object
	Archives  map[string][]*Object
	Commands  []Command
	Canonical map[string]string
}

type ExtractedMember struct {
	Archive string `json:"archive"`
	Unit    string `json:"unit"`
}

type DiscardedUnit struct {
	Unit   string `json:"unit"`
	Reason string `json:"reason"`
}

type SymbolResult struct {
	Name     string `json:"name"`
	Provider string `json:"provider"`
	Binding  string `json:"binding"`
	Size     int    `json:"size"`
}

type LinkError struct {
	Kind   string `json:"kind"`
	Symbol string `json:"symbol"`
	First  string `json:"first"`
	Second string `json:"second"`
}

type Report struct {
	Version          int               `json:"version"`
	Status           string            `json:"status"`
	SelectedUnits    []string          `json:"selected_units"`
	ExtractedMembers []ExtractedMember `json:"extracted_members"`
	DiscardedUnits   []DiscardedUnit   `json:"discarded_units"`
	Symbols          []SymbolResult    `json:"symbols"`
	Unresolved       []string          `json:"unresolved"`
	Errors           []LinkError       `json:"errors"`
	PlanSHA256       string            `json:"plan_sha256"`
}

type Linker struct {
	model         *Model
	selected      []string
	extracted     []ExtractedMember
	discarded     []DiscardedUnit
	providers     map[string]SymbolResult
	unresolved    map[string]struct{}
	errors        []LinkError
	comdatOwner   map[string]string
	extractedUnit map[string]struct{}
}

func validIdent(value string) bool {
	return identRE.MatchString(value)
}

func readTSV(path string, header []string) ([][]string, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	reader := csv.NewReader(file)
	reader.Comma = '\t'
	reader.FieldsPerRecord = -1
	records, err := reader.ReadAll()
	if err != nil {
		return nil, err
	}
	if len(records) == 0 || len(records[0]) != len(header) {
		return nil, errors.New("missing or invalid header")
	}
	for index := range header {
		if records[0][index] != header[index] {
			return nil, errors.New("invalid header")
		}
	}
	for _, row := range records[1:] {
		if len(row) != len(header) {
			return nil, errors.New("wrong field count")
		}
	}
	return records[1:], nil
}

func loadAliases(dir string) (map[string]string, error) {
	rows, err := readTSV(filepath.Join(dir, "aliases.tsv"), []string{"alias", "target"})
	if err != nil {
		return nil, fmt.Errorf("aliases.tsv: %w", err)
	}
	direct := map[string]string{}
	for _, row := range rows {
		alias, target := row[0], row[1]
		if !validIdent(alias) || !validIdent(target) || alias == target {
			return nil, errors.New("aliases.tsv: invalid alias row")
		}
		if _, exists := direct[alias]; exists {
			return nil, errors.New("aliases.tsv: duplicate alias")
		}
		direct[alias] = target
	}

	canonical := map[string]string{}
	state := map[string]int{}
	var resolve func(string) (string, error)
	resolve = func(name string) (string, error) {
		if value, exists := canonical[name]; exists {
			return value, nil
		}
		if state[name] == 1 {
			return "", errors.New("aliases.tsv: alias cycle")
		}
		target, exists := direct[name]
		if !exists {
			canonical[name] = name
			return name, nil
		}
		state[name] = 1
		value, err := resolve(target)
		if err != nil {
			return "", err
		}
		state[name] = 2
		canonical[name] = value
		return value, nil
	}
	for alias := range direct {
		if _, err := resolve(alias); err != nil {
			return nil, err
		}
	}
	return canonical, nil
}

func canonicalName(canonical map[string]string, name string) string {
	if value, exists := canonical[name]; exists {
		return value
	}
	return name
}

func loadModel(dir string) (*Model, error) {
	canonical, err := loadAliases(dir)
	if err != nil {
		return nil, err
	}
	objectRows, err := readTSV(filepath.Join(dir, "objects.tsv"), []string{"unit", "archive", "order", "comdat"})
	if err != nil {
		return nil, fmt.Errorf("objects.tsv: %w", err)
	}

	model := &Model{
		Objects:   map[string]*Object{},
		Archives:  map[string][]*Object{},
		Canonical: canonical,
	}
	archiveOrders := map[string]map[int]struct{}{}
	for _, row := range objectRows {
		unit, archive, orderText, comdat := row[0], row[1], row[2], row[3]
		if !validIdent(unit) || (archive != "-" && !validIdent(archive)) || (comdat != "-" && !validIdent(comdat)) {
			return nil, errors.New("objects.tsv: invalid identifier")
		}
		if _, exists := model.Objects[unit]; exists {
			return nil, errors.New("objects.tsv: duplicate unit")
		}
		order, err := strconv.Atoi(orderText)
		if err != nil || order < 0 {
			return nil, errors.New("objects.tsv: invalid order")
		}
		if archive == "-" && order != 0 {
			return nil, errors.New("objects.tsv: loose object order must be 0")
		}
		if archive != "-" {
			if archiveOrders[archive] == nil {
				archiveOrders[archive] = map[int]struct{}{}
			}
			if _, exists := archiveOrders[archive][order]; exists {
				return nil, errors.New("objects.tsv: duplicate archive order")
			}
			archiveOrders[archive][order] = struct{}{}
		}
		object := &Object{Unit: unit, Archive: archive, Order: order, Comdat: comdat}
		model.Objects[unit] = object
		if archive != "-" {
			model.Archives[archive] = append(model.Archives[archive], object)
		}
	}
	if len(model.Objects) == 0 {
		return nil, errors.New("objects.tsv: no objects")
	}
	for archive := range model.Archives {
		sort.Slice(model.Archives[archive], func(i, j int) bool {
			if model.Archives[archive][i].Order != model.Archives[archive][j].Order {
				return model.Archives[archive][i].Order < model.Archives[archive][j].Order
			}
			return model.Archives[archive][i].Unit < model.Archives[archive][j].Unit
		})
	}

	symbolRows, err := readTSV(filepath.Join(dir, "symbols.tsv"), []string{"unit", "symbol", "kind", "binding", "size"})
	if err != nil {
		return nil, fmt.Errorf("symbols.tsv: %w", err)
	}
	seenUnitSymbol := map[string]struct{}{}
	for _, row := range symbolRows {
		unit, rawSymbol, kind, binding, sizeText := row[0], row[1], row[2], row[3], row[4]
		object := model.Objects[unit]
		if object == nil || !validIdent(rawSymbol) {
			return nil, errors.New("symbols.tsv: unknown unit or invalid symbol")
		}
		symbol := canonicalName(model.Canonical, rawSymbol)
		key := unit + "\x00" + symbol
		if _, exists := seenUnitSymbol[key]; exists {
			return nil, errors.New("symbols.tsv: duplicate canonical unit/symbol")
		}
		seenUnitSymbol[key] = struct{}{}
		size, err := strconv.Atoi(sizeText)
		if err != nil || size < 0 {
			return nil, errors.New("symbols.tsv: invalid size")
		}
		switch kind {
		case "REF", "WEAK_REF":
			if binding != "-" || size != 0 {
				return nil, errors.New("symbols.tsv: invalid reference row")
			}
			if kind == "REF" {
				object.StrongRefs = append(object.StrongRefs, symbol)
			} else {
				object.WeakRefs = append(object.WeakRefs, symbol)
			}
		case "DEF":
			if binding != "STRONG" && binding != "COMMON" && binding != "WEAK" {
				return nil, errors.New("symbols.tsv: invalid binding")
			}
			if binding == "COMMON" {
				if size <= 0 {
					return nil, errors.New("symbols.tsv: common size must be positive")
				}
			} else if size != 0 {
				return nil, errors.New("symbols.tsv: non-common size must be 0")
			}
			object.Defs = append(object.Defs, Definition{Symbol: symbol, Binding: binding, Size: size})
		default:
			return nil, errors.New("symbols.tsv: invalid kind")
		}
	}
	for _, object := range model.Objects {
		sort.Slice(object.Defs, func(i, j int) bool { return object.Defs[i].Symbol < object.Defs[j].Symbol })
		sort.Strings(object.StrongRefs)
		sort.Strings(object.WeakRefs)
	}

	commandFile, err := os.Open(filepath.Join(dir, "command.txt"))
	if err != nil {
		return nil, fmt.Errorf("command.txt: %w", err)
	}
	defer commandFile.Close()

	scanner := bufio.NewScanner(commandFile)
	inGroup := false
	inWhole := false
	usedUnits := map[string]struct{}{}
	usedArchives := map[string]struct{}{}
	usedNeeds := map[string]struct{}{}
	for scanner.Scan() {
		fields := strings.Fields(scanner.Text())
		if len(fields) == 0 {
			continue
		}
		switch fields[0] {
		case "OBJ":
			if len(fields) != 2 || inWhole {
				return nil, errors.New("command.txt: invalid OBJ directive")
			}
			object := model.Objects[fields[1]]
			if object == nil || object.Archive != "-" {
				return nil, errors.New("command.txt: OBJ must name a loose object")
			}
			if _, exists := usedUnits[fields[1]]; exists {
				return nil, errors.New("command.txt: duplicate OBJ")
			}
			usedUnits[fields[1]] = struct{}{}
			model.Commands = append(model.Commands, Command{Kind: "OBJ", Arg: fields[1]})
		case "ARC":
			if len(fields) != 2 {
				return nil, errors.New("command.txt: invalid ARC directive")
			}
			if _, exists := model.Archives[fields[1]]; !exists {
				return nil, errors.New("command.txt: unknown archive")
			}
			if _, exists := usedArchives[fields[1]]; exists {
				return nil, errors.New("command.txt: duplicate ARC")
			}
			usedArchives[fields[1]] = struct{}{}
			model.Commands = append(model.Commands, Command{Kind: "ARC", Arg: fields[1]})
		case "NEED":
			if len(fields) != 2 || inWhole || !validIdent(fields[1]) {
				return nil, errors.New("command.txt: invalid NEED directive")
			}
			symbol := canonicalName(model.Canonical, fields[1])
			if _, exists := usedNeeds[symbol]; exists {
				return nil, errors.New("command.txt: duplicate canonical NEED")
			}
			usedNeeds[symbol] = struct{}{}
			model.Commands = append(model.Commands, Command{Kind: "NEED", Arg: symbol})
		case "GROUP_BEGIN":
			if len(fields) != 1 || inGroup || inWhole {
				return nil, errors.New("command.txt: invalid GROUP_BEGIN")
			}
			inGroup = true
			model.Commands = append(model.Commands, Command{Kind: "GROUP_BEGIN"})
		case "GROUP_END":
			if len(fields) != 1 || !inGroup || inWhole {
				return nil, errors.New("command.txt: invalid GROUP_END")
			}
			inGroup = false
			model.Commands = append(model.Commands, Command{Kind: "GROUP_END"})
		case "WHOLE_BEGIN":
			if len(fields) != 1 || inGroup || inWhole {
				return nil, errors.New("command.txt: invalid WHOLE_BEGIN")
			}
			inWhole = true
			model.Commands = append(model.Commands, Command{Kind: "WHOLE_BEGIN"})
		case "WHOLE_END":
			if len(fields) != 1 || inGroup || !inWhole {
				return nil, errors.New("command.txt: invalid WHOLE_END")
			}
			inWhole = false
			model.Commands = append(model.Commands, Command{Kind: "WHOLE_END"})
		default:
			return nil, errors.New("command.txt: unknown directive")
		}
	}
	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("command.txt: %w", err)
	}
	if inGroup || inWhole {
		return nil, errors.New("command.txt: unclosed block")
	}
	if len(model.Commands) == 0 {
		return nil, errors.New("command.txt: no directives")
	}
	return model, nil
}

func bindingRank(binding string) int {
	switch binding {
	case "STRONG":
		return 3
	case "COMMON":
		return 2
	case "WEAK":
		return 1
	default:
		return 0
	}
}

func (linker *Linker) addNeed(symbol string) {
	if _, exists := linker.providers[symbol]; !exists {
		linker.unresolved[symbol] = struct{}{}
	}
}

func (linker *Linker) accept(object *Object, fromArchive bool) {
	if fromArchive {
		linker.extracted = append(linker.extracted, ExtractedMember{Archive: object.Archive, Unit: object.Unit})
	}
	if object.Comdat != "-" {
		if _, exists := linker.comdatOwner[object.Comdat]; exists {
			linker.discarded = append(linker.discarded, DiscardedUnit{Unit: object.Unit, Reason: "comdat:" + object.Comdat})
			return
		}
		linker.comdatOwner[object.Comdat] = object.Unit
	}

	linker.selected = append(linker.selected, object.Unit)
	for _, definition := range object.Defs {
		candidate := SymbolResult{Name: definition.Symbol, Provider: object.Unit, Binding: definition.Binding, Size: definition.Size}
		current, exists := linker.providers[definition.Symbol]
		if !exists {
			linker.providers[definition.Symbol] = candidate
		} else {
			currentRank := bindingRank(current.Binding)
			candidateRank := bindingRank(candidate.Binding)
			switch {
			case candidateRank > currentRank:
				linker.providers[definition.Symbol] = candidate
			case candidateRank < currentRank:
			case candidate.Binding == "STRONG":
				linker.errors = append(linker.errors, LinkError{
					Kind: "duplicate_strong", Symbol: definition.Symbol,
					First: current.Provider, Second: object.Unit,
				})
			case candidate.Binding == "COMMON" && candidate.Size > current.Size:
				linker.providers[definition.Symbol] = candidate
			}
		}
		delete(linker.unresolved, definition.Symbol)
	}
	for _, reference := range object.StrongRefs {
		linker.addNeed(reference)
	}
	// Weak references are deliberately recorded in the model but never create a need.
}

func (linker *Linker) memberNeeded(object *Object) bool {
	for _, definition := range object.Defs {
		if _, needed := linker.unresolved[definition.Symbol]; needed {
			return true
		}
	}
	return false
}

func (linker *Linker) scanArchive(name string, whole bool) int {
	count := 0
	for _, object := range linker.model.Archives[name] {
		if _, done := linker.extractedUnit[object.Unit]; done {
			continue
		}
		if whole || linker.memberNeeded(object) {
			linker.extractedUnit[object.Unit] = struct{}{}
			linker.accept(object, true)
			count++
		}
	}
	return count
}

func (linker *Linker) process() Report {
	for index := 0; index < len(linker.model.Commands); index++ {
		command := linker.model.Commands[index]
		switch command.Kind {
		case "OBJ":
			linker.accept(linker.model.Objects[command.Arg], false)
		case "ARC":
			linker.scanArchive(command.Arg, false)
		case "NEED":
			linker.addNeed(command.Arg)
		case "WHOLE_BEGIN":
			for index++; index < len(linker.model.Commands) && linker.model.Commands[index].Kind != "WHOLE_END"; index++ {
				linker.scanArchive(linker.model.Commands[index].Arg, true)
			}
		case "GROUP_BEGIN":
			group := []Command{}
			for index++; index < len(linker.model.Commands) && linker.model.Commands[index].Kind != "GROUP_END"; index++ {
				group = append(group, linker.model.Commands[index])
			}
			for _, item := range group {
				switch item.Kind {
				case "OBJ":
					linker.accept(linker.model.Objects[item.Arg], false)
				case "ARC":
					linker.scanArchive(item.Arg, false)
				case "NEED":
					linker.addNeed(item.Arg)
				}
			}
			for {
				extracted := 0
				for _, item := range group {
					if item.Kind == "ARC" {
						extracted += linker.scanArchive(item.Arg, false)
					}
				}
				if extracted == 0 {
					break
				}
			}
		}
	}

	symbols := make([]SymbolResult, 0, len(linker.providers))
	for _, symbol := range linker.providers {
		symbols = append(symbols, symbol)
	}
	sort.Slice(symbols, func(i, j int) bool { return symbols[i].Name < symbols[j].Name })

	unresolved := make([]string, 0, len(linker.unresolved))
	for name := range linker.unresolved {
		unresolved = append(unresolved, name)
	}
	sort.Strings(unresolved)

	sort.Slice(linker.errors, func(i, j int) bool {
		if linker.errors[i].Symbol != linker.errors[j].Symbol {
			return linker.errors[i].Symbol < linker.errors[j].Symbol
		}
		if linker.errors[i].First != linker.errors[j].First {
			return linker.errors[i].First < linker.errors[j].First
		}
		return linker.errors[i].Second < linker.errors[j].Second
	})

	status := "ok"
	if len(unresolved) > 0 || len(linker.errors) > 0 {
		status = "error"
	}
	report := Report{
		Version:          2,
		Status:           status,
		SelectedUnits:    linker.selected,
		ExtractedMembers: linker.extracted,
		DiscardedUnits:   linker.discarded,
		Symbols:          symbols,
		Unresolved:       unresolved,
		Errors:           linker.errors,
	}
	report.PlanSHA256 = planDigest(report)
	return report
}

func planDigest(report Report) string {
	var transcript strings.Builder
	fmt.Fprintf(&transcript, "version\t%d\n", report.Version)
	fmt.Fprintf(&transcript, "status\t%s\n", report.Status)
	for _, unit := range report.SelectedUnits {
		fmt.Fprintf(&transcript, "selected\t%s\n", unit)
	}
	for _, member := range report.ExtractedMembers {
		fmt.Fprintf(&transcript, "extracted\t%s\t%s\n", member.Archive, member.Unit)
	}
	for _, discarded := range report.DiscardedUnits {
		fmt.Fprintf(&transcript, "discarded\t%s\t%s\n", discarded.Unit, discarded.Reason)
	}
	for _, symbol := range report.Symbols {
		fmt.Fprintf(&transcript, "symbol\t%s\t%s\t%s\t%d\n", symbol.Name, symbol.Provider, symbol.Binding, symbol.Size)
	}
	for _, symbol := range report.Unresolved {
		fmt.Fprintf(&transcript, "unresolved\t%s\n", symbol)
	}
	for _, linkError := range report.Errors {
		fmt.Fprintf(&transcript, "error\t%s\t%s\t%s\t%s\n", linkError.Kind, linkError.Symbol, linkError.First, linkError.Second)
	}
	digest := sha256.Sum256([]byte(transcript.String()))
	return "sha256:" + hex.EncodeToString(digest[:])
}

func writeAtomic(path string, report Report) error {
	data, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	directory := filepath.Dir(path)
	temporary, err := os.CreateTemp(directory, ".arcplan-*.tmp")
	if err != nil {
		return err
	}
	temporaryName := temporary.Name()
	defer os.Remove(temporaryName)
	if _, err := temporary.Write(data); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Chmod(0644); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Close(); err != nil {
		return err
	}
	return os.Rename(temporaryName, path)
}

func failInvalid(output string, err error) {
	if output != "" {
		_ = os.Remove(output)
	}
	fmt.Fprintln(os.Stderr, "arcplan:", err)
	os.Exit(2)
}

func main() {
	if len(os.Args) != 3 {
		outputPath := ""
		if len(os.Args) >= 3 {
			outputPath = os.Args[2]
		}
		failInvalid(outputPath, errors.New("expected input directory and output path"))
	}
	inputDir, outputPath := os.Args[1], os.Args[2]
	_ = os.Remove(outputPath)

	model, err := loadModel(inputDir)
	if err != nil {
		failInvalid(outputPath, err)
	}
	linker := &Linker{
		model:         model,
		selected:      []string{},
		extracted:     []ExtractedMember{},
		discarded:     []DiscardedUnit{},
		errors:        []LinkError{},
		providers:     map[string]SymbolResult{},
		unresolved:    map[string]struct{}{},
		comdatOwner:   map[string]string{},
		extractedUnit: map[string]struct{}{},
	}
	report := linker.process()
	if err := writeAtomic(outputPath, report); err != nil {
		failInvalid(outputPath, err)
	}
	if report.Status == "error" {
		os.Exit(1)
	}
}
