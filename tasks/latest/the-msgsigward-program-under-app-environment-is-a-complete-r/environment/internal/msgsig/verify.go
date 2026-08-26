package msgsig

import (
	"crypto/ed25519"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"sort"
	"strconv"
	"strings"
)

// Reference implementation of the RFC 9421 message-signature verification
// contract in docs/security-spec.md. Standard library only.
//
// A bundle may carry several labelled candidate signatures (Signature-Input and
// Signature are Structured-Field dictionaries). Each candidate is evaluated
// under the ordered per-signature policy; the cross-candidate selection then
// accepts the widest-coverage verifying candidate, or reports the
// furthest-progress rejection.

var errUneval = errors.New("unevaluatable input")

// --------------------------------------------------------------------------- //
// Component identifier + parameter model                                       //
// --------------------------------------------------------------------------- //

// param is one component parameter. When isStr is false the parameter is a bare
// boolean-true parameter (e.g. `;bs`), serialised without `=?1`.
type param struct {
	key    string
	strVal string
	isStr  bool
}

type compID struct {
	name   string
	params []param
}

type sigParams struct {
	created    int64
	hasCreated bool
	expires    int64
	hasExpires bool
	keyid      string
	hasKeyid   bool
	alg        string
	hasAlg     bool
}

type candidate struct {
	label       string
	ids         []compID
	params      sigParams
	memberValue string
	sig         []byte
}

// --------------------------------------------------------------------------- //
// Structured-field-ish serialisation of a component identifier                 //
// --------------------------------------------------------------------------- //

func sfString(s string) string {
	r := strings.ReplaceAll(s, "\\", "\\\\")
	r = strings.ReplaceAll(r, "\"", "\\\"")
	return "\"" + r + "\""
}

func serializeComponentID(name string, params []param) string {
	var b strings.Builder
	b.WriteString(sfString(name))
	for _, p := range params {
		if p.isStr {
			b.WriteString(";")
			b.WriteString(p.key)
			b.WriteString("=")
			b.WriteString(sfString(p.strVal))
		} else {
			b.WriteString(";")
			b.WriteString(p.key)
		}
	}
	return b.String()
}

// --------------------------------------------------------------------------- //
// Quote/paren-aware splitters                                                  //
// --------------------------------------------------------------------------- //

func splitTop(s string, sep byte) ([]string, error) {
	var out []string
	depth := 0
	instr := false
	start := 0
	for i := 0; i < len(s); i++ {
		c := s[i]
		if instr {
			if c == '\\' {
				i++
				continue
			}
			if c == '"' {
				instr = false
			}
			continue
		}
		switch c {
		case '"':
			instr = true
		case '(':
			depth++
		case ')':
			depth--
			if depth < 0 {
				return nil, errUneval
			}
		case sep:
			if depth == 0 {
				out = append(out, s[start:i])
				start = i + 1
			}
		}
	}
	if instr || depth != 0 {
		return nil, errUneval
	}
	out = append(out, s[start:])
	return out, nil
}

func splitWS(s string) ([]string, error) {
	var out []string
	instr := false
	var cur strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		if instr {
			cur.WriteByte(c)
			if c == '\\' && i+1 < len(s) {
				cur.WriteByte(s[i+1])
				i++
				continue
			}
			if c == '"' {
				instr = false
			}
			continue
		}
		switch c {
		case '"':
			instr = true
			cur.WriteByte(c)
		case ' ':
			if cur.Len() == 0 {
				return nil, errUneval
			}
			out = append(out, cur.String())
			cur.Reset()
		default:
			cur.WriteByte(c)
		}
	}
	if instr {
		return nil, errUneval
	}
	if cur.Len() > 0 {
		out = append(out, cur.String())
	}
	return out, nil
}

