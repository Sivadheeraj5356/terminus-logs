package audit

import (
	"encoding/json"
	"os"
	"sort"

	"github.com/acme/auth/internal/clock"
	"github.com/acme/auth/internal/jwk"
	"github.com/acme/auth/internal/ledger"
)

type Event struct {
	EventSeq  int    `json:"event_seq"`
	EventType string `json:"event_type"`
	Kid       string `json:"kid,omitempty"`
	JTI       string `json:"jti,omitempty"`
	TS        string `json:"ts"`
}

type Exporter struct {
	clk   *clock.Clock
	state *jwk.RotationState
	led   *ledger.Ledger
	out   string
}

func New(clk *clock.Clock, state *jwk.RotationState, led *ledger.Ledger, out string) *Exporter {
	return &Exporter{clk: clk, state: state, led: led, out: out}
}

func (e *Exporter) Write() error {
	revoked, err := e.led.ListRevokedJTIs()
	if err != nil {
		return err
	}
	events := []Event{
		{EventSeq: 2, EventType: "key_retired", Kid: e.state.RetiringKid, TS: e.clk.RFC3339(10)},
		{EventSeq: 1, EventType: "key_promoted", Kid: e.state.ActiveKid, TS: e.clk.RFC3339(0)},
	}
	for i, jti := range revoked {
		events = append(events, Event{
			EventSeq:  100 + i,
			EventType: "token_revoked",
			JTI:       jti,
			TS:        e.clk.RFC3339(int64(20 + i)),
		})
	}
	if err := os.MkdirAll("/app/auth/out", 0o755); err != nil {
		return err
	}
	f, err := os.Create(e.out)
	if err != nil {
		return err
	}
	defer f.Close()
	for _, ev := range events {
		b, err := json.Marshal(ev)
		if err != nil {
			return err
		}
		if _, err := f.Write(append(b, '\n')); err != nil {
			return err
		}
	}
	return nil
}

func ExpectedEvents(clk *clock.Clock, state *jwk.RotationState, jtis []string) []Event {
	events := []Event{
		{EventSeq: 1, EventType: "key_promoted", Kid: state.ActiveKid, TS: clk.RFC3339(0)},
		{EventSeq: 2, EventType: "key_retired", Kid: state.RetiringKid, TS: clk.RFC3339(10)},
	}
	sort.Strings(jtis)
	for i, jti := range jtis {
		events = append(events, Event{
			EventSeq:  100 + i,
			EventType: "token_revoked",
			JTI:       jti,
			TS:        clk.RFC3339(int64(20 + i)),
		})
	}
	return events
}
