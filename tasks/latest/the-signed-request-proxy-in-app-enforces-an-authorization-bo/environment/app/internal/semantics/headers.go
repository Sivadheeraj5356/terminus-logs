package semantics

import (
	"fmt"
	"net/textproto"
	"strings"
)

// HeaderPolicy defines how headers are classified and normalized.
type HeaderPolicy struct {
	SingletonFields   map[string]bool
	JoinableListFields map[string]bool
	OrderPreserving   map[string]bool
	HopByHop          map[string]bool
	SignedFields      map[string]bool
}

var hopByHopDefault = map[string]bool{
	"Connection":          true,
	"Keep-Alive":          true,
	"Proxy-Authenticate":  true,
	"Proxy-Authorization": true,
	"Te":                  true,
	"Trailers":            true,
	"Transfer-Encoding":   true,
	"Upgrade":             true,
}

func DefaultCurrentPolicy() HeaderPolicy {
	return HeaderPolicy{
		SingletonFields: map[string]bool{
			"Host": true, "X-Sig-Profile": true, "X-Sig-Tenant": true,
			"X-Sig-Key-Id": true, "X-Sig-Nonce": true, "Content-Type": true,
		},
		JoinableListFields: map[string]bool{
			"Accept": true, "X-Test-List": true,
		},
		OrderPreserving: map[string]bool{
			"X-Order-Field": true,
		},
		HopByHop: hopByHopDefault,
		SignedFields: map[string]bool{
			"Host": true, "Content-Type": true, "Accept": true,
			"X-Test-List": true, "X-Order-Field": true,
		},
	}
}

func DefaultLegacyPolicy() HeaderPolicy {
	p := DefaultCurrentPolicy()
	p.SignedFields = map[string]bool{
		"Host": true, "Content-Type": true,
	}
	return p
}

func trimOWS(s string) string {
	return strings.TrimSpace(s)
}

func lowerName(name string) string {
	return strings.ToLower(textproto.CanonicalMIMEHeaderKey(name))
}

// ApplyHeaderPolicy produces the post-policy header set for backend forwarding.
func ApplyHeaderPolicy(policy HeaderPolicy, headers map[string][]string, headerOrder []string) ([]HeaderField, error) {
	nominated := connectionTokens(headers)
	filtered := make(map[string][]string)
	order := make([]string, 0)

	for _, name := range headerOrder {
		vals := headers[name]
		ln := lowerName(name)
		if policy.HopByHop[textproto.CanonicalMIMEHeaderKey(name)] || nominated[ln] {
			continue
		}
		if _, ok := filtered[name]; !ok {
			order = append(order, name)
		}
		filtered[name] = append(filtered[name], vals...)
	}

	return canonicalizeHeaders(policy, filtered, order)
}

// ApplyPreVerifyHeaders applies policy without Connection-token nomination filtering.
// Used by the broken verification path.
func ApplyPreVerifyHeaders(policy HeaderPolicy, headers map[string][]string, headerOrder []string) ([]HeaderField, error) {
	filtered := make(map[string][]string)
	order := make([]string, 0)
	for _, name := range headerOrder {
		vals := headers[name]
		canon := textproto.CanonicalMIMEHeaderKey(name)
		if policy.HopByHop[canon] && canon != "Connection" {
			continue
		}
		if _, ok := filtered[name]; !ok {
			order = append(order, name)
		}
		filtered[name] = append(filtered[name], vals...)
	}
	return canonicalizeHeaders(policy, filtered, order)
}

func connectionTokens(headers map[string][]string) map[string]bool {
	out := make(map[string]bool)
	vals, ok := headers["Connection"]
	if !ok {
		return out
	}
	for _, v := range vals {
		for _, tok := range strings.Split(v, ",") {
			tok = strings.TrimSpace(tok)
			if tok != "" {
				out[strings.ToLower(tok)] = true
			}
		}
	}
	return out
}

func canonicalizeHeaders(policy HeaderPolicy, headers map[string][]string, order []string) ([]HeaderField, error) {
	out := make([]HeaderField, 0)
	for _, name := range order {
		vals := headers[name]
		ln := lowerName(name)
		canonName := textproto.CanonicalMIMEHeaderKey(name)

		if policy.SingletonFields[canonName] || policy.SingletonFields[name] {
			if len(vals) > 1 {
				return nil, fmt.Errorf("duplicate singleton header %s", name)
			}
			if len(vals) == 1 {
				out = append(out, HeaderField{Name: ln, Value: trimOWS(vals[0])})
			}
			continue
		}

		if policy.JoinableListFields[canonName] || policy.JoinableListFields[name] {
			parts := make([]string, 0, len(vals))
			for _, v := range vals {
				parts = append(parts, trimOWS(v))
			}
			out = append(out, HeaderField{Name: ln, Value: strings.Join(parts, ", ")})
			continue
		}

		if policy.OrderPreserving[canonName] || policy.OrderPreserving[name] {
			for _, v := range vals {
				out = append(out, HeaderField{Name: ln, Value: trimOWS(v)})
			}
			continue
		}

		if len(vals) > 1 {
			return nil, fmt.Errorf("duplicate header %s", name)
		}
		if len(vals) == 1 {
			out = append(out, HeaderField{Name: ln, Value: trimOWS(vals[0])})
		}
	}
	return out, nil
}

func FilterSignedHeaders(policy HeaderPolicy, fields []HeaderField) []HeaderField {
	out := make([]HeaderField, 0, len(fields))
	for _, f := range fields {
		canon := textproto.CanonicalMIMEHeaderKey(f.Name)
		if policy.SignedFields[canon] || policy.SignedFields[f.Name] {
			out = append(out, f)
		}
	}
	return out
}
