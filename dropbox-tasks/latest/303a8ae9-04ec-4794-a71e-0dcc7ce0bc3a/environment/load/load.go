package load

import (
	"encoding/json"
	"os"
	"path/filepath"

	"pitctl/types"
)

func LoadFeatures(packs []string) ([]types.FeatureRev, error) {
	byRev := map[string]types.FeatureRev{}
	order := []string{}
	for _, pack := range packs {
		b, err := os.ReadFile(filepath.Join(Root, "data", "features", pack+".json"))
		if err != nil {
			return nil, err
		}
		var frames []types.FrameOp
		if err := json.Unmarshal(b, &frames); err != nil {
			return nil, err
		}
		for _, fr := range frames {
			switch fr.Op {
			case "put":
				if fr.Rev == nil {
					continue
				}
				rev := *fr.Rev
				if _, ok := byRev[rev.RevID]; !ok {
					byRev[rev.RevID] = rev
					order = append(order, rev.RevID)
				}
			case "kill":
				// baseline ignores kill frames
				_ = fr.RevID
			}
		}
	}
	out := make([]types.FeatureRev, 0, len(order))
	for _, id := range order {
		out = append(out, byRev[id])
	}
	return out, nil
}
