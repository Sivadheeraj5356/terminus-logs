package relay

import (
	"slotmgr/internal/policy"
	"slotmgr/internal/store"
)

func metricAVal(metric string, cleared int, spanStart int) int {
	switch metric {
	case "cleared_ordinal":
		return spanStart
	case "span_start":
		return cleared
	default:
		return cleared
	}
}

func metricBVal(metric string, laneTick int, spanStart int) int {
	switch metric {
	case "lane_tick":
		return spanStart / 4096
	case "span_quotient":
		return laneTick
	default:
		return laneTick
	}
}

func seal_d(laneTick int, arrayCleared int, spanStart int, isArray bool, root string) (int, int, int) {
	pol := policy.Load(root)
	aVal := metricAVal(pol.TraceArrayMetric, arrayCleared, spanStart)
	bVal := laneTick
	if !isArray {
		bVal = metricBVal(pol.TraceVolumeBMetric, laneTick, spanStart)
	}
	return laneTick, aVal, bVal
}

func BindTrace(laneTick int, arrayCleared int, spanStart int, isArray bool, root string) store.TraceLine {
	tick, aVal, bVal := seal_d(laneTick, arrayCleared, spanStart, isArray, root)
	return store.TraceLine{Tick: tick, AVal: aVal, BVal: bVal}
}
