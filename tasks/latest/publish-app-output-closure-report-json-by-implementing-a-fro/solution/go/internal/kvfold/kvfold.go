package kvfold

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
)

const (
	reportPath   = "/app/output/closure_report.json"
	manifestPath = "/app/data/tenant_registry.json"
	runtimePath  = "/app/cfg/runtime.toml"
	schemaPath   = "/app/stubs/revision_stamp.txt"
)

type Entry struct {
	Kind  string
	Value any
}

type tenantRow struct {
	ID            string   `json:"id"`
	Base          string   `json:"base"`
	Overlay       string   `json:"overlay,omitempty"`
	ListMode      string   `json:"list_mode,omitempty"`
	Patches       []string `json:"patches,omitempty"`
	TenantPatches map[string]rawEntry `json:"tenant_patches,omitempty"`
}

type rawEntry struct {
	Kind  string          `json:"kind"`
	Value json.RawMessage `json:"value"`
}

type tenantOut struct {
	EffectiveDigestHex string `json:"effective_digest_hex"`
	ResolvedKeyCount   int    `json:"resolved_key_count"`
	OverlayDrifted     bool   `json:"overlay_drifted"`
}

type reportDoc struct {
	SchemaMark int                  `json:"schema_mark"`
	Tenants    map[string]tenantOut `json:"tenants"`
}

func BuildReport() (reportDoc, error) {
	manifest, err := loadManifest()
	if err != nil {
		return reportDoc{}, err
	}
	schemaMark, err := loadSchemaMark()
	if err != nil {
		return reportDoc{}, err
	}
	defaultMode, err := loadDefaultListMode()
	if err != nil {
		return reportDoc{}, err
	}
	out := reportDoc{
		SchemaMark: schemaMark,
		Tenants:    make(map[string]tenantOut, len(manifest)),
	}
	for _, row := range manifest {
		block, err := buildTenant(row, defaultMode)
		if err != nil {
			return reportDoc{}, fmt.Errorf("tenant %s: %w", row.ID, err)
		}
		out.Tenants[row.ID] = block
	}
	return out, nil
}

func WriteReport() error {
	doc, err := BuildReport()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(reportPath), 0o755); err != nil {
		return err
	}
	keys := make([]string, 0, len(doc.Tenants))
	for k := range doc.Tenants {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var buf bytes.Buffer
	buf.WriteString("{\n")
	buf.WriteString(fmt.Sprintf("  \"schema_mark\": %d,\n", doc.SchemaMark))
	buf.WriteString("  \"tenants\": {\n")
	for i, id := range keys {
		block := doc.Tenants[id]
		b, err := json.Marshal(block)
		if err != nil {
			return err
		}
		comma := ","
		if i == len(keys)-1 {
			comma = ""
		}
		buf.WriteString(fmt.Sprintf("    %q: %s%s\n", id, string(b), comma))
	}
	buf.WriteString("  }\n}\n")
	return os.WriteFile(reportPath, buf.Bytes(), 0o644)
}

func loadSchemaMark() (int, error) {
	raw, err := os.ReadFile(schemaPath)
	if err != nil {
		return 0, err
	}
	var mark int
	_, err = fmt.Sscanf(strings.TrimSpace(string(raw)), "%d", &mark)
	return mark, err
}

func loadManifest() ([]tenantRow, error) {
	raw, err := os.ReadFile(manifestPath)
	if err != nil {
		return nil, err
	}
	var doc struct {
		Tenants []tenantRow `json:"tenants"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		return nil, err
	}
	return doc.Tenants, nil
}

func loadDefaultListMode() (string, error) {
	raw, err := os.ReadFile(runtimePath)
	if err != nil {
		return "", err
	}
	lines := strings.Split(string(raw), "\n")
	inRuntime := false
	var top string
	var nested string
	for _, line := range lines {
		trim := strings.TrimSpace(line)
		if trim == "[runtime]" {
			inRuntime = true
			continue
		}
		if strings.HasPrefix(trim, "[") && trim != "[runtime]" {
			inRuntime = false
		}
		if !strings.HasPrefix(trim, "default_list_mode") {
			continue
		}
		parts := strings.SplitN(trim, "=", 2)
		if len(parts) != 2 {
			continue
		}
		val := strings.Trim(strings.TrimSpace(parts[1]), `"`)
		if inRuntime {
			nested = val
		} else {
			top = val
		}
	}
	if nested != "" {
		return nested, nil
	}
	if top != "" {
		return top, nil
	}
	return "replace", nil
}

func effectiveListMode(row tenantRow, defaultMode string) string {
	if row.ListMode != "" {
		return row.ListMode
	}
	return defaultMode
}