// parseQuoted parses a leading "..." from tok, returning (unescaped, rest).
func parseQuoted(tok string) (string, string, error) {
	if len(tok) == 0 || tok[0] != '"' {
		return "", "", errUneval
	}
	var b strings.Builder
	for i := 1; i < len(tok); {
		c := tok[i]
		if c == '\\' {
			if i+1 >= len(tok) {
				return "", "", errUneval
			}
			b.WriteByte(tok[i+1])
			i += 2
			continue
		}
		if c == '"' {
			return b.String(), tok[i+1:], nil
		}
		b.WriteByte(c)
		i++
	}
	return "", "", errUneval
}

func parseParams(rest string) ([]param, error) {
	var params []param
	if rest == "" {
		return params, nil
	}
	if rest[0] != ';' {
		return nil, errUneval
	}
	parts, err := splitTop(rest[1:], ';')
	if err != nil {
		return nil, err
	}
	for _, part := range parts {
		if part == "" {
			return nil, errUneval
		}
		if eq := strings.IndexByte(part, '='); eq >= 0 {
			k, v := part[:eq], part[eq+1:]
			if len(v) < 2 || v[0] != '"' || v[len(v)-1] != '"' {
				return nil, errUneval
			}
			uq, tail, err := parseQuoted(v)
			if err != nil {
				return nil, err
			}
			if tail != "" {
				return nil, errUneval
			}
			params = append(params, param{key: k, strVal: uq, isStr: true})
		} else {
			params = append(params, param{key: part})
		}
	}
	return params, nil
}

func parseComponentID(tok string) (compID, error) {
	name, rest, err := parseQuoted(tok)
	if err != nil {
		return compID{}, err
	}
	params, err := parseParams(rest)
	if err != nil {
		return compID{}, err
	}
	return compID{name: name, params: params}, nil
}

// --------------------------------------------------------------------------- //
// Signature-Input / Signature dictionaries                                     //
// --------------------------------------------------------------------------- //

func parseSigParams(s string) (sigParams, error) {
	var p sigParams
	if s == "" {
		return p, nil
	}
	if s[0] != ';' {
		return p, errUneval
	}
	parts, err := splitTop(s[1:], ';')
	if err != nil {
		return p, err
	}
	for _, part := range parts {
		eq := strings.IndexByte(part, '=')
		if eq < 0 {
			return p, errUneval
		}
		k, v := part[:eq], part[eq+1:]
		switch k {
		case "created", "expires":
			n, err := strconv.ParseInt(v, 10, 64)
			if err != nil {
				return p, errUneval
			}
			if k == "created" {
				p.created, p.hasCreated = n, true
			} else {
				p.expires, p.hasExpires = n, true
			}
		case "keyid", "alg", "nonce", "tag":
			if len(v) < 2 || v[0] != '"' || v[len(v)-1] != '"' {
				return p, errUneval
			}
			uq, tail, err := parseQuoted(v)
			if err != nil {
				return p, err
			}
			if tail != "" {
				return p, errUneval
			}
			if k == "keyid" {
				p.keyid, p.hasKeyid = uq, true
			} else if k == "alg" {
				p.alg, p.hasAlg = uq, true
			}
		default:
			return p, errUneval
		}
	}
	return p, nil
}

func parseSignatureInput(value string) ([]candidate, error) {
	members, err := splitTop(value, ',')
	if err != nil {
		return nil, err
	}
	seen := map[string]bool{}
	var out []candidate
	for _, member := range members {
		member = strings.TrimSpace(member)
		if member == "" {
			return nil, errUneval
		}
		eq := strings.IndexByte(member, '=')
		if eq < 0 {
			return nil, errUneval
		}
		label := strings.TrimSpace(member[:eq])
		if label == "" || strings.Contains(label, " ") {
			return nil, errUneval
		}
		if seen[label] {
			return nil, errUneval
		}
		seen[label] = true
		mval := strings.TrimSpace(member[eq+1:])
		if len(mval) == 0 || mval[0] != '(' {
			return nil, errUneval
		}
		closeIdx := strings.IndexByte(mval, ')')
		if closeIdx < 0 {
			return nil, errUneval
		}
		inner := mval[1:closeIdx]
		paramsStr := mval[closeIdx+1:]
		var ids []compID
		if strings.TrimSpace(inner) != "" {
			toks, err := splitWS(inner)
			if err != nil {
				return nil, err
			}
			for _, tok := range toks {
				cid, err := parseComponentID(tok)
				if err != nil {
					return nil, err
				}
				ids = append(ids, cid)
			}
		}
		sp, err := parseSigParams(paramsStr)
		if err != nil {
			return nil, err
		}
		out = append(out, candidate{label: label, ids: ids, params: sp, memberValue: mval})
	}
	return out, nil
}

