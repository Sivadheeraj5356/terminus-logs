package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

const (
	maxRowsPerFile       = 128
	maxSurvivingLots     = 12
	maxSurvivingFormulas = 16
	maxSurvivingOrders   = 8
	maxRequiredGrams     = 96
	maxLotsPerAllocation = 3
	maxLocalPlans        = 4096
	maxCohortPlans       = 2000000
)

type lot struct {
	LotID               string
	MaterialID          string
	Family              string
	Potency             int64
	Uncertainty         int64
	Grams               int64
	Prime               int64
	Expires             int64
	Stability           int64
	Status              string
	Cost                int64
	AssayGroup          string
	AssayDay            int64
	ValidThrough        int64
	Decay               int64
	UncertaintyGrow     int64
	VialGrams           int64
	MaxOpenCycles       int64
	OpenDecay           int64
	OpenUncertaintyGrow int64
	Events              []event
}

type assayMetadata struct {
	Group           string
	AssayDay        int64
	ValidThrough    int64
	Decay           int64
	UncertaintyGrow int64
}

type packageMetadata struct {
	VialGrams           int64
	MaxOpenCycles       int64
	OpenDecay           int64
	OpenUncertaintyGrow int64
}

type event struct {
	Kind     string
	Day      int64
	Grams    int64
	Sequence int
}

type formula struct {
	ProductID    string
	MaterialID   string
	GramsPerUnit int64
	MinRobust    int64
	Gamma        int64
	MaxLots      int64
	MixLoss      int64
	SubFamily    string
	SubPenalty   int64
}

type order struct {
	OrderID   string
	ProductID string
	Units     int64
	Day       int64
	Priority  string
	MaxCost   int64
}

type localPlan struct {
	Nominal               int64
	OpenDecayLoss         int64
	Deduction             int64
	OpenUncertaintyGrowth int64
	MixLoss               int64
	Robust                int64
	Margin                int64
	Cost                  int64
	SubGrams              int64
	Risk                  int64
	UsedLots              int64
	Key                   string
	Take                  []int64
}

type eligibleOrder struct {
	Order   order
	Formula formula
	Plans   []localPlan
}

type materialUsage struct {
	Drawn       int64
	PrimeCycles int64
	Primed      int64
	Waste       int64
	OpenedVials int64
	Consumed    int64
	Remaining   int64
	Opened      bool
	FirstDay    int64
	LastDay     int64
	Status      string
}

type usageProfile struct {
	Valid       bool
	Items       []materialUsage
	Adjusted    map[string]localPlan
	OpenedLots  int64
	PrimeCycles int64
	Waste       int64
	OpenedVials int64
}

type globalPlan struct {
	Valid       bool
	Counts      [3]int64
	Units       [3]int64
	Opened      int64
	PrimeCycles int64
	Waste       int64
	Cost        int64
	Deduction   int64
	SubGrams    int64
	Risk        int64
	Margin      int64
	Key         string
	Selected    map[string]localPlan
	Usage       usageProfile
}

type rejectionOut struct {
	OrderID string `json:"order_id"`
	Reason  string `json:"reason"`
}

type usedOut struct {
	LotID      string `json:"lot_id"`
	MaterialID string `json:"material_id"`
	Grams      int64  `json:"grams"`
}

type orderOut struct {
	OrderID               string    `json:"order_id"`
	ProductID             string    `json:"product_id"`
	Status                string    `json:"status"`
	Grams                 int64     `json:"grams"`
	Nominal               int64     `json:"nominal_potency_mg"`
	OpenDecayLoss         int64     `json:"open_decay_loss_mg"`
	Deduction             int64     `json:"uncertainty_deduction_mg"`
	OpenUncertaintyGrowth int64     `json:"open_uncertainty_growth_mg"`
	MixLoss               int64     `json:"mix_loss_mg"`
	Robust                int64     `json:"robust_potency_mg"`
	Margin                int64     `json:"robust_margin_mg"`
	Cost                  int64     `json:"cost_cents"`
	SubGrams              int64     `json:"substitute_grams"`
	Lots                  []usedOut `json:"lots"`
}

type materialOut struct {
	LotID       string `json:"lot_id"`
	Remaining   int64  `json:"remaining_grams"`
	PrimeCycles int64  `json:"prime_cycles"`
	Primed      int64  `json:"primed_grams"`
	Waste       int64  `json:"vial_waste_grams"`
	OpenedVials int64  `json:"opened_vial_count"`
	Opened      bool   `json:"opened"`
	FirstUseDay *int64 `json:"first_use_day"`
	LastUseDay  *int64 `json:"last_use_day"`
	Status      string `json:"status"`
}

