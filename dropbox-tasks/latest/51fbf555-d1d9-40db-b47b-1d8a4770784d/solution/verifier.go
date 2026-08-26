package main

import (
	"bufio"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

type deadlineMiss struct {
	MissID      string   `json:"miss_id"`
	FlowID      string   `json:"flow_id"`
	MissType    string   `json:"miss_type"`
	Cycle       *int     `json:"cycle"`
	DeadlineUs  int      `json:"deadline_us"`
	LatencyUs   float64  `json:"latency_us"`
	MarginUs    float64  `json:"margin_us"`
	Description string   `json:"description"`
}

type gateConflict struct {
	ConflictID  string `json:"conflict_id"`
	SwitchID    string `json:"switch_id"`
	Port        string `json:"port"`
	WindowA     string `json:"window_a"`
	WindowB     string `json:"window_b"`
	OverlapNs   int    `json:"overlap_ns"`
	Description string `json:"description"`
}

func main() {
	policy := loadJSON(filepath.Join("/app/data", "validation_policy.json"))
	topology := loadJSON(filepath.Join("/app/data", policy["inputs"].(map[string]any)["topology"].(string)))
	schedulesDoc := loadJSON(filepath.Join("/app/data", policy["inputs"].(map[string]any)["gate_schedules"].(string)))
	trafficClasses := loadJSON(filepath.Join("/app/data", policy["inputs"].(map[string]any)["traffic_classes"].(string)))
	flowsDoc := loadJSON(filepath.Join("/app/data", policy["inputs"].(map[string]any)["message_flows"].(string)))
	clockSync := loadJSON(filepath.Join("/app/data", policy["inputs"].(map[string]any)["clock_sync"].(string)))
	profile := loadJSON(filepath.Join("/app/data", policy["inputs"].(map[string]any)["tsn_profile"].(string)))
	traces := loadJSONL(filepath.Join("/app/data", policy["inputs"].(map[string]any)["packet_traces"].(string)))

	templates := policy["description_templates"].(map[string]any)
	flows := flowsDoc["flows"].([]any)
	flowByID := map[string]map[string]any{}
	for _, raw := range flows {
		flow := raw.(map[string]any)
		flowByID[flow["flow_id"].(string)] = flow
	}

	toleranceUs := int(clockSync["tolerance_us"].(float64))
	grandmaster := clockSync["grandmaster"].(string)
	offsets := map[string]int{}
	for _, raw := range clockSync["offsets"].([]any) {
		row := raw.(map[string]any)
		offsets[row["node_id"].(string)] = int(row["offset_us"].(float64))
	}
	latencyDecimals := int(policy["trace_validation"].(map[string]any)["round_latency_us"].(float64))

	var misses []deadlineMiss
	sequence := 1

	activeFlows := []map[string]any{}
	eligibleFlows := []map[string]any{}
	for _, flow := range toFlowMaps(flows) {
		if flowEnabled(flow) {
			activeFlows = append(activeFlows, flow)
		}
		if flowAnalyticalEligible(flow) {
			eligibleFlows = append(eligibleFlows, flow)
		}
	}
	sortedFlows := append([]map[string]any{}, eligibleFlows...)
	sort.Slice(sortedFlows, func(i, j int) bool {
		return sortedFlows[i]["flow_id"].(string) < sortedFlows[j]["flow_id"].(string)
	})

	for _, flow := range sortedFlows {
		wcet := computeWCET(policy, topology, schedulesDoc, trafficClasses, profile, flow)
		deadline := int(flow["deadline_us"].(float64))
		compliance := complianceDeadlineUs(trafficClasses, flow)
		if wcet > float64(compliance) {
			misses = append(misses, deadlineMiss{
				MissID:      missID(policy, sequence),
				FlowID:      flow["flow_id"].(string),
				MissType:    "analytical",
				Cycle:       nil,
				DeadlineUs:  deadline,
				LatencyUs:   wcet,
				MarginUs:    round(float64(compliance)-wcet, latencyDecimals),
				Description: render(templates["analytical_miss"].(string), map[string]any{
					"wcet_us": wcet, "deadline_us": deadline, "flow_id": flow["flow_id"],
				}),
			})
			sequence++
		}
	}

	for _, trace := range traces {
		if !traceValidated(trace) {
			continue
		}
		flow := flowByID[trace["flow_id"].(string)]
		deadline := int(flow["deadline_us"].(float64))
		compliance := complianceDeadlineUs(trafficClasses, flow)
		raw := round(asFloat64(trace["arrival_us"])-asFloat64(trace["release_us"]), latencyDecimals)
		qualifiesObserved := raw > float64(compliance)
		qualifiesClockSkew := traceQualifiesClockSkew(trace, flow, trafficClasses, offsets, toleranceUs, grandmaster, topology, latencyDecimals)
		if qualifiesObserved && !qualifiesClockSkew {
			cycle := asInt(trace["cycle"])
			misses = append(misses, deadlineMiss{
				MissID:     missID(policy, sequence),
				FlowID:     flow["flow_id"].(string),
				MissType:   "observed",
				Cycle:      &cycle,
				DeadlineUs: deadline,
				LatencyUs:  raw,
				MarginUs:   round(float64(compliance)-raw, latencyDecimals),
				Description: render(templates["observed_miss"].(string), map[string]any{
					"latency_us": raw, "deadline_us": deadline, "flow_id": flow["flow_id"], "cycle": cycle,
				}),
			})
			sequence++
		}
	}

	for _, trace := range traces {
		if !traceValidated(trace) {
			continue
		}
		flow := flowByID[trace["flow_id"].(string)]
		deadline := int(flow["deadline_us"].(float64))
		compliance := complianceDeadlineUs(trafficClasses, flow)
		if traceQualifiesClockSkew(trace, flow, trafficClasses, offsets, toleranceUs, grandmaster, topology, latencyDecimals) {
			raw := traceRawLatencyUs(trace, latencyDecimals)
			skew := pathSkewExcess(flow, offsets, toleranceUs, grandmaster, topology)
			adjusted := round(raw+float64(skew)+float64(traceJitterUs(trace)), latencyDecimals)
			cycle := asInt(trace["cycle"])
			misses = append(misses, deadlineMiss{
				MissID:     missID(policy, sequence),
				FlowID:     flow["flow_id"].(string),
				MissType:   "clock_skew",
				Cycle:      &cycle,
				DeadlineUs: deadline,
				LatencyUs:  adjusted,
				MarginUs:   round(float64(compliance)-adjusted, latencyDecimals),
				Description: render(templates["clock_skew_miss"].(string), map[string]any{
					"adjusted_latency_us": adjusted, "deadline_us": deadline,
					"flow_id": flow["flow_id"], "trace_id": trace["trace_id"],
				}),
			})
			sequence++
		}
	}

	sort.Slice(misses, func(i, j int) bool {
		ci, cj := -1, -1
		if misses[i].Cycle != nil {
			ci = *misses[i].Cycle
		}
		if misses[j].Cycle != nil {
			cj = *misses[j].Cycle
		}
		ri := missTypeRank(policy, misses[i].MissType)
		rj := missTypeRank(policy, misses[j].MissType)
		if ri != rj {
			return ri < rj
		}
		if misses[i].FlowID != misses[j].FlowID {
			return misses[i].FlowID < misses[j].FlowID
		}
		return ci < cj
	})

	conflicts := detectGateConflicts(policy, schedulesDoc)
	inversions := detectPriorityInversions(policy, traces)

	periods := []int{}
	for _, flow := range eligibleFlows {
		periods = append(periods, int(flow["period_us"].(float64)))
	}
	hyperperiod := lcmList(periods)

	utilRows := buildUtilization(policy, topology, activeFlows, hyperperiod)

	analyticalFail := 0
	for _, flow := range eligibleFlows {
		if computeWCET(policy, topology, schedulesDoc, trafficClasses, profile, flow) > float64(complianceDeadlineUs(trafficClasses, flow)) {
			analyticalFail++
		}
	}
	validatedTraces := 0
	compliantTraces := 0
	for _, trace := range traces {
		if !traceValidated(trace) {
			continue
		}
		validatedTraces++
		flow := flowByID[trace["flow_id"].(string)]
		raw := round(asFloat64(trace["arrival_us"])-asFloat64(trace["release_us"]), latencyDecimals)
		if raw <= float64(complianceDeadlineUs(trafficClasses, flow)) {
			compliantTraces++
		}
	}
	headroomMin := math.MaxFloat64
	for _, row := range utilRows {
		headroom := asFloat64(row["available_mbps"]) - asFloat64(row["reserved_mbps"])
		if headroom < headroomMin {
			headroomMin = headroom
		}
	}
	syncNodes := 0
	compliantNodes := 0
	for _, raw := range clockSync["offsets"].([]any) {
		row := raw.(map[string]any)
		if row["node_id"].(string) == grandmaster {
			continue
		}
		syncNodes++
		if math.Abs(row["offset_us"].(float64)) <= float64(toleranceUs) {
			compliantNodes++
		}
	}

	metrics := map[string]any{
		"schedule_feasibility_score":   round(100*(1-float64(analyticalFail)/float64(len(eligibleFlows))), 2),
		"deadline_compliance_rate":     round(float64(compliantTraces)/float64(validatedTraces), 4),
		"bandwidth_headroom_min":       round(headroomMin, 3),
		"clock_sync_compliance_rate":   round(float64(compliantNodes)/float64(syncNodes), 4),
		"priority_inversion_count":     len(inversions),
	}

	networkID := topology["network_id"].(string)
	report := renderReport(policy, profile, metrics, misses, conflicts, inversions, utilRows)

	outputs := policy["outputs"].(map[string]any)
	writeText(filepath.Join("/app/output", outputs["schedule_validation_report"].(map[string]any)["path"].(string)), report)
	writeJSON(filepath.Join("/app/output", outputs["deadline_misses"].(map[string]any)["path"].(string)), map[string]any{
		"network_id": networkID,
		"misses":     missesToMaps(misses),
	})
	writeJSON(filepath.Join("/app/output", outputs["gate_conflicts"].(map[string]any)["path"].(string)), map[string]any{
		"network_id": networkID,
		"conflicts":  conflictsToMaps(conflicts),
	})
	writeText(filepath.Join("/app/output", outputs["network_utilization"].(map[string]any)["path"].(string)), utilCSV(policy, utilRows))
}

func loadJSON(path string) map[string]any {
	data, err := os.ReadFile(path)
	if err != nil {
		panic(err)
	}
	var doc map[string]any
	if err := json.Unmarshal(data, &doc); err != nil {
		panic(err)
	}
	return doc
}

func loadJSONL(path string) []map[string]any {
	file, err := os.Open(path)
	if err != nil {
		panic(err)
	}
	defer file.Close()
	var rows []map[string]any
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var row map[string]any
		if err := json.Unmarshal([]byte(line), &row); err != nil {
			panic(err)
		}
		rows = append(rows, row)
	}
	return rows
}