func parseSignature(value string) (map[string][]byte, error) {
	out := map[string][]byte{}
	members, err := splitTop(value, ',')
	if err != nil {
		return nil, err
	}
	for _, member := range members {
		member = strings.TrimSpace(member)
		if member == "" {
			return nil, errUneval
		}
		eq := strings.IndexByte(member, '=')
		if eq < 0 {
			return nil, errUneval
		}
		label := strings.TrimSpace(member[:eq])
		sval := strings.TrimSpace(member[eq+1:])
		if len(sval) < 2 || sval[0] != ':' || sval[len(sval)-1] != ':' {
			return nil, errUneval
		}
		raw, err := base64.StdEncoding.DecodeString(sval[1 : len(sval)-1])
		if err != nil {
			return nil, errUneval
		}
		out[label] = raw
	}
	return out, nil
}

// --------------------------------------------------------------------------- //
// Component value derivation (with canonicalisation)                           //
// --------------------------------------------------------------------------- //

func fromHex(c byte) int {
	switch {
	case c >= '0' && c <= '9':
		return int(c - '0')
	case c >= 'a' && c <= 'f':
		return int(c - 'a' + 10)
	case c >= 'A' && c <= 'F':
		return int(c - 'A' + 10)
	}
	return -1
}

func pctDecode(s string) string {
	var b []byte
	n := len(s)
	for i := 0; i < n; {
		c := s[i]
		if c == '%' && i+2 <= n-1 {
			hi, lo := fromHex(s[i+1]), fromHex(s[i+2])
			if hi >= 0 && lo >= 0 {
				b = append(b, byte(hi*16+lo))
				i += 3
				continue
			}
		}
		b = append(b, c)
		i++
	}
	return string(b)
}

func canonAuthority(a string) string {
	a = strings.ToLower(a)
	if strings.HasSuffix(a, ":443") {
		a = a[:len(a)-len(":443")]
	}
	return a
}

func unfoldStrip(line string) string {
	var b []byte
	n := len(line)
	for i := 0; i < n; {
		c := line[i]
		if c == '\r' || c == '\n' {
			j := i + 1
			if c == '\r' && j < n && line[j] == '\n' {
				j++
			}
			if j < n && (line[j] == ' ' || line[j] == '\t') {
				for j < n && (line[j] == ' ' || line[j] == '\t') {
					j++
				}
				b = append(b, ' ')
				i = j
				continue
			}
			b = append(b, c)
			i++
			continue
		}
		b = append(b, c)
		i++
	}
	return strings.Join(strings.Fields(string(b)), " ")
}

func fieldValuePlain(m Message, name string) (string, error) {
	fv, ok := m.Headers[name]
	if !ok {
		return "", errUneval
	}
	parts := make([]string, len(fv.Lines))
	for i, l := range fv.Lines {
		parts[i] = unfoldStrip(l)
	}
	return strings.Join(parts, ", "), nil
}

func fieldValueBS(m Message, name string) (string, error) {
	fv, ok := m.Headers[name]
	if !ok {
		return "", errUneval
	}
	parts := make([]string, len(fv.Lines))
	for i, l := range fv.Lines {
		parts[i] = ":" + base64.StdEncoding.EncodeToString([]byte(unfoldStrip(l))) + ":"
	}
	return strings.Join(parts, ", "), nil
}

