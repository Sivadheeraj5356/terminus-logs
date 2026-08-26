package ingest

type LaneSpec struct {
	Name     string `json:"name"`
	Path     string `json:"path"`
	Priority int    `json:"priority"`
}

type Manifest struct {
	Journal       string     `json:"journal"`
	Lanes         []LaneSpec `json:"lanes"`
	Policy        string     `json:"policy"`
	CheckpointDir string     `json:"checkpoint_dir"`
}

func (m Manifest) Resolve(base, rel string) string {
	if rel == "" {
		return ""
	}
	if rel[0] == '/' {
		return rel
	}
	return base + "/" + rel
}

type RawLine struct {
	Lane     string
	Priority int
	LineNum  int
	Raw      string
	RawHash  string
}

type Record struct {
	Raw        RawLine
	Epoch      int
	Seq        int
	Kind       string
	Source     string
	Rev        int
	Cancel     bool
	OpID       string
	Link       string
	Ms         int
	Tag        string
	Policy     map[string]interface{}
	MergeIndex int
}

type IdentityKey struct {
	Epoch  int
	Seq    int
	Source string
	OpID   string
}

func Identity(rec Record) IdentityKey {
	return IdentityKey{
		Epoch: rec.Epoch,
		Seq:   rec.Seq,
	}
}