func toFlowMaps(flows []any) []map[string]any {
	out := make([]map[string]any, 0, len(flows))
	for _, raw := range flows {
		out = append(out, raw.(map[string]any))
	}
	return out
}

func asFloat64(value any) float64 {
	switch v := value.(type) {
	case float64:
		return v
	case int:
		return float64(v)
	case int64:
		return float64(v)
	case string:
		parsed, err := strconv.ParseFloat(v, 64)
		if err != nil {
			panic(err)
		}
		return parsed
	default:
		panic(fmt.Sprintf("expected numeric value, got %T", value))
	}
}

func asInt(value any) int {
	return int(asFloat64(value))
}

func round(value float64, decimals int) float64 {
	pow := math.Pow(10, float64(decimals))
	return math.Round(value*pow) / pow
}

func render(template string, values map[string]any) string {
	result := template
	for key, value := range values {
		result = strings.ReplaceAll(result, "{"+key+"}", formatTemplateValue(value))
	}
	return result
}

func formatTemplateValue(value any) string {
	switch v := value.(type) {
	case float64:
		if math.Mod(v, 1) == 0 {
			return fmt.Sprintf("%.1f", v)
		}
		s := fmt.Sprintf("%.3f", v)
		s = strings.TrimRight(s, "0")
		return strings.TrimRight(s, ".")
	case float32:
		return formatTemplateValue(float64(v))
	case int:
		return strconv.Itoa(v)
	default:
		return fmt.Sprint(value)
	}
}

