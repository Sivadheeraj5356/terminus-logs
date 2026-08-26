package semantics

import "encoding/json"

type ProfileConfig struct {
	ID                   string            `json:"id"`
	Epoch                int               `json:"epoch"`
	SignatureVersion     int               `json:"signature_version"`
	PreserveLegacyQuery  bool              `json:"preserve_legacy_query"`
	UppercasePercent     bool              `json:"uppercase_percent"`
	RemoveDotSegments    bool              `json:"remove_dot_segments"`
	HeaderPolicy         json.RawMessage   `json:"header_policy"`
	AllowedKeyProfiles   []string          `json:"allowed_key_profiles"`
}

func (pc *ProfileConfig) ToProfile() *Profile {
	return &Profile{
		ID:                  pc.ID,
		Epoch:               pc.Epoch,
		SignatureVersion:    pc.SignatureVersion,
		PreserveLegacyQuery: pc.PreserveLegacyQuery,
		UppercasePercent:    pc.UppercasePercent,
		RemoveDotSegments:   pc.RemoveDotSegments,
	}
}

func ProfileFromConfig(pc *ProfileConfig) (*Profile, HeaderPolicy, error) {
	p := pc.ToProfile()
	var policy HeaderPolicy
	if pc.SignatureVersion == 1 {
		policy = DefaultLegacyPolicy()
	} else {
		policy = DefaultCurrentPolicy()
	}
	return p, policy, nil
}
