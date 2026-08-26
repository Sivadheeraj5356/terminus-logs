package model

type QueryParam struct {
	Name  string `json:"name"`
	Value string `json:"value"`
}

type Envelope struct {
	Method  string            `json:"method"`
	Path    string            `json:"path"`
	Query   []QueryParam      `json:"query"`
	Headers map[string]string `json:"headers"`
	Body    string            `json:"body"`
	Covered []string          `json:"covered"`
	Created int64             `json:"created"`
	Expires int64             `json:"expires"`
	Kid     string            `json:"kid"`
	MAC     string            `json:"mac"`
}

type Keyring struct {
	Keys map[string]string `json:"keys"`
}
