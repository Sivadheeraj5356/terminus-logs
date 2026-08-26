// Package engine implements the endpoint over-limit protection alarm ledger.
//
// Run parses the JSON scenario, validates it (including the per-endpoint service
// window structure), and computes the deterministic per-endpoint ledger.
// Parsing, validation, the per-endpoint timeline construction,
// and output assembly are already complete; only computeEndpoint needs the real
// state machine.
package engine

import (
	"encoding/json"
	"errors"
	"fmt"
	"sort"
)

type inEndpoint struct {
	Name   *string `json:"name"`
	Limit  *int    `json:"limit"`
	Arm    *int    `json:"arm"`
	Reset  *int    `json:"reset"`
	Budget *int    `json:"budget"`
}

type inSample struct {
	T       *int    `json:"t"`
	Endpoint *string `json:"endpoint"`
	Latency    *int    `json:"latency"`
	Type    *string `json:"type"`
}

type inDoc struct {
	Until    *int        `json:"until"`
	Endpoints []inEndpoint `json:"endpoints"`
	Samples []inSample `json:"samples"`
}

// Alarm is a confirmed over-limit interval [Start, End).
type Alarm struct {
	Start int `json:"start"`
	End   int `json:"end"`
}

// Final reports a endpoint's state at the horizon.
type Final struct {
	State string `json:"state"`
	Since int    `json:"since"`
}

// OutEndpoint is one endpoint's ledger entry.
type OutEndpoint struct {
	Name        string      `json:"name"`
	Alarms  []Alarm `json:"alarms"`
	OverSeconds int         `json:"alarm_seconds"`
	LockedAt   *int        `json:"locked_at"`
	Final       Final       `json:"final"`
}

// OutDoc is the full ledger.
type OutDoc struct {
	Endpoints []OutEndpoint `json:"endpoints"`
}

type cfg struct {
	limit, arm, reset, budget int
}

type evKind int

const (
	evSample evKind = iota
	evService
	evEndService
)

// event is one entry on a endpoint's timeline.
type event struct {
	t    int
	kind evKind
	latency int // valid only for evSample
}

// Run parses, validates, and evaluates the scenario.
func Run(data []byte) (OutDoc, error) {
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(data, &raw); err != nil {
		return OutDoc{}, err
	}
	var doc inDoc
	if err := json.Unmarshal(data, &doc); err != nil {
		return OutDoc{}, err
	}
	if _, ok := raw["endpoints"]; !ok {
		return OutDoc{}, errors.New("endpoints must be an array")
	}
	if _, ok := raw["samples"]; !ok {
		return OutDoc{}, errors.New("samples must be an array")
	}

	endpoints := map[string]cfg{}
	for _, p := range doc.Endpoints {
		if p.Name == nil || *p.Name == "" {
			return OutDoc{}, errors.New("endpoint name must be a non-empty string")
		}
		if _, ok := endpoints[*p.Name]; ok {
			return OutDoc{}, fmt.Errorf("duplicate endpoint %s", *p.Name)
		}
		if p.Limit == nil || p.Arm == nil || p.Reset == nil || p.Budget == nil {
			return OutDoc{}, errors.New("endpoint missing a required field")
		}
		if *p.Arm < 0 || *p.Reset < 0 || *p.Budget < 0 {
			return OutDoc{}, errors.New("arm, reset, and budget must be non-negative")
		}
		endpoints[*p.Name] = cfg{*p.Limit, *p.Arm, *p.Reset, *p.Budget}
	}

	per := map[string][]event{}
	for n := range endpoints {
		per[n] = nil
	}
	haveMax := false
	maxT := 0
	for _, r := range doc.Samples {
		if r.T == nil || r.Endpoint == nil {
			return OutDoc{}, errors.New("sample missing a required field")
		}
		if *r.T < 0 {
			return OutDoc{}, errors.New("sample t must be non-negative")
		}
		if _, ok := endpoints[*r.Endpoint]; !ok {
			return OutDoc{}, fmt.Errorf("sample references unknown endpoint %q", *r.Endpoint)
		}
		kind := evSample
		if r.Type != nil {
			switch *r.Type {
			case "", "sample":
				kind = evSample
			case "service":
				kind = evService
			case "endservice":
				kind = evEndService
			default:
				return OutDoc{}, fmt.Errorf("unknown sample type %q", *r.Type)
			}
		}
		ev := event{t: *r.T, kind: kind}
		if kind == evSample {
			if r.Latency == nil {
				return OutDoc{}, errors.New("sample missing a required field")
			}
			ev.latency = *r.Latency
		} else if r.Latency != nil {
			return OutDoc{}, errors.New("service event must not carry latency")
		}
		per[*r.Endpoint] = append(per[*r.Endpoint], ev)
		if !haveMax || *r.T > maxT {
			maxT, haveMax = *r.T, true
		}
	}

	var horizon int
	hasHorizon := false
	if doc.Until != nil {
		if haveMax && *doc.Until < maxT {
			return OutDoc{}, errors.New("until is before the last sample")
		}
		horizon, hasHorizon = *doc.Until, true
	} else if haveMax {
		horizon, hasHorizon = maxT, true
	}

	names := make([]string, 0, len(endpoints))
	for n := range endpoints {
		names = append(names, n)
	}
	sort.Strings(names)

	out := OutDoc{Endpoints: []OutEndpoint{}}
	for _, n := range names {
		op, err := computeEndpoint(n, endpoints[n], per[n], horizon, hasHorizon)
		if err != nil {
			return OutDoc{}, err
		}
		out.Endpoints = append(out.Endpoints, op)
	}
	return out, nil
}