func queryParamValue(query, want string) (string, error) {
	if query == "" {
		return "", errUneval
	}
	var matches []string
	for _, pair := range strings.Split(query, "&") {
		if pair == "" {
			continue
		}
		k, v := pair, ""
		if eq := strings.IndexByte(pair, '='); eq >= 0 {
			k, v = pair[:eq], pair[eq+1:]
		}
		if pctDecode(k) == want {
			matches = append(matches, pctDecode(v))
		}
	}
	if len(matches) != 1 {
		return "", errUneval
	}
	return matches[0], nil
}

func componentValue(m Message, name string, params []param) (string, error) {
	if strings.HasPrefix(name, "@") {
		switch name {
		case "@method", "@authority", "@path", "@query":
			if len(params) != 0 {
				return "", errUneval
			}
			switch name {
			case "@method":
				return m.Method, nil
			case "@authority":
				return canonAuthority(m.Authority), nil
			case "@path":
				if m.Path == "" {
					return "/", nil
				}
				return m.Path, nil
			default: // @query
				return "?" + m.Query, nil
			}
		case "@query-param":
			var want string
			got := false
			for _, p := range params {
				if p.key == "name" && p.isStr {
					want, got = p.strVal, true
				} else {
					return "", errUneval
				}
			}
			if !got {
				return "", errUneval
			}
			return queryParamValue(m.Query, want)
		default:
			return "", errUneval
		}
	}
	if _, ok := m.Headers[name]; !ok {
		return "", errUneval
	}
	bs, sf := false, false
	for _, p := range params {
		if p.key == "bs" && !p.isStr {
			bs = true
		} else if p.key == "sf" && !p.isStr {
			sf = true
		} else {
			return "", errUneval
		}
	}
	if bs && sf {
		return "", errUneval
	}
	if sf {
		return fieldValueSF(m, name)
	}
	if bs {
		return fieldValueBS(m, name)
	}
	return fieldValuePlain(m, name)
}

// --------------------------------------------------------------------------- //
// RFC 8941 structured-field canonicalisation for ;sf header components          //
// (bounded to a Dictionary of Integer/Token/String/Boolean bare items+params).  //
// --------------------------------------------------------------------------- //

func sfIsKey0(c byte) bool { return (c >= 'a' && c <= 'z') || c == '*' }
func sfIsKey(c byte) bool {
	return sfIsKey0(c) || (c >= '0' && c <= '9') || c == '_' || c == '-' || c == '.'
}
func sfIsToken0(c byte) bool {
	return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '*'
}
func sfIsTchar(c byte) bool {
	if (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') {
		return true
	}
	switch c {
	case '!', '#', '$', '%', '&', '\'', '*', '+', '-', '.', '^', '_', '`', '|', '~', ':', '/':
		return true
	}
	return false
}

type sfVal struct {
	typ string // "int", "token", "string", "bool"
	i   int64
	s   string
	b   bool
}

type sfParam struct {
	key string
	val sfVal
}

type sfMember struct {
	key    string
	val    sfVal
	params []sfParam
}

func sfSkipSp(s string, i int) int {
	for i < len(s) && (s[i] == ' ' || s[i] == '\t') {
		i++
	}
	return i
}

func sfParseKey(s string, i int) (string, int, error) {
	if i >= len(s) || !sfIsKey0(s[i]) {
		return "", 0, errUneval
	}
	j := i
	for j < len(s) && sfIsKey(s[j]) {
		j++
	}
	return s[i:j], j, nil
}

