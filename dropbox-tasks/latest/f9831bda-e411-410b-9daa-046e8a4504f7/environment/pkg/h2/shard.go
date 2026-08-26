package h2

import (
	"encoding/json"
	"os"
)

type VendorShard struct {
	Issuer  string   `json:"issuer"`
	ThisUp  string   `json:"this_up"`
	Serials []string `json:"serials"`
}

func LoadShard(root, ref string) (*VendorShard, error) {
	path := root + "/m4/mirrors/" + ref + ".json"
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var v VendorShard
	if err := json.Unmarshal(raw, &v); err != nil {
		return nil, err
	}
	return &v, nil
}
