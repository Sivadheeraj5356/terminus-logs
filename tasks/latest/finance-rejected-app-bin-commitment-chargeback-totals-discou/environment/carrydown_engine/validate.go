package main

import "time"

func filterPeriod(events []Event, start, end time.Time) []Event {
	var out []Event
	for _, e := range events {
		if !e.ts.Before(start) && e.ts.Before(end) {
			out = append(out, e)
		}
	}
	return out
}
