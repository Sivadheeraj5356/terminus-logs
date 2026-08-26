package eval

import (
	"strings"
	"testing"

	"example.com/acl/internal/cidr"
	"example.com/acl/internal/ruleset"
)

func TestParseFlows(t *testing.T) {
	in := strings.Join([]string{
		`{"src":"10.0.0.1","dst":"192.168.1.1","port":22,"protocol":"tcp","direction":"inbound"}`,
		``,
		`{bad json}`,
		`{"src":"8.8.8.8","dst":"9.9.9.9","port":53,"protocol":"udp","direction":"outbound"}`,
	}, "\n")
	flows := ParseFlows(strings.NewReader(in))
	if len(flows) != 2 {
		t.Fatalf("want 2 flows (blank and malformed skipped), got %d", len(flows))
	}
	if flows[0].Line != 1 || flows[1].Line != 4 {
		t.Errorf("line numbers wrong: %+v", flows)
	}
	if flows[0].Dst != "192.168.1.1" || flows[1].Direction != "outbound" {
		t.Errorf("fields not parsed: %+v", flows)
	}
}

func TestUnparseableSrcDefaultDeny(t *testing.T) {
	flows := []Flow{{Src: "999.1.1.1", Dst: "10.0.0.1", Port: 22, Protocol: "tcp", Direction: "inbound", Line: 1}}
	dec, _ := Evaluate(flows, []ruleset.Rule{}, cidr.ParseIP)
	if dec[0].Decision != "deny" {
		t.Errorf("unparseable src should be denied, got %q", dec[0].Decision)
	}
	if dec[0].Matched != DefaultMatch || DefaultMatch != "default-deny" {
		t.Errorf("default-deny sentinel must be %q, got %q", "default-deny", dec[0].Matched)
	}
	if dec[0].Logged == nil {
		t.Errorf("logged must be an array, not nil")
	}
}

func TestDecisionsPreserveOrder(t *testing.T) {
	flows := []Flow{
		{Src: "8.8.8.8", Dst: "1.1.1.1", Port: 1, Protocol: "tcp", Direction: "inbound", Line: 1},
		{Src: "10.5.5.5", Dst: "2.2.2.2", Port: 22, Protocol: "tcp", Direction: "inbound", Line: 2},
	}
	dec, _ := Evaluate(flows, []ruleset.Rule{}, cidr.ParseIP)
	if dec[0].Src != "8.8.8.8" || dec[1].Src != "10.5.5.5" {
		t.Errorf("decisions must be in input order: %+v", dec)
	}
}