type auditOut struct {
	Priority              string `json:"priority"`
	Eligible              int64  `json:"eligible_order_count"`
	Filled                int64  `json:"filled_order_count"`
	Units                 int64  `json:"filled_units"`
	Opened                int64  `json:"opened_lot_count"`
	PrimeCycles           int64  `json:"prime_cycle_count"`
	Waste                 int64  `json:"vial_waste_grams"`
	OpenedVials           int64  `json:"opened_vial_count"`
	Nominal               int64  `json:"nominal_potency_mg"`
	OpenDecayLoss         int64  `json:"open_decay_loss_mg"`
	Deduction             int64  `json:"uncertainty_deduction_mg"`
	OpenUncertaintyGrowth int64  `json:"open_uncertainty_growth_mg"`
	MixLoss               int64  `json:"mix_loss_mg"`
	Robust                int64  `json:"robust_potency_mg"`
	Margin                int64  `json:"robust_margin_mg"`
	Cost                  int64  `json:"total_cost_cents"`
	SubGrams              int64  `json:"substitute_grams"`
	Risk                  int64  `json:"expiry_risk"`
	AllocationKey         string `json:"allocation_key"`
}

type summaryOut struct {
	Filled                int64  `json:"filled_count"`
	Rejected              int64  `json:"rejected_count"`
	Cost                  int64  `json:"total_cost_cents"`
	Dispensed             int64  `json:"total_dispensed_grams"`
	PrimeCycles           int64  `json:"total_prime_cycles"`
	Prime                 int64  `json:"total_prime_grams"`
	Waste                 int64  `json:"total_vial_waste_grams"`
	OpenedVials           int64  `json:"total_opened_vials"`
	Opened                int64  `json:"opened_lot_count"`
	OpenDecayLoss         int64  `json:"total_open_decay_loss_mg"`
	OpenUncertaintyGrowth int64  `json:"total_open_uncertainty_growth_mg"`
	Margin                int64  `json:"robust_margin_mg"`
	Digest                string `json:"digest"`
}

type reportOut struct {
	Schema      string         `json:"schema"`
	InputDigest string         `json:"input_digest"`
	Orders      []orderOut     `json:"orders"`
	Rejections  []rejectionOut `json:"rejections"`
	Materials   []materialOut  `json:"materials"`
	Audit       []auditOut     `json:"cohort_audit"`
	Summary     summaryOut     `json:"summary"`
}

func fail(out string) {
	if out != "" {
		_ = os.Remove(out)
	}
	os.Exit(1)
}

