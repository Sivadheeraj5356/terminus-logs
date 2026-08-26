package ruleset

import (
	"os"
	"path/filepath"
	"testing"
)

func writeTemp(t *testing.T, body string) string {
	t.Helper()
	p := filepath.Join(t.TempDir(), "rules.json")
	if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
	return p
}

func TestLoadValid(t *testing.T) {
	p := writeTemp(t, `[
	  {"id":"a","action":"allow","src":"10.0.0.0/8","dst":"0.0.0.0/0","port_min":22,"port_max":22,"protocol":"tcp","direction":"inbound","priority":100},
	  {"id":"b","action":"deny","src":"0.0.0.0/0","dst":"0.0.0.0/0","port_min":0,"port_max":65535,"protocol":"any","direction":"any","priority":0}
	]`)
	got, err := Load(p)
	if err != nil {
		t.Fatal(err)
	}
	if len(got.Rules) != 2 {
		t.Fatalf("want 2 rules, got %d", len(got.Rules))
	}
	if len(got.Warnings) != 0 {
		t.Fatalf("want no warnings, got %+v", got.Warnings)
	}
	if got.RawCount != 2 {
		t.Errorf("RawCount = %d, want 2", got.RawCount)
	}
	if got.Rules[0].Index != 0 || got.Rules[1].Index != 1 {
		t.Errorf("indices not preserved: %+v", got.Rules)
	}
}

func TestLoadDropsBadRulesButKeepsIndex(t *testing.T) {
	p := writeTemp(t, `[
	  {"id":"a","action":"allow","src":"10.0.0.0/8","dst":"0.0.0.0/0","port_min":22,"port_max":22,"protocol":"tcp","direction":"inbound","priority":100},
	  {"id":"","action":"allow","src":"10.0.0.0/8","dst":"0.0.0.0/0","port_min":22,"port_max":22,"protocol":"tcp","direction":"inbound","priority":100},
	  {"id":"c","action":"allow","src":"10.0.0.0/33","dst":"0.0.0.0/0","port_min":22,"port_max":22,"protocol":"tcp","direction":"inbound","priority":100},
	  {"id":"d","action":"deny","src":"192.168.0.0/16","dst":"0.0.0.0/0","port_min":80,"port_max":80,"protocol":"tcp","direction":"inbound","priority":50}
	]`)
	got, err := Load(p)
	if err != nil {
		t.Fatal(err)
	}
	if len(got.Rules) != 2 {
		t.Fatalf("want 2 surviving rules, got %d", len(got.Rules))
	}
	// survivors keep their original indices 0 and 3, not 0 and 1.
	if got.Rules[0].Index != 0 || got.Rules[1].Index != 3 {
		t.Errorf("surviving indices wrong: %d,%d", got.Rules[0].Index, got.Rules[1].Index)
	}
	if got.RawCount != 4 {
		t.Errorf("RawCount = %d, want 4", got.RawCount)
	}
	codes := map[string]int{}
	for _, w := range got.Warnings {
		codes[w.Code]++
	}
	if codes["bad_id"] != 1 {
		t.Errorf("want 1 bad_id, got %d", codes["bad_id"])
	}
	if codes["bad_cidr"] != 1 {
		t.Errorf("want 1 bad_cidr, got %d", codes["bad_cidr"])
	}
}

func TestLoadBadPortRange(t *testing.T) {
	p := writeTemp(t, `[
	  {"id":"a","action":"allow","src":"10.0.0.0/8","dst":"0.0.0.0/0","port_min":90,"port_max":80,"protocol":"tcp","direction":"inbound","priority":100}
	]`)
	got, err := Load(p)
	if err != nil {
		t.Fatal(err)
	}
	if len(got.Rules) != 0 {
		t.Fatalf("inverted port rule should be dropped")
	}
	if len(got.Warnings) != 1 || got.Warnings[0].Code != "bad_port" {
		t.Fatalf("want one bad_port warning, got %+v", got.Warnings)
	}
	if got.Warnings[0].Index != 0 {
		t.Errorf("bad_port index = %d, want 0", got.Warnings[0].Index)
	}
}
