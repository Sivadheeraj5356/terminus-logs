package stage

import (
	"sort"
	"time"

	"passenger-rebooking-engine/internal/load"
	"passenger-rebooking-engine/internal/model"
	"passenger-rebooking-engine/internal/policy"
)

func flightIndex(flights []model.FlightInventory) map[string]model.FlightInventory {
	out := make(map[string]model.FlightInventory, len(flights))
	for _, f := range flights {
		out[f.FlightID] = f
	}
	return out
}

func copyInventory(flights []model.FlightInventory) map[string]map[string]int {
	out := make(map[string]map[string]int, len(flights))
	for _, f := range flights {
		inv := make(map[string]int, len(f.Inventory))
		for k, v := range f.Inventory {
			inv[k] = v
		}
		out[f.FlightID] = inv
	}
	return out
}

func pruneRemaining(seats map[string]map[string]int) map[string]map[string]int {
	out := make(map[string]map[string]int)
	for fid, classes := range seats {
		inner := make(map[string]int)
		for fc, n := range classes {
			if n > 0 {
				inner[fc] = n
			}
		}
		if len(inner) > 0 {
			out[fid] = inner
		}
	}
	return out
}

func allianceOK(origCarrier, replCarrier string, alliances model.AllianceDoc) bool {
	if origCarrier == replCarrier {
		return true
	}
	car, ok := alliances.Carriers[origCarrier]
	if !ok {
		return false
	}
	for _, p := range car.Partners {
		if p == replCarrier {
			return true
		}
	}
	return false
}

func legFareClass(leg model.Leg, passenger model.Passenger) string {
	if leg.FareClass != "" {
		return leg.FareClass
	}
	return passenger.FareClass
}

func fareOK(orig, repl string, pol model.Policy) bool {
	or := pol.FareClassRank[orig]
	rr := pol.FareClassRank[repl]
	if rr == or {
		return true
	}
	if rr < or {
		return false
	}
	if pol.UpgradeOnCancel && rr-or <= pol.MaxFareUpgradeSteps {
		return true
	}
	return false
}

func parseTime(iso string) (time.Time, error) {
	return time.Parse(time.RFC3339, iso)
}

func connectionOK(replArrival, nextDeparture string, pol model.Policy) bool {
	arr, err := parseTime(replArrival)
	if err != nil {
		return false
	}
	dep, err := parseTime(nextDeparture)
	if err != nil {
		return false
	}
	minDep := arr.Add(time.Duration(pol.ConnectionProtectionMinutes) * time.Minute)
	return !minDep.After(dep)
}

type candidate struct {
	flightID  string
	carrier   string
	fareClass string
	departure string
	arrival   string
}

func buildCandidates(
	leg model.Leg,
	cancel model.CancellationEvent,
	flights map[string]model.FlightInventory,
) []candidate {
	seen := map[string]bool{}
	out := []candidate{}
	add := func(fid, carrier, fc string) {
		key := fid + ":" + fc
		if seen[key] {
			return
		}
		seen[key] = true
		f, ok := flights[fid]
		if !ok {
			return
		}
		out = append(out, candidate{
			flightID:  fid,
			carrier:   carrier,
			fareClass: fc,
			departure: f.DepartureUTC,
			arrival:   f.ArrivalUTC,
		})
	}
	for _, opt := range cancel.ReplacementPool {
		add(opt.FlightID, opt.Carrier, opt.FareClass)
	}
	for _, f := range flights {
		if f.Origin == leg.Origin && f.Destination == leg.Destination {
			for fc := range f.Inventory {
				add(f.FlightID, f.Carrier, fc)
			}
		}
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].flightID != out[j].flightID {
			return out[i].flightID < out[j].flightID
		}
		return out[i].fareClass < out[j].fareClass
	})
	return out
}

func sortPassengers(passengers []model.Passenger, pol model.Policy) []model.Passenger {
	out := make([]model.Passenger, len(passengers))
	copy(out, passengers)
	mode := policy.PickMode(pol)
	if mode == "manifest_passenger_order" {
		return out
	}
	sort.SliceStable(out, func(i, j int) bool {
		si := policy.PriorityScore(out[i], pol)
		sj := policy.PriorityScore(out[j], pol)
		if si != sj {
			return si > sj
		}
		return out[i].PassengerID < out[j].PassengerID
	})
	return out
}