// validateTimeline checks the per-endpoint service-window structure and that no
// two samples share a timestamp.
func validateTimeline(name string, evs []event) error {
	tmp := make([]event, len(evs))
	copy(tmp, evs)
	sort.SliceStable(tmp, func(i, j int) bool { return tmp[i].t < tmp[j].t })
	serviceOpen := false
	lastReadT := -1
	for _, e := range tmp {
		switch e.kind {
		case evService:
			if serviceOpen {
				return fmt.Errorf("nested service window for endpoint %s", name)
			}
			serviceOpen = true
		case evEndService:
			if !serviceOpen {
				return fmt.Errorf("endservice without service for endpoint %s", name)
			}
			serviceOpen = false
		case evSample:
			if lastReadT == e.t {
				return fmt.Errorf("duplicate timestamp for endpoint %s", name)
			}
			lastReadT = e.t
		}
	}
	if serviceOpen {
		return fmt.Errorf("service window left open for endpoint %s", name)
	}
	return nil
}

// computeEndpoint evaluates one endpoint's alarm ledger from its timeline.
//
// It processes the endpoint's event timeline against the configured limits
// and produces the alarms, cumulative alarm-seconds, lockout state, and
// final state.
func computeEndpoint(name string, c cfg, evs []event, horizon int, hasHorizon bool) (OutEndpoint, error) {
	if err := validateTimeline(name, evs); err != nil {
		return OutEndpoint{}, err
	}
	excs := []Alarm{}
	if len(evs) == 0 || !hasHorizon {
		return OutEndpoint{
			Name: name, Alarms: excs, OverSeconds: 0, LockedAt: nil,
			Final: Final{State: "ok", Since: 0},
		}, nil
	}

	sort.SliceStable(evs, func(i, j int) bool { return evs[i].t < evs[j].t })
	samples := [][2]int{}
	for _, e := range evs {
		if e.kind == evSample {
			samples = append(samples, [2]int{e.t, e.latency})
		}
	}

	cum := 0
	var lockedAt *int
	lastOver := false
	lastEnd := 0
	for i := 0; i < len(samples); i++ {
		a := samples[i][0]
		b := horizon
		if i+1 < len(samples) {
			b = samples[i+1][0]
		}
		if b <= a {
			continue
		}
		over := samples[i][1] > c.limit
		lastOver = over
		if over && lockedAt == nil {
			excs = append(excs, Alarm{Start: a, End: b})
			cum += b - a
			lastEnd = b
			if cum > c.budget {
				v := b
				lockedAt = &v
			}
		} else if !over {
			lastEnd = b
		}
	}

	final := Final{State: "ok", Since: lastEnd}
	if lockedAt != nil {
		final = Final{State: "locked", Since: *lockedAt}
	} else if lastOver {
		final = Final{State: "active", Since: lastEnd}
	}
	return OutEndpoint{Name: name, Alarms: excs, OverSeconds: cum, LockedAt: lockedAt, Final: final}, nil
}
