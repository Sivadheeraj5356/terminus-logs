package types

type ReplaceSpec struct {
	OldPath    string `json:"old_path"`
	NewPath    string `json:"new_path"`
	NewVersion string `json:"new_version"`
}

type RequestSpec struct {
	RootModule  string        `json:"root_module"`
	RootVersion string        `json:"root_version"`
	Replaces    []ReplaceSpec `json:"replaces"`
}

type ModuleEntry struct {
	Path           string         `json:"path"`
	Version        string         `json:"version"`
	Source         string         `json:"source"`
	PolicyDecision string         `json:"policy_decision"`
	Replaces       []ReplaceSpec  `json:"replaces"`
}

type Artifact struct {
	SchemaVersion    string        `json:"schema_version"`
	Goos             string        `json:"goos"`
	Goarch           string        `json:"goarch"`
	PolicyRevision   string        `json:"policy_revision"`
	Modules          []ModuleEntry `json:"modules"`
	ResolutionDigest string        `json:"resolution_digest"`
}

type PinRow struct {
	Path           string
	Version        string
	Goos           string
	Goarch         string
	PolicyRevision string
	Decision       string
}

type V1Module struct {
	Path           string `json:"path"`
	Version        string `json:"version"`
	Source         string `json:"source"`
	PolicyCode     string `json:"policy_code"`
	ReplaceOld     string `json:"replace_old,omitempty"`
	ReplaceNew     string `json:"replace_new,omitempty"`
	ReplaceVersion string `json:"replace_version,omitempty"`
}

type V1Lock struct {
	SchemaVersion string     `json:"schema_version"`
	Goos          string     `json:"goos"`
	Goarch        string     `json:"goarch"`
	Modules       []V1Module `json:"modules"`
}