func missTypeRank(policy map[string]any, missType string) int {
	order := policy["outputs"].(map[string]any)["deadline_misses"].(map[string]any)["miss_type_output_order"].([]any)
	for idx, raw := range order {
		if raw.(string) == missType {
			return idx
		}
	}
	panic("unknown miss_type: " + missType)
}

func missID(policy map[string]any, sequence int) string {
	cfg := policy["outputs"].(map[string]any)["deadline_misses"].(map[string]any)
	prefix := cfg["miss_id_prefix"].(string)
	sep := cfg["miss_id_separator"].(string)
	width := int(cfg["miss_id_sequence_width"].(float64))
	return fmt.Sprintf("%s%s%0*d", prefix, sep, width, sequence)
}

func conflictID(policy map[string]any, sequence int) string {
	cfg := policy["outputs"].(map[string]any)["gate_conflicts"].(map[string]any)
	prefix := cfg["conflict_id_prefix"].(string)
	sep := cfg["conflict_id_separator"].(string)
	width := int(cfg["conflict_id_sequence_width"].(float64))
	return fmt.Sprintf("%s%s%0*d", prefix, sep, width, sequence)
}

func queueForClass(trafficClasses map[string]any, classID string) int {
	for _, raw := range trafficClasses["classes"].([]any) {
		row := raw.(map[string]any)
		if row["class_id"].(string) == classID {
			return int(row["queue"].(float64))
		}
	}
	panic("class not found: " + classID)
}

