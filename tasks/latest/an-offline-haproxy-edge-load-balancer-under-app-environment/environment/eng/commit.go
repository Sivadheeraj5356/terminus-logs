package eng

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"qxhub/cas"
	"qxhub/fyn"
	"qxhub/gst"
	"qxhub/idm"
	"qxhub/led"
	"qxhub/pex"
	"qxhub/pth"
	"qxhub/zeb"
)

type manifestDoc struct {
	Generation int      `json:"generation"`
	Arm        string   `json:"arm"`
	Pane       string   `json:"pane"`
	Groups     []string `json:"groups"`
	Rows       []rowDoc `json:"rows"`
}

type rowDoc struct {
	Kind   string   `json:"kind"`
	Mode   string   `json:"mode"`
	Target string   `json:"target"`
	Match  []string `json:"match"`
	Group  string   `json:"group"`
}

func manifestBytes(plan *Plan, gen int) ([]byte, string, error) {
	doc := manifestDoc{
		Generation: gen,
		Arm:        plan.Arm,
		Pane:       plan.Pane,
		Groups:     append([]string{}, plan.Groups...),
	}
	sort.Strings(doc.Groups)
	for _, r := range plan.Rows {
		doc.Rows = append(doc.Rows, rowDoc{
			Kind:   r.Kind,
			Mode:   r.Mode,
			Target: r.Target,
			Match:  append([]string{}, r.Match...),
			Group:  r.Group,
		})
	}
	if doc.Rows == nil {
		doc.Rows = []rowDoc{}
	}
	raw, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return nil, "", err
	}
	raw = append(raw, '\n')
	return raw, gst.SealBytes(raw), nil
}

// CommitPlan lands one prepared plan: idempotency, token guard, generation
// write, ledger append, session advance, then the sealed audit.
func CommitPlan(plan *Plan, outPath string) error {
	if err := pth.EnsureDirs(); err != nil {
		return err
	}
	tx := idm.TxFor(plan.Arm, plan.Gen, plan.Pane)
	seen, err := idm.Seen(tx)
	if err != nil {
		return err
	}
	if seen {
		sess, err := zeb.Load()
		if err != nil {
			return err
		}
		return emitAudit(outPath, plan, sess, false, gst.ReadCurrent(), "", tx)
	}
	if err := cas.Guard(plan.Token, plan.Arm, plan.Gen); err != nil {
		return err
	}
	sess, err := zeb.Load()
	if err != nil {
		return err
	}
	if plan.Phase == "cut" {
		if err := runCut(plan.Arm, plan.Rows); err != nil {
			return err
		}
		if err := idm.Mark(tx); err != nil {
			return err
		}
		runGen(&sess, plan.Phase, plan.Arm)
		if err := zeb.Save(sess); err != nil {
			return err
		}
		return curt_fold(outPath, plan, sess)
	}
	runGen(&sess, plan.Phase, plan.Arm)
	gen := sess.ActiveGen
	raw, seal, err := manifestBytes(plan, gen)
	if err != nil {
		return err
	}
	if err := gst.WriteGeneration(gen, raw, seal); err != nil {
		return err
	}
	ent, err := led.Append(gen, sess.Floor, sess.Epoch, plan.Arm, seal, tx)
	if err != nil {
		return err
	}
	if err := idm.Mark(tx); err != nil {
		return err
	}
	if err := zeb.Save(sess); err != nil {
		return err
	}
	return emitAudit(outPath, plan, sess, false, gen, ent.Hash, tx)
}

func emitAudit(outPath string, plan *Plan, sess zeb.Session, interrupt bool, gen int, head, tx string) error {
	_ = tx
	rows := plan.Rows
	if rows == nil {
		rows = []fyn.LaneRow{}
	}
	if head == "" {
		if h, ok, err := led.Head(); err == nil && ok {
			head = h.Hash
		}
	}
	groups := plan.Groups
	if groups == nil {
		groups = []string{}
	}
	hops := plan.Hops
	if hops == nil {
		hops = []pex.HopRec{}
	}
	outs := plan.Outs
	if outs == nil {
		outs = []pex.CellOut{}
	}
	seal := ""
	if gen > 0 {
		p := filepath.Join(pth.GenerationsDir(), fmt.Sprintf("%d", gen), "MSEAL")
		if b, err := os.ReadFile(p); err == nil {
			seal = strings.TrimSpace(string(b))
		}
	}
	audit := Audit{
		Arm:              plan.Arm,
		RuleRows:         rows,
		RouteCount:       len(rows),
		GroupCount:       len(groups),
		CellOutcomes:     outs,
		GroupKeys:        groups,
		HopRecords:       hops,
		PaneDigest:       plan.Pane,
		TwinDigest:       plan.Twin,
		ExpectedRowCap:   plan.RowCap,
		ExpectedGroupCap: plan.GroupCap,
		SessionFloor:     sess.Floor,
		SessionGen:       sess.ActiveGen,
		Interrupt:        interrupt,
		RunStamp:         runStamp(plan.Arm, plan.Pane, sess.Floor, sess.ActiveGen),
		Generation:       gen,
		ManifestSeal:     seal,
		LedgerHead:       head,
		PlanToken:        plan.Token,
		Status:           "ok",
	}
	return writeAudit(outPath, audit)
}

func runStamp(arm, pane string, floor, gen int) string {
	text := fmt.Sprintf("%s:%s:%d:%d\n", arm, pane, floor, gen)
	sum := sha256.Sum256([]byte(text))
	return hex.EncodeToString(sum[:])
}

func writeAudit(outPath string, audit Audit) error {
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(audit, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(outPath, append(raw, '\n'), 0o644)
}

// RunArm is the single-shot drive path: recover pre-pass, plan, commit.
func RunArm(arm, outPath string) error {
	fx, err := LoadFixture(arm)
	if err != nil {
		return err
	}
	if fx.Phase == "recover" {
		if err := runReplay(); err != nil {
			return err
		}
		if err := led.Mend(); err != nil {
			return err
		}
	}
	plan, err := BuildPlan(arm)
	if err != nil {
		return err
	}
	return CommitPlan(plan, outPath)
}
