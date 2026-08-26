package main

import "time"

func resolveRateLegacy(rates []RateCard, service, tenantID, region string, ts time.Time) int64 {
	var best *RateCard
	for i := range rates {
		rc := &rates[i]
		if rc.Service != service {
			continue
		}
		switch rc.Scope {
		case "global":
		case "region":
			if rc.ScopeKey != region {
				continue
			}
		case "tenant":
			if rc.ScopeKey != tenantID {
				continue
			}
		default:
			continue
		}
		if ts.Before(rc.from) {
			continue
		}
		if best == nil || rc.from.After(best.from) {
			best = rc
		}
	}
	if best == nil {
		panic("no rate for " + service + " " + tenantID)
	}
	return best.UnitRate
}