func deadlineShavingUs(trafficClasses map[string]any, classID string) int {
	for _, raw := range trafficClasses["classes"].([]any) {
		row := raw.(map[string]any)
		if row["class_id"].(string) == classID {
			if shaving, ok := row["deadline_shaving_us"]; ok {
				return int(shaving.(float64))
			}
			return 0
		}
	}
	panic("class not found: " + classID)
}

func complianceDeadlineUs(trafficClasses map[string]any, flow map[string]any) int {
	return int(flow["deadline_us"].(float64)) - deadlineShavingUs(trafficClasses, flow["traffic_class"].(string))
}

func bandwidthFrameBytes(flow map[string]any) int {
	overhead := 0
	if raw, ok := flow["bandwidth_overhead_bytes"]; ok {
		overhead = int(raw.(float64))
	}
	return int(flow["frame_size_bytes"].(float64)) + overhead
}

func bandwidthReservedMbps(flow map[string]any) float64 {
	return reservedMbps(bandwidthFrameBytes(flow), int(flow["period_us"].(float64)), burstsPerPeriod(flow))
}

func queueGuardBandUs(schedule map[string]any, queue int) float64 {
	raw, ok := schedule["queue_guard_bands_us"]
	if !ok {
		return 0
	}
	bands := raw.(map[string]any)
	key := strconv.Itoa(queue)
	if value, found := bands[key]; found {
		return value.(float64)
	}
	return 0
}

func linkByNodes(topology map[string]any, upstream, downstream string) map[string]any {
	for _, raw := range topology["links"].([]any) {
		link := raw.(map[string]any)
		if link["from"].(string) == upstream && link["to"].(string) == downstream {
			return link
		}
	}
	panic(upstream + "->" + downstream)
}

func scheduleForSwitch(schedulesDoc map[string]any, switchID, port string) map[string]any {
	for _, raw := range schedulesDoc["schedules"].([]any) {
		row := raw.(map[string]any)
		if row["switch_id"].(string) == switchID && row["port"].(string) == port {
			return row
		}
	}
	return nil
}

func flowEnabled(flow map[string]any) bool {
	enabled, ok := flow["enabled"]
	if !ok {
		return true
	}
	if b, isBool := enabled.(bool); isBool {
		return b
	}
	return true
}

func traceValidated(trace map[string]any) bool {
	validate, ok := trace["validate"]
	if !ok {
		return true
	}
	if b, isBool := validate.(bool); isBool {
		return b
	}
	return true
}

func switchProcessingUs(topology map[string]any, nodeID string) float64 {
	return nodeProcessingUs(topology, nodeID)
}

func nodeProcessingUs(topology map[string]any, nodeID string) float64 {
	for _, raw := range topology["nodes"].([]any) {
		node := raw.(map[string]any)
		if node["node_id"].(string) == nodeID {
			if node["role"].(string) == "grandmaster" {
				return 0
			}
			if proc, ok := node["processing_us"]; ok {
				return proc.(float64)
			}
			return 0
		}
	}
	return 0
}

func burstsPerPeriod(flow map[string]any) int {
	if bursts, ok := flow["bursts_per_period"]; ok {
		return int(bursts.(float64))
	}
	return 1
}

func linkAvailableMbps(link map[string]any) float64 {
	derate := 1.0
	if raw, ok := link["derate_factor"]; ok {
		derate = raw.(float64)
	}
	return link["bandwidth_mbps"].(float64) * derate
}

func egressPortForHop(topology, schedulesDoc map[string]any, upstream, downstream string) string {
	link := linkByNodes(topology, upstream, downstream)
	if portsRaw, ok := link["switch_ports"]; ok {
		ports := portsRaw.(map[string]any)
		if portRaw, found := ports[upstream]; found {
			return portRaw.(string)
		}
	}
	for _, raw := range schedulesDoc["schedules"].([]any) {
		row := raw.(map[string]any)
		if row["switch_id"].(string) == upstream {
			return row["port"].(string)
		}
	}
	return ""
}