func buildTenant(row tenantRow, defaultMode string) (tenantOut, error) {
	listMode := effectiveListMode(row, defaultMode)
	acc, err := readFragment(row.Base)
	if err != nil {
		return tenantOut{}, err
	}
	if row.Overlay != "" {
		overlay, err := readFragment(row.Overlay)
		if err != nil {
			return tenantOut{}, err
		}
		acc = mergeLayer(acc, overlay, listMode)
	}
	preDigest := effectiveDigest(acc)
	layerIndex := 0
	for _, patchPath := range row.Patches {
		layerIndex++
		patch, err := readFragment(patchPath)
		if err != nil {
			return tenantOut{}, err
		}
		acc = applyPatch(acc, patch, listMode, layerIndex)
	}
	if len(row.TenantPatches) > 0 {
		layerIndex++
		inline := make(map[string]Entry, len(row.TenantPatches))
		for key, spec := range row.TenantPatches {
			val, err := decodeInlineValue(spec.Kind, spec.Value)
			if err != nil {
				return tenantOut{}, err
			}
			inline[key] = Entry{Kind: spec.Kind, Value: val}
		}
		acc = applyPatch(acc, inline, listMode, layerIndex)
	}
	acc = materializeAliases(acc)
	effective := effectiveDigest(acc)
	return tenantOut{
		EffectiveDigestHex: effective,
		ResolvedKeyCount:   len(acc),
		OverlayDrifted:     effective != preDigest,
	}, nil
}

func readFragment(path string) (map[string]Entry, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var outer map[string]struct {
		Kind  string          `json:"kind"`
		Value json.RawMessage `json:"value"`
	}
	if err := json.Unmarshal(raw, &outer); err != nil {
		return nil, err
	}
	out := make(map[string]Entry, len(outer))
	for key, spec := range outer {
		val, err := decodeValue(spec.Kind, spec.Value)
		if err != nil {
			return nil, err
		}
		out[key] = Entry{Kind: spec.Kind, Value: val}
	}
	return out, nil
}

func decodeInlineValue(kind string, raw json.RawMessage) (any, error) {
	if kind == "scalar" {
		var v any
		if err := json.Unmarshal(raw, &v); err != nil {
			return nil, err
		}
		return v, nil
	}
	return parseOrderedJSON(raw)
}

func decodeValue(kind string, raw json.RawMessage) (any, error) {
	if kind == "scalar" {
		var s string
		if err := json.Unmarshal(raw, &s); err == nil {
			return coerceScalar(s), nil
		}
		var v any
		if err := json.Unmarshal(raw, &v); err != nil {
			return nil, err
		}
		return v, nil
	}
	val, err := parseOrderedJSON(raw)
	if err != nil {
		return nil, err
	}
	return val, nil
}

func coerceScalar(value string) any {
	lower := strings.TrimSpace(strings.ToLower(value))
	switch lower {
	case "true", "yes", "on", "1":
		return true
	case "false", "no", "off", "0", "":
		return false
	default:
		return value
	}
}

// Ordered JSON representation preserving map key insertion order.
type orderedMap []orderedEntry

type orderedEntry struct {
	key   string
	value any
}

func parseOrderedJSON(raw json.RawMessage) (any, error) {
	dec := json.NewDecoder(bytes.NewReader(raw))
	tok, err := dec.Token()
	if err != nil {
		return nil, err
	}
	switch delim := tok.(type) {
	case json.Delim:
		switch delim {
		case '{':
			var pairs orderedMap
			for dec.More() {
				keyTok, err := dec.Token()
				if err != nil {
					return nil, err
				}
				key, ok := keyTok.(string)
				if !ok {
					return nil, fmt.Errorf("expected object key")
				}
				val, err := decodeToken(dec)
				if err != nil {
					return nil, err
				}
				pairs = append(pairs, orderedEntry{key: key, value: val})
			}
			if _, err := dec.Token(); err != nil {
				return nil, err
			}
			return pairs, nil
		case '[':
			var items []any
			for dec.More() {
				val, err := decodeToken(dec)
				if err != nil {
					return nil, err
				}
				items = append(items, val)
			}
			if _, err := dec.Token(); err != nil {
				return nil, err
			}
			return items, nil
		default:
			return nil, fmt.Errorf("unexpected delimiter")
		}
	default:
		return tok, nil
	}
}

