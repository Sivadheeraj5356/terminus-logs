package eng

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"qxhub/cas"
	"qxhub/fyn"
	"qxhub/jor"
	"qxhub/pex"
	"qxhub/pth"
	"qxhub/zeb"
)

func armFile(arm string) string {
	switch arm {
	case "dense":
		return "t0.json"
	case "sparse":
		return "t1.json"
	case "weave":
		return "t2.json"
	case "starve":
		return "t3.json"
	case "held_out":
		return "t4.json"
	case "side_cut":
		return "t5.json"
	case "side_rcv":
		return "t6.json"
	case "side_prt":
		return "t7.json"
	case "side_stl":
		return "t8.json"
	default:
		return ""
	}
}

// LoadFixture reads one arm pack.
func LoadFixture(arm string) (*FixtureFile, error) {
	name := armFile(arm)
	if name == "" {
		return nil, fmt.Errorf("unknown arm %q", arm)
	}
	path := filepath.Join(pth.Root(), "fixtures", "qv", name)
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var fx FixtureFile
	if err := json.Unmarshal(raw, &fx); err != nil {
		return nil, err
	}
	if fx.Phase == "" {
		fx.Phase = "normal"
	}
	return &fx, nil
}

func candidates(cells []jor.CellSpec) []fyn.LaneRow {
	out := make([]fyn.LaneRow, 0, len(cells))
	for _, c := range cells {
		out = append(out, fyn.LaneRow{
			Kind:   c.Kind,
			Match:  []string{c.Match},
			Target: c.Target,
			Want:   c.Want,
		})
	}
	return out
}

// BuildPlan derives one arm through fold, tally, bind, and seal, then mints
// its commit token at the live session generation.
func BuildPlan(arm string) (*Plan, error) {
	fx, err := LoadFixture(arm)
	if err != nil {
		return nil, err
	}
	if err := pth.EnsureDirs(); err != nil {
		return nil, err
	}
	sess, err := zeb.Load()
	if err != nil {
		return nil, err
	}
	cands := candidates(fx.Cells)
	folded := fyn.ApplyWeft(cands, uint64(sess.ActiveGen))
	tallied, err := jor.ApplyTally(folded, fx.Cells, fx.RowCap, fx.GroupCap)
	if err != nil {
		return nil, err
	}
	outs := pex.ApplyBind(tallied, fx.Cells)
	pex.ApplySeal(fx.Arm, tallied, fx.Cells, outs, sess.Epoch)
	pane := pex.LastPane()
	tok, err := cas.Mint(fx.Arm, sess.ActiveGen, pane)
	if err != nil {
		return nil, err
	}
	return &Plan{
		Arm:      fx.Arm,
		Phase:    fx.Phase,
		Gen:      sess.ActiveGen,
		Floor:    sess.Floor,
		Epoch:    sess.Epoch,
		Token:    tok,
		Pane:     pane,
		Twin:     pex.LastTwin(),
		Rows:     tallied,
		Outs:     outs,
		Groups:   pex.LastGroups(),
		Hops:     pex.LastHops(),
		RowCap:   fx.RowCap,
		GroupCap: fx.GroupCap,
		Cells:    fx.Cells,
	}, nil
}

// WritePlan persists a prepared plan document.
func WritePlan(path string, plan *Plan) error {
	raw, err := json.MarshalIndent(plan, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, append(raw, '\n'), 0o644)
}

// ReadPlan loads a previously written plan document.
func ReadPlan(path string) (*Plan, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var p Plan
	if err := json.Unmarshal(raw, &p); err != nil {
		return nil, err
	}
	return &p, nil
}