func disruptionDate(collapsed []model.CancellationEvent) string {
	if len(collapsed) == 0 {
		return "1970-01-01"
	}
	latest := collapsed[0].RecordedUTC
	for _, c := range collapsed[1:] {
		if c.RecordedUTC > latest {
			latest = c.RecordedUTC
		}
	}
	if len(latest) >= 10 {
		return latest[:10]
	}
	return "1970-01-01"
}

func Allocate(bundle *load.Bundle, collapsed []model.CancellationEvent) model.RebookingSnapshot {
	cancelByFlight := map[string]model.CancellationEvent{}
	cancelledSet := map[string]bool{}
	for _, c := range collapsed {
		cancelByFlight[c.FlightID] = c
		cancelledSet[c.FlightID] = true
	}
	cancelledFlights := make([]string, 0, len(cancelledSet))
	for fid := range cancelledSet {
		cancelledFlights = append(cancelledFlights, fid)
	}
	sort.Strings(cancelledFlights)

	flights := flightIndex(bundle.Flights)
	remaining := copyInventory(bundle.Flights)

	ordered := sortPassengers(bundle.Passengers, bundle.Policy)
	records := make([]model.PassengerRecord, 0, len(ordered))
	autoRebooked := []string{}

	for _, pax := range ordered {
		score := policy.PriorityScore(pax, bundle.Policy)
		rebooked := []model.RebookedLeg{}
		affected := false

		sortedLegs := make([]model.Leg, len(pax.Itinerary))
		copy(sortedLegs, pax.Itinerary)
		sort.Slice(sortedLegs, func(i, j int) bool { return sortedLegs[i].LegSeq < sortedLegs[j].LegSeq })

		for _, leg := range sortedLegs {
			if !cancelledSet[leg.FlightID] {
				continue
			}
			affected = true
			cancel := cancelByFlight[leg.FlightID]
			origFare := legFareClass(leg, pax)
			cands := buildCandidates(leg, cancel, flights)

			var nextLeg *model.Leg
			for i := range sortedLegs {
				if sortedLegs[i].LegSeq == leg.LegSeq+1 {
					nextLeg = &sortedLegs[i]
					break
				}
			}

			assigned := false
			for _, cand := range cands {
				if !allianceOK(leg.Carrier, cand.carrier, bundle.Alliances) {
					continue
				}
				if !fareOK(origFare, cand.fareClass, bundle.Policy) {
					continue
				}
				if nextLeg != nil {
					if !connectionOK(cand.arrival, nextLeg.DepartureUTC, bundle.Policy) {
						continue
					}
				}
				if remaining[cand.flightID][cand.fareClass] <= 0 {
					continue
				}
				remaining[cand.flightID][cand.fareClass]--
				rebooked = append(rebooked, model.RebookedLeg{
					LegSeq:            leg.LegSeq,
					OriginalFlight:    leg.FlightID,
					ReplacementFlight: cand.flightID,
					Carrier:           cand.carrier,
					FareClass:         cand.fareClass,
					DepartureUTC:      cand.departure,
					ArrivalUTC:        cand.arrival,
				})
				assigned = true
				break
			}
			if !assigned {
				// standby partial
			}
		}

		status := "unaffected"
		if affected {
			allOK := true
			for _, leg := range sortedLegs {
				if !cancelledSet[leg.FlightID] {
					continue
				}
				found := false
				for _, rb := range rebooked {
					if rb.LegSeq == leg.LegSeq {
						found = true
						break
					}
				}
				if !found {
					allOK = false
					break
				}
			}
			if allOK && len(rebooked) > 0 {
				status = "rebooked"
				autoRebooked = append(autoRebooked, pax.PassengerID)
			} else {
				status = "standby"
			}
		}

		records = append(records, model.PassengerRecord{
			PassengerID:   pax.PassengerID,
			Status:        status,
			PriorityScore: score,
			RebookedLegs:  rebooked,
		})
	}

	sort.Strings(autoRebooked)

	return model.RebookingSnapshot{
		SnapshotVersion:            1,
		DisruptionDate:             disruptionDate(collapsed),
		CollapsedCancellationCount: len(collapsed),
		AutoRebookedPassengerIDs:   autoRebooked,
		PassengerRecords:           records,
		RemainingSeats:             pruneRemaining(remaining),
		CancelledFlights:           cancelledFlights,
	}
}