func validateIdentifier(value, out string) string {
	if len(value) == 0 || len(value) > 64 {
		fail(out)
	}
	for _, r := range value {
		if (r >= 'A' && r <= 'Z') || (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '.' || r == '_' || r == '~' || r == '-' {
			continue
		}
		fail(out)
	}
	return value
}

func parseUint(value, out string, positive bool) int64 {
	if value == "" {
		fail(out)
	}
	for _, r := range value {
		if r < '0' || r > '9' {
			fail(out)
		}
	}
	parsed, err := strconv.ParseInt(value, 10, 64)
	if err != nil || parsed < 0 || (positive && parsed == 0) {
		fail(out)
	}
	return parsed
}

func parseCSV(raw []byte, header []string, out string) [][]string {
	reader := csv.NewReader(bytes.NewReader(raw))
	reader.FieldsPerRecord = -1
	rows, err := reader.ReadAll()
	if err != nil {
		fail(out)
	}
	clean := make([][]string, 0, len(rows))
	for _, row := range rows {
		if len(row) == 1 && strings.Trim(row[0], " \t") == "" {
			continue
		}
		clean = append(clean, row)
	}
	if len(clean) == 0 || len(clean[0]) != len(header) {
		fail(out)
	}
	for index := range header {
		if clean[0][index] != header[index] {
			fail(out)
		}
	}
	for _, row := range clean[1:] {
		if len(row) != len(header) {
			fail(out)
		}
	}
	if len(clean)-1 > maxRowsPerFile {
		fail(out)
	}
	return clean[1:]
}

func priorityRank(value, out string) int {
	switch value {
	case "urgent":
		return 0
	case "normal":
		return 1
	case "standby":
		return 2
	default:
		fail(out)
	}
	return 0
}

func betterLot(left, right *lot) bool {
	if left.Potency != right.Potency {
		return left.Potency > right.Potency
	}
	if left.Uncertainty != right.Uncertainty {
		return left.Uncertainty < right.Uncertainty
	}
	if left.Expires != right.Expires {
		return left.Expires < right.Expires
	}
	return left.MaterialID < right.MaterialID
}

func betterOrder(left, right order, out string) bool {
	leftRank := priorityRank(left.Priority, out)
	rightRank := priorityRank(right.Priority, out)
	if leftRank != rightRank {
		return leftRank < rightRank
	}
	if left.Units != right.Units {
		return left.Units > right.Units
	}
	if left.Day != right.Day {
		return left.Day < right.Day
	}
	return left.ProductID < right.ProductID
}

func requiredGrams(units, gramsPerUnit int64, out string) int64 {
	if units > maxRequiredGrams || gramsPerUnit > maxRequiredGrams {
		fail(out)
	}
	value := units * gramsPerUnit
	if value > maxRequiredGrams {
		fail(out)
	}
	return value
}

func ceilDiv(value, divisor int64) int64 {
	return (value + divisor - 1) / divisor
}

func allocationKey(lots []*lot, take []int64) string {
	parts := []string{}
	for index, grams := range take {
		if grams > 0 {
			parts = append(parts, fmt.Sprintf("%s:%d", lots[index].LotID, grams))
		}
	}
	return strings.Join(parts, ",")
}

func effectiveAssay(item *lot, day int64) (int64, int64) {
	age := day - item.AssayDay
	potency := item.Potency - age*item.Decay
	if potency < 0 {
		potency = 0
	}
	uncertainty := item.Uncertainty + age*item.UncertaintyGrow
	return potency, uncertainty
}

func applyEventState(grams int64, status string, item event) (int64, string) {
	switch item.Kind {
	case "loss":
		if item.Grams >= grams {
			grams = 0
		} else {
			grams -= item.Grams
		}
	case "restock":
		grams += item.Grams
	case "hold":
		status = "hold"
	case "release":
		status = "active"
	}
	return grams, status
}

func lotStateAt(item *lot, day int64) (int64, string) {
	grams := item.Grams
	status := item.Status
	for _, ev := range item.Events {
		if ev.Day <= day {
			grams, status = applyEventState(grams, status, ev)
		}
	}
	return grams, status
}

func planMetrics(lots []*lot, f formula, o order, take []int64, substitutes map[int]bool, openAges map[int]int64) localPlan {
	nominal := int64(0)
	openDecayLoss := int64(0)
	openUncertaintyGrowth := int64(0)
	groups := map[string]int64{}
	cost := int64(0)
	subGrams := int64(0)
	risk := int64(0)
	usedLots := int64(0)
	for index, amount := range take {
		if amount == 0 {
			continue
		}
		usedLots++
		item := lots[index]
		potency, uncertainty := effectiveAssay(item, o.Day)
		openAge := openAges[index]
		adjustedPotency := potency - openAge*item.OpenDecay
		if adjustedPotency < 0 {
			adjustedPotency = 0
		}
		adjustedUncertainty := uncertainty + openAge*item.OpenUncertaintyGrow
		nominal += amount * adjustedPotency
		openDecayLoss += amount * (potency - adjustedPotency)
		openUncertaintyGrowth += amount * (adjustedUncertainty - uncertainty)
		groups[item.AssayGroup] += amount * adjustedUncertainty
		cost += amount * item.Cost
		if substitutes[index] {
			cost += amount * f.SubPenalty
			subGrams += amount
		}
		risk += amount * (item.Expires - o.Day)
	}
	contributions := make([]int64, 0, len(groups))
	for _, value := range groups {
		contributions = append(contributions, value)
	}
	sort.Slice(contributions, func(i, j int) bool { return contributions[i] > contributions[j] })
	limit := int(f.Gamma)
	if limit > len(contributions) {
		limit = len(contributions)
	}
	deduction := int64(0)
	for index := 0; index < limit; index++ {
		deduction += contributions[index]
	}
	mixLoss := f.MixLoss * maxInt64(0, usedLots-1)
	robust := nominal - deduction - mixLoss
	if robust < 0 {
		robust = 0
	}
	target := o.Units * f.MinRobust
	copyTake := append([]int64(nil), take...)
	return localPlan{
		Nominal:               nominal,
		OpenDecayLoss:         openDecayLoss,
		Deduction:             deduction,
		OpenUncertaintyGrowth: openUncertaintyGrowth,
		MixLoss:               mixLoss,
		Robust:                robust,
		Margin:                robust - target,
		Cost:                  cost,
		SubGrams:              subGrams,
		Risk:                  risk,
		UsedLots:              usedLots,
		Key:                   allocationKey(lots, copyTake),
		Take:                  copyTake,
	}
}

func maxInt64(left, right int64) int64 {
	if left > right {
		return left
	}
	return right
}

func enumeratePlans(lots []*lot, f formula, o order, out string) []localPlan {
	type candidate struct {
		Index   int
		Maximum int64
	}
	need := requiredGrams(o.Units, f.GramsPerUnit, out)
	target := o.Units * f.MinRobust
	candidates := []candidate{}
	substitutes := map[int]bool{}
	for index, item := range lots {
		availableGrams, availableStatus := lotStateAt(item, o.Day)
		if availableStatus != "active" || availableGrams == 0 || item.Expires < o.Day {
			continue
		}
		if o.Day < item.AssayDay || o.Day > item.ValidThrough {
			continue
		}
		substitute := false
		if item.MaterialID == f.MaterialID {
		} else if f.SubFamily != "-" && item.Family == f.SubFamily {
			substitute = true
		} else {
			continue
		}
		usable := availableGrams / item.VialGrams * item.VialGrams
		maximum := usable - item.Prime
		if maximum <= 0 {
			continue
		}
		candidates = append(candidates, candidate{index, maximum})
		substitutes[index] = substitute
	}
	suffix := make([]int64, len(candidates)+1)
	for index := len(candidates) - 1; index >= 0; index-- {
		suffix[index] = suffix[index+1] + candidates[index].Maximum
	}
	take := make([]int64, len(lots))
	plans := []localPlan{}
	var visit func(int, int64, int64)
	visit = func(position int, grams, usedLots int64) {
		if grams > need || usedLots > f.MaxLots {
			return
		}
		if grams+suffix[position] < need {
			return
		}
		if position == len(candidates) {
			if grams != need {
				return
			}
			plan := planMetrics(lots, f, o, take, substitutes, nil)
			if plan.Robust >= target {
				plans = append(plans, plan)
				if len(plans) > maxLocalPlans {
					fail(out)
				}
			}
			return
		}
		item := candidates[position]
		take[item.Index] = 0
		visit(position+1, grams, usedLots)
		if usedLots < f.MaxLots {
			upper := item.Maximum
			if need-grams < upper {
				upper = need - grams
			}
			for amount := int64(1); amount <= upper; amount++ {
				take[item.Index] = amount
				visit(position+1, grams+amount, usedLots+1)
			}
		}
		take[item.Index] = 0
	}
	visit(0, 0, 0)
	sort.Slice(plans, func(i, j int) bool {
		left := plans[i]
		right := plans[j]
		if left.UsedLots != right.UsedLots {
			return left.UsedLots < right.UsedLots
		}
		if left.Cost != right.Cost {
			return left.Cost < right.Cost
		}
		if left.Deduction != right.Deduction {
			return left.Deduction < right.Deduction
		}
		if left.SubGrams != right.SubGrams {
			return left.SubGrams < right.SubGrams
		}
		if left.Risk != right.Risk {
			return left.Risk < right.Risk
		}
		if left.Margin != right.Margin {
			return left.Margin > right.Margin
		}
		return left.Key < right.Key
	})
	return plans
}

func cohortKey(selected map[string]localPlan) string {
	ids := make([]string, 0, len(selected))
	for id := range selected {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	parts := make([]string, 0, len(ids))
	for _, id := range ids {
		parts = append(parts, id+"="+selected[id].Key)
	}
	return strings.Join(parts, ";")
}

func computeUsage(lots []*lot, selected map[string]localPlan, eligibleByID map[string]eligibleOrder) usageProfile {
	type episode struct {
		Start    int64
		End      int64
		Draw     int64
		Consumed int64
		Waste    int64
	}
	uses := make([]map[int64]int64, len(lots))
	openAges := make([]map[int64]int64, len(lots))
	for index := range uses {
		uses[index] = map[int64]int64{}
		openAges[index] = map[int64]int64{}
	}
	for orderID, plan := range selected {
		item := eligibleByID[orderID]
		for index, amount := range plan.Take {
			if amount > 0 {
				uses[index][item.Order.Day] += amount
			}
		}
	}
	profile := usageProfile{Valid: true, Items: make([]materialUsage, len(lots)), Adjusted: map[string]localPlan{}}
	for index, item := range lots {
		days := make([]int64, 0, len(uses[index]))
		for day := range uses[index] {
			days = append(days, day)
		}
		sort.Slice(days, func(i, j int) bool { return days[i] < days[j] })
		episodes := []episode{}
		position := 0
		for position < len(days) {
			start := days[position]
			end := start
			draw := int64(0)
			for position < len(days) && days[position] <= start+item.Stability {
				day := days[position]
				end = day
				draw += uses[index][day]
				openAges[index][day] = day - start
				position++
			}
			consumed := ceilDiv(draw+item.Prime, item.VialGrams) * item.VialGrams
			episodes = append(episodes, episode{Start: start, End: end, Draw: draw, Consumed: consumed, Waste: consumed - draw - item.Prime})
		}
		usage := materialUsage{Remaining: item.Grams, Status: item.Status}
		byStart := map[int64]episode{}
		daySet := map[int64]bool{}
		for _, ep := range episodes {
			byStart[ep.Start] = ep
			daySet[ep.Start] = true
			usage.PrimeCycles++
			usage.Drawn += ep.Draw
			usage.Primed += item.Prime
			usage.Waste += ep.Waste
			usage.OpenedVials += ep.Consumed / item.VialGrams
			usage.Consumed += ep.Consumed
			if !usage.Opened {
				usage.Opened = true
				usage.FirstDay = ep.Start
			}
			usage.LastDay = ep.End
		}
		for _, ev := range item.Events {
			daySet[ev.Day] = true
		}
		timeline := make([]int64, 0, len(daySet))
		for day := range daySet {
			timeline = append(timeline, day)
		}
		sort.Slice(timeline, func(i, j int) bool { return timeline[i] < timeline[j] })
		if usage.PrimeCycles > item.MaxOpenCycles {
			profile.Valid = false
		}
		for _, day := range timeline {
			for _, ev := range item.Events {
				if ev.Day == day {
					usage.Remaining, usage.Status = applyEventState(usage.Remaining, usage.Status, ev)
				}
			}
			if ep, ok := byStart[day]; ok {
				if ep.Consumed > usage.Remaining {
					profile.Valid = false
				}
				usage.Remaining -= ep.Consumed
				if usage.Remaining < 0 {
					usage.Remaining = 0
				}
			}
		}
		profile.Items[index] = usage
		if usage.Opened {
			profile.OpenedLots++
		}
		profile.PrimeCycles += usage.PrimeCycles
		profile.Waste += usage.Waste
		profile.OpenedVials += usage.OpenedVials
	}
	for orderID, plan := range selected {
		item := eligibleByID[orderID]
		ages := map[int]int64{}
		substitutes := map[int]bool{}
		for index, amount := range plan.Take {
			if amount > 0 {
				ages[index] = openAges[index][item.Order.Day]
				substitutes[index] = lots[index].MaterialID != item.Formula.MaterialID
			}
		}
		adjusted := planMetrics(lots, item.Formula, item.Order, plan.Take, substitutes, ages)
		profile.Adjusted[orderID] = adjusted
		if adjusted.Margin < 0 {
			profile.Valid = false
		}
	}
	return profile
}

func betterGlobal(candidate, best globalPlan) bool {
	if !best.Valid {
		return true
	}
	for rank := 0; rank < 3; rank++ {
		if candidate.Counts[rank] != best.Counts[rank] {
			return candidate.Counts[rank] > best.Counts[rank]
		}
		if candidate.Units[rank] != best.Units[rank] {
			return candidate.Units[rank] > best.Units[rank]
		}
	}
	if candidate.Opened != best.Opened {
		return candidate.Opened < best.Opened
	}
	if candidate.PrimeCycles != best.PrimeCycles {
		return candidate.PrimeCycles < best.PrimeCycles
	}
	if candidate.Waste != best.Waste {
		return candidate.Waste < best.Waste
	}
	if candidate.Cost != best.Cost {
		return candidate.Cost < best.Cost
	}
	if candidate.Deduction != best.Deduction {
		return candidate.Deduction < best.Deduction
	}
	if candidate.SubGrams != best.SubGrams {
		return candidate.SubGrams < best.SubGrams
	}
	if candidate.Risk != best.Risk {
		return candidate.Risk < best.Risk
	}
	if candidate.Margin != best.Margin {
		return candidate.Margin > best.Margin
	}
	return candidate.Key < best.Key
}

func copySelected(selected map[string]localPlan) map[string]localPlan {
	result := make(map[string]localPlan, len(selected))
	for key, value := range selected {
		result[key] = value
	}
	return result
}

func chooseGlobal(lots []*lot, eligible []eligibleOrder, out string) globalPlan {
	eligibleByID := map[string]eligibleOrder{}
	for _, item := range eligible {
		eligibleByID[item.Order.OrderID] = item
	}
	selected := map[string]localPlan{}
	best := globalPlan{}
	var visit func(int, [3]int64, [3]int64)
	visit = func(position int, counts, units [3]int64) {
		if position == len(eligible) {
			usage := computeUsage(lots, selected, eligibleByID)
			if !usage.Valid {
				return
			}
			cost := int64(0)
			deduction := int64(0)
			subGrams := int64(0)
			risk := int64(0)
			margin := int64(0)
			for _, plan := range usage.Adjusted {
				cost += plan.Cost
				deduction += plan.Deduction
				subGrams += plan.SubGrams
				risk += plan.Risk
				margin += plan.Margin
			}
			candidate := globalPlan{
				Valid:       true,
				Counts:      counts,
				Units:       units,
				Opened:      usage.OpenedLots,
				PrimeCycles: usage.PrimeCycles,
				Waste:       usage.Waste,
				Cost:        cost,
				Deduction:   deduction,
				SubGrams:    subGrams,
				Risk:        risk,
				Margin:      margin,
				Key:         cohortKey(usage.Adjusted),
				Selected:    copySelected(usage.Adjusted),
				Usage:       usage,
			}
			if betterGlobal(candidate, best) {
				best = candidate
			}
			return
		}
		item := eligible[position]
		rank := priorityRank(item.Order.Priority, out)
		for _, plan := range item.Plans {
			selected[item.Order.OrderID] = plan
			usage := computeUsage(lots, selected, eligibleByID)
			if usage.Valid {
				nextCounts := counts
				nextUnits := units
				nextCounts[rank]++
				nextUnits[rank] += item.Order.Units
				visit(position+1, nextCounts, nextUnits)
			}
			delete(selected, item.Order.OrderID)
		}
		visit(position+1, counts, units)
	}
	visit(0, [3]int64{}, [3]int64{})
	return best
}

func inputDigest(names []string, raw map[string][]byte) string {
	hash := sha256.New()
	for _, name := range names {
		_, _ = hash.Write([]byte(name))
		_, _ = hash.Write([]byte{0})
		_, _ = hash.Write([]byte(strconv.Itoa(len(raw[name]))))
		_, _ = hash.Write([]byte{0})
		_, _ = hash.Write(raw[name])
		_, _ = hash.Write([]byte{0})
	}
	return hex.EncodeToString(hash.Sum(nil))
}

func main() {
	outPath := ""
	if len(os.Args) >= 3 {
		outPath = os.Args[2]
	}
	if len(os.Args) != 3 {
		fail(outPath)
	}
	inputRoot := os.Args[1]
	names := []string{"lots.csv", "assays.csv", "packaging.csv", "formulas.csv", "orders.csv", "events.csv"}
	raw := map[string][]byte{}
	for _, name := range names {
		content, err := os.ReadFile(filepath.Join(inputRoot, name))
		if err != nil {
			fail(outPath)
		}
		raw[name] = content
	}
	lotsRows := parseCSV(raw["lots.csv"], []string{"lot_id", "material_id", "family", "potency_mg_per_g", "uncertainty_mg_per_g", "grams", "prime_grams", "expires_day", "open_stability_days", "status", "cost_cents_per_g"}, outPath)
	assayRows := parseCSV(raw["assays.csv"], []string{"lot_id", "assay_group", "assay_day", "valid_through_day", "decay_mg_per_g_per_day", "uncertainty_growth_mg_per_g_per_day"}, outPath)
	packageRows := parseCSV(raw["packaging.csv"], []string{"lot_id", "vial_grams", "max_open_cycles", "open_decay_mg_per_g_per_day", "open_uncertainty_growth_mg_per_g_per_day"}, outPath)
	formulaRows := parseCSV(raw["formulas.csv"], []string{"product_id", "required_material_id", "grams_per_unit", "min_robust_potency_mg_per_unit", "uncertainty_budget", "max_lots", "mix_loss_mg_per_extra_lot", "substitute_family", "substitution_penalty_cents_per_g"}, outPath)
	orderRows := parseCSV(raw["orders.csv"], []string{"order_id", "product_id", "units", "requested_day", "priority", "max_cost_cents"}, outPath)
	eventRows := parseCSV(raw["events.csv"], []string{"lot_id", "kind", "day", "grams"}, outPath)

	lotsMap := map[string]*lot{}
	for _, row := range lotsRows {
		if row[9] != "active" && row[9] != "hold" {
			fail(outPath)
		}
		item := &lot{
			LotID:       validateIdentifier(row[0], outPath),
			MaterialID:  validateIdentifier(row[1], outPath),
			Family:      validateIdentifier(row[2], outPath),
			Potency:     parseUint(row[3], outPath, false),
			Uncertainty: parseUint(row[4], outPath, false),
			Grams:       parseUint(row[5], outPath, false),
			Prime:       parseUint(row[6], outPath, false),
			Expires:     parseUint(row[7], outPath, false),
			Stability:   parseUint(row[8], outPath, false),
			Status:      row[9],
			Cost:        parseUint(row[10], outPath, false),
		}
		old := lotsMap[item.LotID]
		if old == nil || betterLot(item, old) {
			lotsMap[item.LotID] = item
		}
	}
	if len(lotsMap) > maxSurvivingLots {
		fail(outPath)
	}
	assays := map[string]assayMetadata{}
	for _, row := range assayRows {
		lotID := validateIdentifier(row[0], outPath)
		item := assayMetadata{
			Group:           validateIdentifier(row[1], outPath),
			AssayDay:        parseUint(row[2], outPath, false),
			ValidThrough:    parseUint(row[3], outPath, false),
			Decay:           parseUint(row[4], outPath, false),
			UncertaintyGrow: parseUint(row[5], outPath, false),
		}
		if item.ValidThrough < item.AssayDay {
			fail(outPath)
		}
		assays[lotID] = item
	}
	packages := map[string]packageMetadata{}
	for _, row := range packageRows {
		lotID := validateIdentifier(row[0], outPath)
		packages[lotID] = packageMetadata{
			VialGrams:           parseUint(row[1], outPath, true),
			MaxOpenCycles:       parseUint(row[2], outPath, true),
			OpenDecay:           parseUint(row[3], outPath, false),
			OpenUncertaintyGrow: parseUint(row[4], outPath, false),
		}
	}
	for id, item := range lotsMap {
		assay, ok := assays[id]
		if !ok {
			fail(outPath)
		}
		pack, ok := packages[id]
		if !ok {
			fail(outPath)
		}
		item.AssayGroup = assay.Group
		item.AssayDay = assay.AssayDay
		item.ValidThrough = assay.ValidThrough
		item.Decay = assay.Decay
		item.UncertaintyGrow = assay.UncertaintyGrow
		item.VialGrams = pack.VialGrams
		item.MaxOpenCycles = pack.MaxOpenCycles
		item.OpenDecay = pack.OpenDecay
		item.OpenUncertaintyGrow = pack.OpenUncertaintyGrow
	}
	for sequence, row := range eventRows {
		lotID := validateIdentifier(row[0], outPath)
		kind := row[1]
		day := parseUint(row[2], outPath, false)
		grams := parseUint(row[3], outPath, false)
		if kind != "loss" && kind != "restock" && kind != "hold" && kind != "release" {
			fail(outPath)
		}
		item := lotsMap[lotID]
		if item == nil {
			continue
		}
		item.Events = append(item.Events, event{Kind: kind, Day: day, Grams: grams, Sequence: sequence})
	}
	for _, item := range lotsMap {
		sort.Slice(item.Events, func(i, j int) bool {
			if item.Events[i].Day != item.Events[j].Day {
				return item.Events[i].Day < item.Events[j].Day
			}
			return item.Events[i].Sequence < item.Events[j].Sequence
		})
	}
	formulas := map[string]formula{}
	for _, row := range formulaRows {
		item := formula{
			ProductID:    validateIdentifier(row[0], outPath),
			MaterialID:   validateIdentifier(row[1], outPath),
			GramsPerUnit: parseUint(row[2], outPath, true),
			MinRobust:    parseUint(row[3], outPath, false),
			Gamma:        parseUint(row[4], outPath, false),
			MaxLots:      parseUint(row[5], outPath, true),
			MixLoss:      parseUint(row[6], outPath, false),
			SubFamily:    validateIdentifier(row[7], outPath),
			SubPenalty:   parseUint(row[8], outPath, false),
		}
		if item.MaxLots > maxLotsPerAllocation {
			fail(outPath)
		}
		formulas[item.ProductID] = item
	}
	if len(formulas) > maxSurvivingFormulas {
		fail(outPath)
	}
	ordersMap := map[string]order{}
	for _, row := range orderRows {
		item := order{
			OrderID:   validateIdentifier(row[0], outPath),
			ProductID: validateIdentifier(row[1], outPath),
			Units:     parseUint(row[2], outPath, true),
			Day:       parseUint(row[3], outPath, false),
			Priority:  row[4],
			MaxCost:   parseUint(row[5], outPath, false),
		}
		_ = priorityRank(item.Priority, outPath)
		old, exists := ordersMap[item.OrderID]
		if !exists || betterOrder(item, old, outPath) {
			ordersMap[item.OrderID] = item
		}
	}
	if len(ordersMap) > maxSurvivingOrders {
		fail(outPath)
	}
	lotIDs := make([]string, 0, len(lotsMap))
	for id := range lotsMap {
		lotIDs = append(lotIDs, id)
	}
	sort.Strings(lotIDs)
	lots := make([]*lot, 0, len(lotIDs))
	for _, id := range lotIDs {
		lots = append(lots, lotsMap[id])
	}
	orders := make([]order, 0, len(ordersMap))
	for _, item := range ordersMap {
		orders = append(orders, item)
	}
	sort.Slice(orders, func(i, j int) bool {
		leftRank := priorityRank(orders[i].Priority, outPath)
		rightRank := priorityRank(orders[j].Priority, outPath)
		if leftRank != rightRank {
			return leftRank < rightRank
		}
		if orders[i].Day != orders[j].Day {
			return orders[i].Day < orders[j].Day
		}
		return orders[i].OrderID < orders[j].OrderID
	})
	rejections := []rejectionOut{}
	eligible := []eligibleOrder{}
	cohortPlanCount := int64(1)
	for _, item := range orders {
		f, exists := formulas[item.ProductID]
		if !exists {
			rejections = append(rejections, rejectionOut{item.OrderID, "UNKNOWN_PRODUCT"})
			continue
		}
		_ = requiredGrams(item.Units, f.GramsPerUnit, outPath)
		plans := enumeratePlans(lots, f, item, outPath)
		if len(plans) == 0 {
			rejections = append(rejections, rejectionOut{item.OrderID, "NO_MATERIAL"})
			continue
		}
		budgetPlans := []localPlan{}
		for _, plan := range plans {
			if plan.Cost <= item.MaxCost {
				budgetPlans = append(budgetPlans, plan)
			}
		}
		if len(budgetPlans) == 0 {
			rejections = append(rejections, rejectionOut{item.OrderID, "OVER_BUDGET"})
			continue
		}
		factor := int64(len(budgetPlans) + 1)
		if cohortPlanCount > maxCohortPlans/factor {
			fail(outPath)
		}
		cohortPlanCount *= factor
		eligible = append(eligible, eligibleOrder{item, f, budgetPlans})
	}
	winning := chooseGlobal(lots, eligible, outPath)
	eligibleByID := map[string]eligibleOrder{}
	for _, item := range eligible {
		eligibleByID[item.Order.OrderID] = item
	}
	filled := []orderOut{}
	for _, item := range eligible {
		plan, selected := winning.Selected[item.Order.OrderID]
		if !selected {
			rejections = append(rejections, rejectionOut{item.Order.OrderID, "DEFERRED_CAPACITY"})
			continue
		}
		uses := []usedOut{}
		for index, amount := range plan.Take {
			if amount > 0 {
				uses = append(uses, usedOut{lots[index].LotID, lots[index].MaterialID, amount})
			}
		}
		filled = append(filled, orderOut{
			OrderID:               item.Order.OrderID,
			ProductID:             item.Order.ProductID,
			Status:                "FILLED",
			Grams:                 item.Order.Units * item.Formula.GramsPerUnit,
			Nominal:               plan.Nominal,
			OpenDecayLoss:         plan.OpenDecayLoss,
			Deduction:             plan.Deduction,
			OpenUncertaintyGrowth: plan.OpenUncertaintyGrowth,
			MixLoss:               plan.MixLoss,
			Robust:                plan.Robust,
			Margin:                plan.Margin,
			Cost:                  plan.Cost,
			SubGrams:              plan.SubGrams,
			Lots:                  uses,
		})
	}
	sort.Slice(filled, func(i, j int) bool {
		left := ordersMap[filled[i].OrderID]
		right := ordersMap[filled[j].OrderID]
		leftRank := priorityRank(left.Priority, outPath)
		rightRank := priorityRank(right.Priority, outPath)
		if leftRank != rightRank {
			return leftRank < rightRank
		}
		if left.Day != right.Day {
			return left.Day < right.Day
		}
		return left.OrderID < right.OrderID
	})
	sort.Slice(rejections, func(i, j int) bool { return rejections[i].OrderID < rejections[j].OrderID })
	materials := make([]materialOut, 0, len(lots))
	for index, item := range lots {
		usage := winning.Usage.Items[index]
		var first *int64
		var last *int64
		if usage.Opened {
			firstValue := usage.FirstDay
			lastValue := usage.LastDay
			first = &firstValue
			last = &lastValue
		}
		materials = append(materials, materialOut{
			LotID:       item.LotID,
			Remaining:   usage.Remaining,
			PrimeCycles: usage.PrimeCycles,
			Primed:      usage.Primed,
			Waste:       usage.Waste,
			OpenedVials: usage.OpenedVials,
			Opened:      usage.Opened,
			FirstUseDay: first,
			LastUseDay:  last,
			Status:      usage.Status,
		})
	}
	priorities := []string{"urgent", "normal", "standby"}
	audits := []auditOut{}
	for _, priority := range priorities {
		selectedForPriority := map[string]localPlan{}
		audit := auditOut{Priority: priority}
		for _, item := range eligible {
			if item.Order.Priority != priority {
				continue
			}
			audit.Eligible++
			plan, selected := winning.Selected[item.Order.OrderID]
			if !selected {
				continue
			}
			selectedForPriority[item.Order.OrderID] = plan
			audit.Filled++
			audit.Units += item.Order.Units
			audit.Nominal += plan.Nominal
			audit.OpenDecayLoss += plan.OpenDecayLoss
			audit.Deduction += plan.Deduction
			audit.OpenUncertaintyGrowth += plan.OpenUncertaintyGrowth
			audit.MixLoss += plan.MixLoss
			audit.Robust += plan.Robust
			audit.Margin += plan.Margin
			audit.Cost += plan.Cost
			audit.SubGrams += plan.SubGrams
			audit.Risk += plan.Risk
		}
		profile := computeUsage(lots, selectedForPriority, eligibleByID)
		audit.Opened = profile.OpenedLots
		audit.PrimeCycles = profile.PrimeCycles
		audit.Waste = profile.Waste
		audit.OpenedVials = profile.OpenedVials
		audit.AllocationKey = cohortKey(selectedForPriority)
		audits = append(audits, audit)
	}
	digestValue := inputDigest(names, raw)
	summary := summaryOut{
		Filled:   int64(len(filled)),
		Rejected: int64(len(rejections)),
	}
	for _, item := range filled {
		summary.Cost += item.Cost
		summary.Dispensed += item.Grams
		summary.OpenDecayLoss += item.OpenDecayLoss
		summary.OpenUncertaintyGrowth += item.OpenUncertaintyGrowth
		summary.Margin += item.Margin
	}
	for _, item := range materials {
		summary.PrimeCycles += item.PrimeCycles
		summary.Prime += item.Primed
		summary.Waste += item.Waste
		summary.OpenedVials += item.OpenedVials
		if item.Opened {
			summary.Opened++
		}
	}
	rows := []string{"I|" + digestValue}
	for _, item := range audits {
		rows = append(rows, fmt.Sprintf(
			"A|%s|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%s",
			item.Priority,
			item.Eligible,
			item.Filled,
			item.Units,
			item.Opened,
			item.PrimeCycles,
			item.Waste,
			item.OpenedVials,
			item.Nominal,
			item.OpenDecayLoss,
			item.Deduction,
			item.OpenUncertaintyGrowth,
			item.MixLoss,
			item.Robust,
			item.Margin,
			item.Cost,
			item.SubGrams,
			item.Risk,
			item.AllocationKey,
		))
	}
	for _, item := range filled {
		keyParts := []string{}
		for _, use := range item.Lots {
			keyParts = append(keyParts, fmt.Sprintf("%s:%d", use.LotID, use.Grams))
		}
		rows = append(rows, fmt.Sprintf(
			"F|%s|%d|%d|%d|%d|%d|%d|%d|%d|%d|%s",
			item.OrderID,
			item.Cost,
			item.Nominal,
			item.OpenDecayLoss,
			item.Deduction,
			item.OpenUncertaintyGrowth,
			item.MixLoss,
			item.Robust,
			item.Margin,
			item.SubGrams,
			strings.Join(keyParts, ","),
		))
	}
	for _, item := range rejections {
		rows = append(rows, fmt.Sprintf("R|%s|%s", item.OrderID, item.Reason))
	}
	for _, item := range materials {
		openedValue := "false"
		firstValue := "-"
		lastValue := "-"
		if item.Opened {
			openedValue = "true"
			firstValue = strconv.FormatInt(*item.FirstUseDay, 10)
			lastValue = strconv.FormatInt(*item.LastUseDay, 10)
		}
		rows = append(rows, fmt.Sprintf(
			"M|%s|%d|%d|%d|%d|%d|%s|%s|%s|%s",
			item.LotID,
			item.Remaining,
			item.PrimeCycles,
			item.Primed,
			item.Waste,
			item.OpenedVials,
			openedValue,
			firstValue,
			lastValue,
			item.Status,
		))
	}
	hash := sha256.Sum256([]byte(strings.Join(rows, "\n") + "\n"))
	summary.Digest = hex.EncodeToString(hash[:])
	result := reportOut{
		Schema:      "amberglass.v6",
		InputDigest: digestValue,
		Orders:      filled,
		Rejections:  rejections,
		Materials:   materials,
		Audit:       audits,
		Summary:     summary,
	}
	encoded, marshalErr := json.MarshalIndent(result, "", "  ")
	if marshalErr != nil {
		fail(outPath)
	}
	if writeErr := os.WriteFile(outPath, append(encoded, '\n'), 0644); writeErr != nil {
		fail(outPath)
	}
}