func transmissionUs(frameSize int, bandwidthMbps float64) float64 {
	return float64(frameSize) * 8 / bandwidthMbps
}

func reservedMbps(frameSize, periodUs, bursts int) float64 {
	return float64(frameSize) * 8 * float64(bursts) / float64(periodUs)
}

func openTimeNs(schedule map[string]any, queue, gateOpen int) int {
	total := 0
	for _, raw := range schedule["gate_control_list"].([]any) {
		interval := raw.(map[string]any)
		states := toIntSlice(interval["gate_states"].([]any))
		if states[queue] == gateOpen {
			total += int(interval["interval_ns"].(float64))
		}
	}
	return total
}

func gateWaitUs(schedule map[string]any, queue, cycleTimeNs, gateOpen int) float64 {
	openNs := openTimeNs(schedule, queue, gateOpen)
	return float64(cycleTimeNs-openNs)/1000.0 + queueGuardBandUs(schedule, queue)
}

func toIntSlice(values []any) []int {
	out := make([]int, len(values))
	for i, v := range values {
		out[i] = int(v.(float64))
	}
	return out
}

func toStringSlice(path []any) []string {
	out := make([]string, len(path))
	for i, v := range path {
		out[i] = v.(string)
	}
	return out
}

func computeWCET(policy, topology, schedulesDoc, trafficClasses, profile, flow map[string]any) float64 {
	path := toStringSlice(flow["path"].([]any))
	frameSize := int(flow["frame_size_bytes"].(float64))
	queue := queueForClass(trafficClasses, flow["traffic_class"].(string))
	gateOpen := int(profile["gate_open_value"].(float64))
	cycleTimeNs := int(schedulesDoc["cycle_time_ns"].(float64))

	total := 0.0
	for i := 0; i < len(path)-1; i++ {
		link := linkByNodes(topology, path[i], path[i+1])
		total += transmissionUs(frameSize, link["bandwidth_mbps"].(float64))
		total += link["propagation_us"].(float64)
	}
	for _, node := range path {
		total += nodeProcessingUs(topology, node)
	}
	for i := 0; i < len(path)-2; i++ {
		upstream := path[i+1]
		downstream := path[i+2]
		if !isSwitchNode(topology, upstream) {
			continue
		}
		port := egressPortForHop(topology, schedulesDoc, upstream, downstream)
		if port == "" {
			continue
		}
		schedule := scheduleForSwitch(schedulesDoc, upstream, port)
		if schedule != nil {
			total += gateWaitUs(schedule, queue, cycleTimeNs, gateOpen)
		}
	}
	total += interFrameGapPenaltyUs(flow)
	decimals := int(policy["deadline_analysis"].(map[string]any)["round_wcet_us"].(float64))
	return round(total, decimals)
}

func flowsOnLink(flows []map[string]any, topology map[string]any, linkID string) []map[string]any {
	var link map[string]any
	for _, raw := range topology["links"].([]any) {
		row := raw.(map[string]any)
		if row["link_id"].(string) == linkID {
			link = row
			break
		}
	}
	var matched []map[string]any
	for _, flow := range flows {
		if !flowEnabled(flow) {
			continue
		}
		path := toStringSlice(flow["path"].([]any))
		for i := 0; i < len(path)-1; i++ {
			if path[i] == link["from"].(string) && path[i+1] == link["to"].(string) {
				matched = append(matched, flow)
				break
			}
		}
	}
	return matched
}

func flowAnalyticalEligible(flow map[string]any) bool {
	if !flowEnabled(flow) {
		return false
	}
	if exempt, ok := flow["scheduling_exempt"]; ok {
		if b, isBool := exempt.(bool); isBool && b {
			return false
		}
	}
	return true
}

func traceJitterUs(trace map[string]any) int {
	if jitter, ok := trace["jitter_us"]; ok {
		return int(jitter.(float64))
	}
	return 0
}

func traceRawLatencyUs(trace map[string]any, decimals int) float64 {
	return round(asFloat64(trace["arrival_us"])-asFloat64(trace["release_us"]), decimals)
}

