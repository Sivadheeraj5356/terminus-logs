package policy

import "passenger-rebooking-engine/internal/model"

func PriorityScore(p model.Passenger, pol model.Policy) int {
	lw := pol.PriorityWeight.Loyalty[p.LoyaltyTier]
	fw := pol.PriorityWeight.FareClass[p.FareClass]
	return lw + fw
}

func PickMode(pol model.Policy) string {
	if pol.PriorityPickMode == "manifest_passenger_order" {
		return "manifest_passenger_order"
	}
	return "priority_score"
}