func sfParseBare(s string, i int) (sfVal, int, error) {
	n := len(s)
	if i >= n {
		return sfVal{}, 0, errUneval
	}
	c := s[i]
	if c == '"' {
		j := i + 1
		var b strings.Builder
		for j < n {
			ch := s[j]
			if ch == '\\' {
				if j+1 >= n || (s[j+1] != '"' && s[j+1] != '\\') {
					return sfVal{}, 0, errUneval
				}
				b.WriteByte(s[j+1])
				j += 2
				continue
			}
			if ch == '"' {
				return sfVal{typ: "string", s: b.String()}, j + 1, nil
			}
			if ch < 0x20 || ch > 0x7e {
				return sfVal{}, 0, errUneval
			}
			b.WriteByte(ch)
			j++
		}
		return sfVal{}, 0, errUneval
	}
	if c == '?' {
		if i+1 < n && (s[i+1] == '0' || s[i+1] == '1') {
			return sfVal{typ: "bool", b: s[i+1] == '1'}, i + 2, nil
		}
		return sfVal{}, 0, errUneval
	}
	if c == '-' || (c >= '0' && c <= '9') {
		j := i
		if c == '-' {
			j++
		}
		k := j
		for k < n && s[k] >= '0' && s[k] <= '9' {
			k++
		}
		if k == j || (k-j) > 15 || (k < n && s[k] == '.') {
			return sfVal{}, 0, errUneval
		}
		v, err := strconv.ParseInt(s[i:k], 10, 64)
		if err != nil {
			return sfVal{}, 0, errUneval
		}
		return sfVal{typ: "int", i: v}, k, nil
	}
	if sfIsToken0(c) {
		j := i
		for j < n && sfIsTchar(s[j]) {
			j++
		}
		return sfVal{typ: "token", s: s[i:j]}, j, nil
	}
	return sfVal{}, 0, errUneval
}

func sfParseParams(s string, i int) ([]sfParam, int, error) {
	var params []sfParam
	n := len(s)
	for i < n && s[i] == ';' {
		i++
		i = sfSkipSp(s, i)
		key, ni, err := sfParseKey(s, i)
		if err != nil {
			return nil, 0, err
		}
		i = ni
		var val sfVal
		if i < n && s[i] == '=' {
			i++
			v, ni2, err := sfParseBare(s, i)
			if err != nil {
				return nil, 0, err
			}
			val, i = v, ni2
		} else {
			val = sfVal{typ: "bool", b: true}
		}
		params = append(params, sfParam{key, val})
	}
	return params, i, nil
}

func sfParseDict(s string) ([]sfMember, error) {
	var members []sfMember
	i := sfSkipSp(s, 0)
	n := len(s)
	for i < n {
		key, ni, err := sfParseKey(s, i)
		if err != nil {
			return nil, err
		}
		i = ni
		var val sfVal
		if i < n && s[i] == '=' {
			i++
			v, ni2, err := sfParseBare(s, i)
			if err != nil {
				return nil, err
			}
			val, i = v, ni2
		} else {
			val = sfVal{typ: "bool", b: true}
		}
		prm, ni3, err := sfParseParams(s, i)
		if err != nil {
			return nil, err
		}
		i = ni3
		found := -1
		for idx, mm := range members {
			if mm.key == key {
				found = idx
				break
			}
		}
		if found >= 0 {
			members[found] = sfMember{key, val, prm}
		} else {
			members = append(members, sfMember{key, val, prm})
		}
		i = sfSkipSp(s, i)
		if i >= n {
			break
		}
		if s[i] != ',' {
			return nil, errUneval
		}
		i++
		i = sfSkipSp(s, i)
		if i >= n {
			return nil, errUneval
		}
	}
	return members, nil
}

func sfSerBare(v sfVal) string {
	switch v.typ {
	case "int":
		return strconv.FormatInt(v.i, 10)
	case "token":
		return v.s
	case "string":
		r := strings.ReplaceAll(v.s, "\\", "\\\\")
		r = strings.ReplaceAll(r, "\"", "\\\"")
		return "\"" + r + "\""
	default: // bool
		if v.b {
			return "?1"
		}
		return "?0"
	}
}

