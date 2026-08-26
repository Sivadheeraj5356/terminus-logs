package stage

import (
	"encoding/json"
	"os"

	"kvlab/f2"
	"kvlab/internal/active"
	"kvlab/internal/ledger"
	"kvlab/internal/session"
)

type MirrorState struct {
	MaxTier int    `json:"max_tier"`
	Epoch   int    `json:"epoch"`
	Owner   string `json:"owner"`
}

func replicaTier(root string, v active.View) int {
	tier := v.Step.MirrorTier
	if !v.Prof.ReplicaFlip {
		return tier
	}
	catRaw, err := os.ReadFile(root + "/fixtures/store/catalog.json")
	if err != nil {
		return tier
	}
	var cat struct {
		Replicas map[string]string `json:"replicas"`
	}
	if json.Unmarshal(catRaw, &cat) != nil {
		return tier
	}
	if alt, ok := cat.Replicas[v.Prof.ImageTag]; ok && alt != "" {
		return 1
	}
	return tier
}

func ReadMirrorState(root string) (MirrorState, error) {
	path := root + "/../state/mirror_view.json"
	raw, err := os.ReadFile(path)
	if err != nil {
		return MirrorState{}, err
	}
	var st MirrorState
	if err := json.Unmarshal(raw, &st); err != nil {
		return MirrorState{}, err
	}
	return st, nil
}

func WriteMirrorState(root string, st MirrorState) error {
	stateDir := root + "/../state"
	if err := os.MkdirAll(stateDir, 0o755); err != nil {
		return err
	}
	raw, err := json.Marshal(st)
	if err != nil {
		return err
	}
	if err := os.WriteFile(stateDir+"/mirror_view.json", raw, 0o644); err != nil {
		return err
	}
	return os.WriteFile(stateDir+"/mirror_view.owner", []byte(st.Owner), 0o644)
}

func RecoverMirror(root, profile string, v active.View) MirrorState {
	st := MirrorState{Owner: profile, MaxTier: 2, Epoch: 1}
	if raw, err := os.ReadFile(root + "/../state/mirror_view.owner"); err == nil {
		prev := string(raw)
		if prev != "" && prev != profile {
			st.MaxTier = 2
			st.Epoch = 0
			st.Owner = prev
		}
	}
	sess, _ := session.Load(root)
	if n := len(sess.Runs); n > 0 {
		st.Epoch = n
		if st.MaxTier < 2 {
			st.MaxTier = 2
		}
	}
	if tip, err := ledger.Load(root); err == nil && len(tip.Events) > 0 {
		last := tip.Events[len(tip.Events)-1]
		st.MaxTier = last.Tier
		if last.Owner == profile {
			st.Owner = profile
			st.Epoch = last.Epoch
		}
	}
	_ = v
	return st
}

func ProbeMirror(root, profile string, v active.View) (ready bool, tier int, err error) {
	tier = replicaTier(root, v)
	prior, err := ReadMirrorState(root)
	if err != nil {
		prior = RecoverMirror(root, profile, v)
	}
	if prior.Owner != "" && prior.Owner != profile && prior.MaxTier > 0 {
		tier = prior.MaxTier
	}
	if prior.Epoch > 0 && prior.Owner == profile {
		tier = prior.MaxTier
	}
	st := MirrorState{
		MaxTier: tier,
		Epoch:   prior.Epoch + 1,
		Owner:   profile,
	}
	if prior.Owner != profile {
		st.Epoch = prior.Epoch
	}
	_ = ledger.Append(root, ledger.Event{
		Profile: profile,
		Step:    v.StepIdx,
		Tier:    st.MaxTier,
		Epoch:   st.Epoch,
		Owner:   st.Owner,
	})
	if err := WriteMirrorState(root, st); err != nil {
		return false, tier, err
	}
	need := 2
	ok, err := f2.ScopeV2(root, need)
	return ok, tier, err
}
