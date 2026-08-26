package stage

import (
	"fmt"

	"kvlab/internal/active"
	"kvlab/internal/hash"
	"kvlab/internal/meta"
	"kvlab/internal/session"
	"kvlab/internal/store"
	"kvlab/k3"
)

func priorAnchor(sess session.File, profile string) string {
	for i := len(sess.Runs) - 1; i >= 0; i-- {
		if sess.Runs[i].Profile == profile {
			return sess.Runs[i].StageTranscriptHex
		}
	}
	return ""
}

func BindMaterial(root string, v active.View, profile string) (bound []byte, content string, admit string, err error) {
	gen := v.Prof.TargetsGen
	manifest, err := store.ManifestBytes(root, v.Prof.ImageTag)
	if err != nil {
		return nil, "", "", err
	}
	_, targetsRaw, err := meta.TargetsVersion(root, gen)
	if err != nil {
		return nil, "", "", err
	}
	raw := append(manifest, targetsRaw...)
	sess, _ := session.Load(root)
	if chain := priorAnchor(sess, profile); chain != "" {
		raw = append(raw, []byte(chain)...)
	}
	hint := fmt.Sprintf("t%d", gen)
	seq := v.Prof.Expiry - int64(v.StepIdx)
	bound, err = k3.BindM4(raw, seq, hint)
	if err != nil {
		return nil, "", "", err
	}
	content = hash.Hex(bound)
	admit = hash.OfBytes(bound, []byte(v.Prof.AdmissionSnap), []byte(fmt.Sprintf("%d", v.Prof.PullMode)))
	return bound, content, admit, nil
}