func traceQualifiesClockSkew(
	trace map[string]any,
	flow map[string]any,
	trafficClasses map[string]any,
	offsets map[string]int,
	toleranceUs int,
	grandmaster string,
	topology map[string]any,
	decimals int,
) bool {
	raw := traceRawLatencyUs(trace, decimals)
	skew := pathSkewExcess(flow, offsets, toleranceUs, grandmaster, topology)
	adjusted := round(raw+float64(skew)+float64(traceJitterUs(trace)), decimals)
	return skew > 0 && adjusted > float64(complianceDeadlineUs(trafficClasses, flow))
}

func interFrameGapPenaltyUs(flow map[string]any) float64 {
	bursts := burstsPerPeriod(flow)
	gap := 0.0
	if raw, ok := flow["inter_frame_gap_us"]; ok {
		gap = raw.(float64)
	}
	if bursts <= 1 {
		return 0
	}
	return gap * float64(bursts-1)
}

func isSwitchNode(topology map[string]any, nodeID string) bool {
	for _, raw := range topology["nodes"].([]any) {
		node := raw.(map[string]any)
		if node["node_id"].(string) == nodeID {
			return node["role"].(string) == "switch"
		}
	}
	return false
}

func pathSkewExcess(flow map[string]any, offsets map[string]int, toleranceUs int, grandmaster string, topology map[string]any) int {
	total := 0
	for _, node := range toStringSlice(flow["path"].([]any)) {
		if node == grandmaster || !isSwitchNode(topology, node) {
			continue
		}
		if offset, ok := offsets[node]; ok {
			excess := int(math.Abs(float64(offset))) - toleranceUs
			if excess > 0 {
				total += excess
			}
		}
	}
	return total
}

func detectGateConflicts(policy, schedulesDoc map[string]any) []gateConflict {
	templates := policy["description_templates"].(map[string]any)
	type pendingConflict struct {
		switchID, port, windowA, windowB, description string
		overlapNs                                     int
	}
	var pending []pendingConflict
	for _, raw := range schedulesDoc["schedules"].([]any) {
		schedule := raw.(map[string]any)
		windowsRaw, ok := schedule["reserved_windows"]
		if !ok {
			continue
		}
		windows := windowsRaw.([]any)
		for i := 0; i < len(windows); i++ {
			for j := i + 1; j < len(windows); j++ {
				a := windows[i].(map[string]any)
				b := windows[j].(map[string]any)
				if !a["exclusive"].(bool) || !b["exclusive"].(bool) {
					continue
				}
				startA := int(a["start_ns"].(float64))
				endA := startA + int(a["duration_ns"].(float64))
				startB := int(b["start_ns"].(float64))
				endB := startB + int(b["duration_ns"].(float64))
				overlap := int(math.Min(float64(endA), float64(endB))) - int(math.Max(float64(startA), float64(startB)))
				if overlap <= 0 {
					continue
				}
				pending = append(pending, pendingConflict{
					switchID: schedule["switch_id"].(string),
					port:     schedule["port"].(string),
					windowA:  a["window_id"].(string),
					windowB:  b["window_id"].(string),
					overlapNs: overlap,
					description: render(templates["gate_conflict"].(string), map[string]any{
						"window_a": a["window_id"], "window_b": b["window_id"], "overlap_ns": overlap,
						"switch_id": schedule["switch_id"], "port": schedule["port"],
					}),
				})
			}
		}
	}
	sort.Slice(pending, func(i, j int) bool {
		if pending[i].switchID != pending[j].switchID {
			return pending[i].switchID < pending[j].switchID
		}
		if pending[i].port != pending[j].port {
			return pending[i].port < pending[j].port
		}
		return pending[i].overlapNs > pending[j].overlapNs
	})
	conflicts := make([]gateConflict, 0, len(pending))
	for sequence, row := range pending {
		conflicts = append(conflicts, gateConflict{
			ConflictID:  conflictID(policy, sequence+1),
			SwitchID:    row.switchID,
			Port:        row.port,
			WindowA:     row.windowA,
			WindowB:     row.windowB,
			OverlapNs:   row.overlapNs,
			Description: row.description,
		})
	}
	return conflicts
}

