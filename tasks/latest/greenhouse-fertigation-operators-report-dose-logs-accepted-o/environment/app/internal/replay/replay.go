package replay

import (
	"fmt"

	"greenhouse-fert-gate/internal/parse"
	"greenhouse-fert-gate/internal/store"
)

func EventID(ev *parse.Event) string {
	switch ev.EventType {
	case "ZONE_REGISTER":
		return fmt.Sprintf("ZR:%s:%d", ev.ZoneID, ev.EventSeq)
	case "BATCH_OPEN":
		return fmt.Sprintf("BO:%s:%d", ev.BatchID, ev.EventSeq)
	case "DOSE_TICK":
		return fmt.Sprintf("DT:%s:%d", ev.BatchID, ev.EventSeq)
	case "BATCH_CLOSE":
		return fmt.Sprintf("BC:%s:%d", ev.BatchID, ev.EventSeq)
	default:
		return fmt.Sprintf("X:%d", ev.EventSeq)
	}
}

func ShouldSkip(st *store.Store, eventID string) (bool, error) {
	return st.EventExists(eventID)
}