func decodeToken(dec *json.Decoder) (any, error) {
	tok, err := dec.Token()
	if err != nil {
		return nil, err
	}
	switch v := tok.(type) {
	case json.Delim:
		switch v {
		case '{':
			var pairs orderedMap
			for dec.More() {
				keyTok, err := dec.Token()
				if err != nil {
					return nil, err
				}
				key, ok := keyTok.(string)
				if !ok {
					return nil, fmt.Errorf("expected object key")
				}
				val, err := decodeToken(dec)
				if err != nil {
					return nil, err
				}
				pairs = append(pairs, orderedEntry{key: key, value: val})
			}
			if _, err := dec.Token(); err != nil {
				return nil, err
			}
			return pairs, nil
		case '[':
			var items []any
			for dec.More() {
				val, err := decodeToken(dec)
				if err != nil {
					return nil, err
				}
				items = append(items, val)
			}
			if _, err := dec.Token(); err != nil {
				return nil, err
			}
			return items, nil
		default:
			return nil, fmt.Errorf("unexpected delimiter")
		}
	default:
		return v, nil
	}
}

func cloneAcc(acc map[string]Entry) map[string]Entry {
	out := make(map[string]Entry, len(acc))
	for k, v := range acc {
		out[k] = Entry{Kind: v.Kind, Value: deepCopy(v.Value)}
	}
	return out
}

func deepCopy(v any) any {
	switch t := v.(type) {
	case orderedMap:
		cp := make(orderedMap, 0, len(t))
		for _, e := range t {
			cp = append(cp, orderedEntry{key: e.key, value: deepCopy(e.value)})
		}
		return cp
	case []any:
		cp := make([]any, len(t))
		for i, item := range t {
			cp[i] = deepCopy(item)
		}
		return cp
	default:
		return t
	}
}

func mergeLayer(base, incoming map[string]Entry, listMode string) map[string]Entry {
	out := cloneAcc(base)
	for key, spec := range incoming {
		kind := spec.Kind
		val := spec.Value
		if kind == "tombstone" {
			continue
		}
		switch kind {
		case "scalar":
			out[key] = Entry{Kind: "scalar", Value: val}
		case "list":
			inList, _ := val.([]any)
			if cur, ok := out[key]; ok && listMode == "append" && cur.Kind == "list" {
				prev, _ := cur.Value.([]any)
				out[key] = Entry{Kind: "list", Value: mergeListAppend(prev, inList)}
			} else {
				out[key] = Entry{Kind: "list", Value: mergeListReplace(inList)}
			}
		case "map":
			prev := orderedMap{}
			if cur, ok := out[key]; ok && cur.Kind == "map" {
				prev, _ = cur.Value.(orderedMap)
			}
			inMap, _ := val.(orderedMap)
			out[key] = Entry{Kind: "map", Value: mergeMap(prev, inMap)}
		}
	}
	return out
}

func applyPatch(acc, patch map[string]Entry, listMode string, layerIndex int) map[string]Entry {
	out := cloneAcc(acc)
	for key, spec := range patch {
		kind := spec.Kind
		val := spec.Value
		if kind == "tombstone" {
			if layerIndex >= 1 {
				delete(out, key)
			}
			continue
		}
		if cur, ok := out[key]; ok && cur.Kind != kind {
			out[key] = Entry{Kind: kind, Value: val}
			continue
		}
		switch kind {
		case "scalar":
			out[key] = Entry{Kind: "scalar", Value: val}
		case "list":
			inList, _ := val.([]any)
			if listMode == "append" {
				if cur, ok := out[key]; ok && cur.Kind == "list" {
					prev, _ := cur.Value.([]any)
					out[key] = Entry{Kind: "list", Value: mergeListAppend(prev, inList)}
					continue
				}
			}
			out[key] = Entry{Kind: "list", Value: mergeListReplace(inList)}
		case "map":
			prev := orderedMap{}
			if cur, ok := out[key]; ok && cur.Kind == "map" {
				prev, _ = cur.Value.(orderedMap)
			}
			inMap, _ := val.(orderedMap)
			out[key] = Entry{Kind: "map", Value: mergeMap(prev, inMap)}
		}
	}
	return out
}

func mergeListReplace(new []any) []any {
	out := make([]any, len(new))
	copy(out, new)
	return out
}

func mergeListAppend(current, new []any) []any {
	cur := append([]any{}, current...)
	for _, item := range new {
		if !listContains(cur, item) {
			cur = append(cur, item)
		}
	}
	return cur
}

func listContains(items []any, want any) bool {
	for _, existing := range items {
		if valuesEqual(existing, want) {
			return true
		}
	}
	return false
}

func valuesEqual(a, b any) bool {
	return reflect.DeepEqual(a, b)
}

func mergeMap(current, incoming orderedMap) orderedMap {
	index := make(map[string]int, len(current))
	out := make(orderedMap, 0, len(current)+len(incoming))
	for _, e := range current {
		index[e.key] = len(out)
		out = append(out, orderedEntry{key: e.key, value: deepCopy(e.value)})
	}
	for _, e := range incoming {
		if pos, ok := index[e.key]; ok {
			if curMap, ok := out[pos].value.(orderedMap); ok {
				if inMap, ok := e.value.(orderedMap); ok {
					out[pos].value = mergeMap(curMap, inMap)
					continue
				}
			}
			out[pos].value = deepCopy(e.value)
			continue
		}
		index[e.key] = len(out)
		out = append(out, orderedEntry{key: e.key, value: deepCopy(e.value)})
	}
	return out
}