func detectPriorityInversions(policy map[string]any, traces []map[string]any) []string {
	templates := policy["description_templates"].(map[string]any)
	grouped := map[string][]map[string]any{}
	for _, trace := range traces {
		if !traceValidated(trace) {
			continue
		}
		key := fmt.Sprintf("%s|%s|%d", trace["egress_node"], trace["egress_port"], asInt(trace["cycle"]))
		grouped[key] = append(grouped[key], trace)
	}
	type inversion struct {
		node, port string
		cycle      int
		lower, higher int
	}
	var found []inversion
	for _, rows := range grouped {
		for i := 0; i < len(rows); i++ {
			for j := i + 1; j < len(rows); j++ {
				a, b := rows[i], rows[j]
				qA := asInt(a["queue"])
				qB := asInt(b["queue"])
				if qA == qB {
					continue
				}
				var low, high map[string]any
				if qA < qB {
					low, high = a, b
				} else {
					low, high = b, a
				}
				lowTx := asInt(low["transmit_us"])
				highTx := asInt(high["transmit_us"])
				highRelease := asInt(high["release_us"])
				if lowTx < highTx && highRelease < lowTx {
					found = append(found, inversion{
						node: low["egress_node"].(string), port: low["egress_port"].(string),
						cycle: asInt(low["cycle"]), lower: asInt(low["queue"]),
						higher: asInt(high["queue"]),
					})
				}
			}
		}
	}
	sort.Slice(found, func(i, j int) bool {
		if found[i].node != found[j].node {
			return found[i].node < found[j].node
		}
		if found[i].port != found[j].port {
			return found[i].port < found[j].port
		}
		if found[i].cycle != found[j].cycle {
			return found[i].cycle < found[j].cycle
		}
		return found[i].lower < found[j].lower
	})
	var descriptions []string
	for _, inv := range found {
		descriptions = append(descriptions, render(templates["priority_inversion"].(string), map[string]any{
			"lower_queue": inv.lower, "higher_queue": inv.higher,
			"egress_node": inv.node, "egress_port": inv.port, "cycle": inv.cycle,
		}))
	}
	return descriptions
}

func gcd(a, b int) int {
	for b != 0 {
		a, b = b, a%b
	}
	return a
}

func lcm(a, b int) int {
	return a * b / gcd(a, b)
}

func lcmList(values []int) int {
	result := values[0]
	for _, v := range values[1:] {
		result = lcm(result, v)
	}
	return result
}

func buildUtilization(policy, topology map[string]any, flows []map[string]any, hyperperiod int) []map[string]any {
	reservedDecimals := int(policy["outputs"].(map[string]any)["network_utilization"].(map[string]any)["reserved_mbps_decimals"].(float64))
	ratioDecimals := int(policy["outputs"].(map[string]any)["network_utilization"].(map[string]any)["utilization_ratio_decimals"].(float64))

	links := append([]map[string]any{}, topologyLinks(topology)...)
	sort.Slice(links, func(i, j int) bool {
		return links[i]["link_id"].(string) < links[j]["link_id"].(string)
	})

	var rows []map[string]any
	for _, link := range links {
		available := linkAvailableMbps(link)
		reserved := 0.0
		for _, flow := range flowsOnLink(flows, topology, link["link_id"].(string)) {
			reserved += bandwidthReservedMbps(flow)
		}
		reserved = round(reserved, reservedDecimals)
		ratio := round(reserved/available, ratioDecimals)
		rows = append(rows, map[string]any{
			"link_id":           link["link_id"],
			"hyperperiod_us":    hyperperiod,
			"reserved_mbps":     reserved,
			"available_mbps":    int(available),
			"utilization_ratio": ratio,
			"overcommitted":     reserved > available,
		})
	}
	return rows
}

func topologyLinks(topology map[string]any) []map[string]any {
	var links []map[string]any
	for _, raw := range topology["links"].([]any) {
		links = append(links, raw.(map[string]any))
	}
	return links
}