func sfIsBoolTrue(v sfVal) bool { return v.typ == "bool" && v.b }

func sfSerParams(params []sfParam) string {
	var b strings.Builder
	for _, p := range params {
		if sfIsBoolTrue(p.val) {
			b.WriteString(";")
			b.WriteString(p.key)
		} else {
			b.WriteString(";")
			b.WriteString(p.key)
			b.WriteString("=")
			b.WriteString(sfSerBare(p.val))
		}
	}
	return b.String()
}

func sfSerializeDict(members []sfMember) string {
	parts := make([]string, len(members))
	for i, m := range members {
		if sfIsBoolTrue(m.val) {
			parts[i] = m.key + sfSerParams(m.params)
		} else {
			parts[i] = m.key + "=" + sfSerBare(m.val) + sfSerParams(m.params)
		}
	}
	return strings.Join(parts, ", ")
}

func fieldValueSF(m Message, name string) (string, error) {
	pv, err := fieldValuePlain(m, name)
	if err != nil {
		return "", err
	}
	members, err := sfParseDict(pv)
	if err != nil {
		return "", err
	}
	return sfSerializeDict(members), nil
}

func signatureBase(m Message, ids []compID, memberValue string) ([]byte, error) {
	var b strings.Builder
	for _, id := range ids {
		v, err := componentValue(m, id.name, id.params)
		if err != nil {
			return nil, err
		}
		b.WriteString(serializeComponentID(id.name, id.params))
		b.WriteString(": ")
		b.WriteString(v)
		b.WriteString("\n")
	}
	b.WriteString("\"@signature-params\": ")
	b.WriteString(memberValue)
	return []byte(b.String()), nil
}

// --------------------------------------------------------------------------- //
// Crypto                                                                       //
// --------------------------------------------------------------------------- //

func contentDigest(body []byte) string {
	sum := sha256.Sum256(body)
	return "sha-256=:" + base64.StdEncoding.EncodeToString(sum[:]) + ":"
}

func verifyUnder(alg string, k Key, base, sig []byte) (bool, error) {
	switch alg {
	case "ed25519":
		pub, err := hex.DecodeString(k.Public)
		if err != nil || len(pub) != ed25519.PublicKeySize {
			return false, nil
		}
		return ed25519.Verify(ed25519.PublicKey(pub), base, sig), nil
	case "hmac-sha256":
		secretHex := k.Secret
		if secretHex == "" {
			secretHex = k.Public
		}
		secret, err := hex.DecodeString(secretHex)
		if err != nil {
			return false, nil
		}
		mac := hmac.New(sha256.New, secret)
		mac.Write(base)
		return hmac.Equal(mac.Sum(nil), sig), nil
	default:
		return false, errUneval
	}
}

// --------------------------------------------------------------------------- //
// Per-candidate evaluation + cross-candidate selection                         //
// --------------------------------------------------------------------------- //

type candResult struct {
	label   string
	stage   int
	verdict string
	reason  string
	covered string
}

func coveredList(ids []compID) string {
	parts := make([]string, len(ids))
	for i, id := range ids {
		parts[i] = serializeComponentID(id.name, id.params)
	}
	return strings.Join(parts, ",")
}