func lookupPath(acc map[string]Entry, path string) any {
	if !strings.Contains(path, ".") {
		if entry, ok := acc[path]; ok {
			return entry.Value
		}
		return nil
	}
	head, tail, _ := strings.Cut(path, ".")
	entry, ok := acc[head]
	if !ok || entry.Kind != "map" {
		return nil
	}
	cur := entry.Value
	for _, part := range strings.Split(tail, ".") {
		omap, ok := cur.(orderedMap)
		if !ok {
			return nil
		}
		var next any
		found := false
		for _, e := range omap {
			if e.key == part {
				next = e.value
				found = true
				break
			}
		}
		if !found {
			return nil
		}
		cur = next
	}
	return cur
}

func resolveValue(acc map[string]Entry, value any) any {
	return resolveValueSeen(acc, value, nil)
}

func resolveValueSeen(acc map[string]Entry, value any, seen map[string]struct{}) any {
	switch v := value.(type) {
	case string:
		if strings.HasPrefix(v, "$ref:") {
			target := strings.TrimPrefix(v, "$ref:")
			if seen == nil {
				seen = make(map[string]struct{})
			}
			if _, ok := seen[target]; ok {
				return v
			}
			seen[target] = struct{}{}
			resolved := lookupPath(acc, target)
			if resolved == nil {
				return v
			}
			return resolveValueSeen(acc, resolved, seen)
		}
		return v
	case []any:
		out := make([]any, len(v))
		for i, item := range v {
			out[i] = resolveValueSeen(acc, item, seen)
		}
		return out
	case orderedMap:
		out := make(orderedMap, 0, len(v))
		for _, e := range v {
			out = append(out, orderedEntry{key: e.key, value: resolveValueSeen(acc, e.value, seen)})
		}
		return out
	default:
		return v
	}
}

func materializeAliases(acc map[string]Entry) map[string]Entry {
	out := cloneAcc(acc)
	for key, spec := range out {
		out[key] = Entry{Kind: spec.Kind, Value: resolveValue(out, spec.Value)}
	}
	for {
		changed := false
		for key, spec := range out {
			resolved := resolveValue(out, spec.Value)
			if !valuesEqual(resolved, spec.Value) {
				out[key] = Entry{Kind: spec.Kind, Value: resolved}
				changed = true
			}
		}
		if !changed {
			break
		}
	}
	return out
}

func effectiveDigest(acc map[string]Entry) string {
	keys := make([]string, 0, len(acc))
	for k := range acc {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	lines := make([]string, 0, len(keys))
	for _, key := range keys {
		spec := acc[key]
		payload := map[string]any{
			"key":   key,
			"kind":  spec.Kind,
			"value": spec.Value,
		}
		line, err := marshalCompact(payload)
		if err != nil {
			panic(err)
		}
		lines = append(lines, line)
	}
	body := strings.Join(lines, "\n")
	sum := sha256.Sum256([]byte(body))
	return hex.EncodeToString(sum[:])
}

func marshalCompact(payload map[string]any) (string, error) {
	var buf bytes.Buffer
	buf.WriteByte('{')
	buf.WriteString(`"key":`)
	kb, _ := json.Marshal(payload["key"])
	buf.Write(kb)
	buf.WriteString(`,"kind":`)
	kindb, _ := json.Marshal(payload["kind"])
	buf.Write(kindb)
	buf.WriteString(`,"value":`)
	vb, err := marshalValue(payload["value"])
	if err != nil {
		return "", err
	}
	buf.Write(vb)
	buf.WriteByte('}')
	return buf.String(), nil
}

func marshalValue(v any) ([]byte, error) {
	switch t := v.(type) {
	case orderedMap:
		var buf bytes.Buffer
		buf.WriteByte('{')
		for i, e := range t {
			if i > 0 {
				buf.WriteByte(',')
			}
			kb, _ := json.Marshal(e.key)
			buf.Write(kb)
			buf.WriteByte(':')
			vb, err := marshalValue(e.value)
			if err != nil {
				return nil, err
			}
			buf.Write(vb)
		}
		buf.WriteByte('}')
		return buf.Bytes(), nil
	case []any:
		var buf bytes.Buffer
		buf.WriteByte('[')
		for i, item := range t {
			if i > 0 {
				buf.WriteByte(',')
			}
			vb, err := marshalValue(item)
			if err != nil {
				return nil, err
			}
			buf.Write(vb)
		}
		buf.WriteByte(']')
		return buf.Bytes(), nil
	default:
		return json.Marshal(t)
	}
}