func renderReport(policy map[string]any, profile map[string]any, metrics map[string]any, misses []deadlineMiss, conflicts []gateConflict, inversions []string, utilRows []map[string]any) string {
	cfg := policy["report_markdown"].(map[string]any)
	labels := policy["metrics"].(map[string]any)["report_metric_labels"].(map[string]any)
	var lines []string
	lines = append(lines, render(cfg["title"].(string), map[string]any{
		"profile_name": profile["profile_name"],
	}), "")
	lines = append(lines, cfg["metrics_section_heading"].(string), "")
	lines = append(lines, "| "+strings.Join(toIfaceStrings(cfg["metrics_table_headers"].([]any)), " | ")+" |")
	lines = append(lines, cfg["metrics_table_separator"].(string))
	metricKeys := []string{
		"schedule_feasibility_score",
		"deadline_compliance_rate",
		"bandwidth_headroom_min",
		"clock_sync_compliance_rate",
		"priority_inversion_count",
	}
	for _, key := range metricKeys {
		label := labels[key].(string)
		value := metrics[key]
		var rendered string
		if key == "priority_inversion_count" {
			rendered = fmt.Sprint(value)
		} else {
			decimals := int(policy["metrics"].(map[string]any)[key].(map[string]any)["round_decimals"].(float64))
			rendered = fmt.Sprintf("%.*f", decimals, asFloat64(value))
		}
		lines = append(lines, fmt.Sprintf("| %s | %s |", label, rendered))
	}
	lines = append(lines, "", cfg["deadline_summary_heading"].(string), "")
	for _, miss := range misses {
		lines = append(lines, fmt.Sprintf("- `%s` [%s] %s", miss.MissID, miss.MissType, miss.Description))
	}
	lines = append(lines, "", cfg["gate_conflict_heading"].(string), "")
	for _, conflict := range conflicts {
		lines = append(lines, fmt.Sprintf("- `%s` %s", conflict.ConflictID, conflict.Description))
	}
	lines = append(lines, "", cfg["priority_inversion_heading"].(string), "")
	for _, desc := range inversions {
		lines = append(lines, "- "+desc)
	}
	lines = append(lines, "", cfg["bandwidth_heading"].(string), "")
	for _, row := range utilRows {
		if cfg["bandwidth_include_overcommitted_only"].(bool) && !row["overcommitted"].(bool) {
			continue
		}
		lines = append(lines, fmt.Sprintf("- `%s` reserved %v Mbps / %v Mbps (overcommitted: %v)",
			row["link_id"], row["reserved_mbps"], row["available_mbps"], strings.ToLower(fmt.Sprint(row["overcommitted"]))))
	}
	return strings.Join(lines, "\n") + "\n"
}

func toIfaceStrings(values []any) []string {
	out := make([]string, len(values))
	for i, v := range values {
		out[i] = v.(string)
	}
	return out
}

type jsonFloat3 float64

func (f jsonFloat3) MarshalJSON() ([]byte, error) {
	v := float64(f)
	if math.Mod(v, 1) == 0 {
		return []byte(fmt.Sprintf("%.1f", v)), nil
	}
	s := fmt.Sprintf("%.3f", v)
	s = strings.TrimRight(s, "0")
	s = strings.TrimRight(s, ".")
	return []byte(s), nil
}

func missesToMaps(misses []deadlineMiss) []map[string]any {
	out := make([]map[string]any, 0, len(misses))
	for _, miss := range misses {
		row := map[string]any{
			"miss_id": miss.MissID, "flow_id": miss.FlowID, "miss_type": miss.MissType,
			"cycle": miss.Cycle, "deadline_us": miss.DeadlineUs,
			"latency_us": jsonFloat3(miss.LatencyUs),
			"margin_us": jsonFloat3(miss.MarginUs),
			"description": miss.Description,
		}
		out = append(out, row)
	}
	return out
}

func conflictsToMaps(conflicts []gateConflict) []map[string]any {
	out := make([]map[string]any, 0, len(conflicts))
	for _, conflict := range conflicts {
		out = append(out, map[string]any{
			"conflict_id": conflict.ConflictID, "switch_id": conflict.SwitchID, "port": conflict.Port,
			"window_a": conflict.WindowA, "window_b": conflict.WindowB, "overlap_ns": conflict.OverlapNs,
			"description": conflict.Description,
		})
	}
	return out
}

func utilCSV(policy map[string]any, rows []map[string]any) string {
	header := policy["outputs"].(map[string]any)["network_utilization"].(map[string]any)["header"].(string)
	var buf strings.Builder
	writer := csv.NewWriter(&buf)
	_ = writer.Write(strings.Split(header, ","))
	for _, row := range rows {
		_ = writer.Write([]string{
			row["link_id"].(string),
			strconv.Itoa(asInt(row["hyperperiod_us"])),
			fmt.Sprintf("%v", row["reserved_mbps"]),
			strconv.Itoa(asInt(row["available_mbps"])),
			fmt.Sprintf("%v", row["utilization_ratio"]),
			strings.ToLower(strconv.FormatBool(row["overcommitted"].(bool))),
		})
	}
	writer.Flush()
	return buf.String()
}

func writeText(path, content string) {
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		panic(err)
	}
}

func writeJSON(path string, value any) {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		panic(err)
	}
	data = append(data, '\n')
	if err := os.WriteFile(path, data, 0o644); err != nil {
		panic(err)
	}
}