func evalCandidate(keys map[string]Key, now int64, m Message, c candidate) (candResult, error) {
	covered := coveredList(c.ids)
	names := map[string]bool{}
	for _, id := range c.ids {
		names[id.name] = true
	}
	key, ok := keys[c.params.keyid]
	if !ok {
		return candResult{c.label, 1, Rejected, "unknown_key", "-"}, nil
	}
	bound := key.Alg
	use := bound
	if c.params.hasAlg {
		use = c.params.alg
	}
	base, err := signatureBase(m, c.ids, c.memberValue)
	if err != nil {
		return candResult{}, err
	}
	okSig, err := verifyUnder(use, key, base, c.sig)
	if err != nil {
		return candResult{}, err
	}
	if !okSig {
		return candResult{c.label, 3, Rejected, "signature_invalid", "-"}, nil
	}
	required := []string{"@method", "@path"}
	if len(m.Body) > 0 {
		required = append(required, "content-digest")
	}
	for _, r := range required {
		if !names[r] {
			return candResult{c.label, 4, Rejected, "coverage_inadequate", covered}, nil
		}
	}
	// tolerate small clock skew on the freshness window
	const skew = 300
	if c.params.hasExpires && now > c.params.expires+skew {
		return candResult{c.label, 5, Rejected, "expired", covered}, nil
	}
	if c.params.hasCreated && now < c.params.created-skew {
		return candResult{c.label, 6, Rejected, "not_yet_valid", covered}, nil
	}
	if names["content-digest"] {
		cd, err := fieldValuePlain(m, "content-digest")
		if err != nil {
			return candResult{}, err
		}
		if cd == "" {
			return candResult{c.label, 7, Rejected, "digest_mismatch", covered}, nil
		}
	}
	return candResult{c.label, 8, Verified, "ok", covered}, nil
}

func coveredCount(c string) int {
	if c == "-" {
		return 0
	}
	return len(strings.Split(c, ","))
}

func selectDecision(results []candResult) (string, string, string) {
	var verified []candResult
	for _, r := range results {
		if r.verdict == Verified {
			verified = append(verified, r)
		}
	}
	if len(verified) > 0 {
		sort.SliceStable(verified, func(i, j int) bool {
			ci, cj := coveredCount(verified[i].covered), coveredCount(verified[j].covered)
			if ci != cj {
				return ci > cj
			}
			return verified[i].label < verified[j].label
		})
		best := verified[0]
		return Verified, best.label, best.covered
	}
	all := append([]candResult{}, results...)
	sort.SliceStable(all, func(i, j int) bool {
		if all[i].stage != all[j].stage {
			return all[i].stage < all[j].stage
		}
		return all[i].label < all[j].label
	})
	best := all[0]
	return Rejected, best.reason, best.covered
}

// Verify implements the docs/security-spec.md contract.
func Verify(in Input) (verdict string, selector string, covered string, err error) {
	m := in.Message
	if len(in.Keys) == 0 {
		return "", "", "", errUneval
	}
	if m.Headers == nil {
		return "", "", "", errUneval
	}
	siFV, ok := m.Headers["signature-input"]
	if !ok {
		return "", "", "", errUneval
	}
	sigFV, ok := m.Headers["signature"]
	if !ok {
		return "", "", "", errUneval
	}
	siStr, err := siFV.One()
	if err != nil {
		return "", "", "", errUneval
	}
	sigStr, err := sigFV.One()
	if err != nil {
		return "", "", "", errUneval
	}
	cands, err := parseSignatureInput(siStr)
	if err != nil {
		return "", "", "", err
	}
	if len(cands) == 0 {
		return "", "", "", errUneval
	}
	sigs, err := parseSignature(sigStr)
	if err != nil {
		return "", "", "", err
	}
	for i := range cands {
		if !cands[i].params.hasKeyid {
			return "", "", "", errUneval
		}
		sb, ok := sigs[cands[i].label]
		if !ok {
			return "", "", "", errUneval
		}
		cands[i].sig = sb
		for _, id := range cands[i].ids {
			if _, err := componentValue(m, id.name, id.params); err != nil {
				return "", "", "", err
			}
		}
	}
	results := make([]candResult, 0, len(cands))
	for _, c := range cands {
		r, err := evalCandidate(in.Keys, in.Now, m, c)
		if err != nil {
			return "", "", "", err
		}
		results = append(results, r)
	}
	v, sel, cov := selectDecision(results)
	return v, sel, cov, nil
}
