package semantics

// HeaderField is one canonical header name/value pair in wire order.
type HeaderField struct {
	Name  string `json:"name"`
	Value string `json:"value"`
}

// Request is the authoritative semantic request representation.
type Request struct {
	RequestID          string        `json:"request_id"`
	SignatureVersion   int           `json:"signature_version"`
	ProfileID          string        `json:"profile_id"`
	ProfileEpoch       int           `json:"profile_epoch"`
	Tenant             string        `json:"tenant"`
	KeyID              string        `json:"key_id"`
	KeyEpoch           int           `json:"key_epoch"`
	Method             string        `json:"method"`
	Authority          string        `json:"authority"`
	CanonicalPath      string        `json:"canonical_path"`
	CanonicalQuery     string        `json:"canonical_query"`
	CanonicalQueryPairs []QueryPair  `json:"canonical_query_pairs"`
	CanonicalTarget    string        `json:"canonical_target"`
	CanonicalHeaders   []HeaderField `json:"canonical_headers"`
	EntityBody         []byte        `json:"-"`
	EntityBodySHA256   string        `json:"entity_body_sha256"`
	EntityBodyLength   int           `json:"entity_body_length"`
	RequestNonce       string        `json:"request_nonce"`
}

type QueryPair struct {
	Key   string `json:"key"`
	Value string `json:"value"`
}

func (r *Request) Clone() *Request {
	cp := *r
	cp.EntityBody = append([]byte(nil), r.EntityBody...)
	cp.CanonicalHeaders = append([]HeaderField(nil), r.CanonicalHeaders...)
	cp.CanonicalQueryPairs = append([]QueryPair(nil), r.CanonicalQueryPairs...)
	return &cp
}

func (r *Request) HeaderMap() map[string]string {
	m := make(map[string]string, len(r.CanonicalHeaders))
	for _, h := range r.CanonicalHeaders {
		m[h.Name] = h.Value
	}
	return m
}
