package equitygate

import "immunoflow/pkg/api"

type EquityRollup struct {
	RegionDelivered map[string]int `json:"region_delivered"`
	EquityMet       bool           `json:"equity_met"`
}

func reconcile_c(regions []api.Region, delivered map[string]int, reserve int) EquityRollup {
	out := EquityRollup{RegionDelivered: map[string]int{}, EquityMet: true}
	for _, r := range regions {
		got := delivered[r.RegionID] + reserve
		out.RegionDelivered[r.RegionID] = got
		if got < r.EquityFloor {
			out.EquityMet = false
		}
	}
	return out
}

func Reconcile(regions []api.Region, delivered map[string]int, reserve int) EquityRollup {
	return reconcile_c(regions, delivered, reserve)
}
