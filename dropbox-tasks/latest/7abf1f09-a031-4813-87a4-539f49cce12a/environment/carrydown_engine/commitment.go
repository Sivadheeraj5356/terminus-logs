package main

type serviceLine struct {
	service           string
	totalUnits        int64
	listCost          int64
	committedUnits    int64
	committedDiscount int64
	onDemandUnits     int64
	onDemandCost      int64
}

func computeServiceLine(service, tenantID, region string, evs []Event, rates []RateCard, commit *Commitment) serviceLine {
	sortEvents(evs)
	var pledged, discRate int64
	if commit != nil {
		pledged = commit.CommittedUnits
		discRate = commit.DiscountRate
	}
	var lagRate int64
	sl := serviceLine{service: service}
	for _, e := range evs {
		rate := resolveRate(rates, service, tenantID, region, e.ts)
		u := e.Units
		sl.totalUnits += u
		sl.listCost += u * rate
		billRate := lagRate
		if billRate == 0 {
			billRate = rate
		}
		remaining := pledged
		cu := u
		if cu > remaining {
			cu = remaining
		}
		sl.committedUnits += cu
		sl.committedDiscount += cu * (billRate - discRate)
		od := u - cu
		sl.onDemandUnits += od
		sl.onDemandCost += od * rate
		lagRate = rate
	}
	return sl
}
