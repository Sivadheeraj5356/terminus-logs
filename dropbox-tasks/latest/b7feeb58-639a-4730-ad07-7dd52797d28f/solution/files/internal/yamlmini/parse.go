package yamlmini

import (
	"fmt"
	"strconv"
	"strings"
)

type listMeta struct {
	parent map[string]any
	key    string
}

type container struct {
	indent   int
	m        map[string]any
	listMeta *listMeta
}

func Parse(data string) (map[string]any, error) {
	lines := strings.Split(strings.ReplaceAll(data, "\r\n", "\n"), "\n")
	root := map[string]any{}
	stack := []container{{indent: -1, m: root}}

	for i, raw := range lines {
		line := strings.TrimRight(raw, " \t")
		if line == "" || strings.HasPrefix(strings.TrimLeft(line, " "), "#") {
			continue
		}
		indent := leadingSpaces(raw)
		if indent%2 != 0 {
			return nil, fmt.Errorf("line %d: indent must be multiple of 2", i+1)
		}
		for len(stack) > 1 && indent <= stack[len(stack)-1].indent {
			stack = stack[:len(stack)-1]
		}
		cur := stack[len(stack)-1]
		trim := strings.TrimSpace(line)
		if strings.HasPrefix(trim, "- ") {
			if cur.listMeta == nil {
				return nil, fmt.Errorf("line %d: list item outside list", i+1)
			}
			rest := strings.TrimSpace(trim[2:])
			if rest == "" {
				item := map[string]any{}
				appendList(cur.listMeta, item)
				stack = append(stack, container{indent: indent, m: item})
				continue
			}
			key, valPart, ok := strings.Cut(rest, ":")
			if !ok {
				val, err := parseScalar(rest)
				if err != nil {
					return nil, fmt.Errorf("line %d: %w", i+1, err)
				}
				appendList(cur.listMeta, val)
				continue
			}
			key = strings.TrimSpace(key)
			valPart = strings.TrimSpace(valPart)
			item := map[string]any{}
			if valPart == "" {
				stack = append(stack, container{indent: indent, m: item})
			} else {
				val, err := parseScalar(valPart)
				if err != nil {
					return nil, fmt.Errorf("line %d: %w", i+1, err)
				}
				item[key] = val
				stack = append(stack, container{indent: indent, m: item})
			}
			appendList(cur.listMeta, item)
			continue
		}
		key, valPart, ok := strings.Cut(trim, ":")
		if !ok {
			return nil, fmt.Errorf("line %d: expected key: value", i+1)
		}
		key = strings.TrimSpace(key)
		valPart = strings.TrimSpace(valPart)
		if valPart == "" {
			childIndent := indent + 2
			if i+1 < len(lines) && leadingSpaces(lines[i+1]) == childIndent && strings.HasPrefix(strings.TrimSpace(lines[i+1]), "- ") {
				cur.m[key] = []any{}
				stack = append(stack, container{
					indent:   indent,
					listMeta: &listMeta{parent: cur.m, key: key},
				})
			} else {
				child := map[string]any{}
				cur.m[key] = child
				stack = append(stack, container{indent: indent, m: child})
			}
			continue
		}
		val, err := parseScalar(valPart)
		if err != nil {
			return nil, fmt.Errorf("line %d: %w", i+1, err)
		}
		cur.m[key] = val
	}
	return root, nil
}

func appendList(meta *listMeta, item any) {
	cur, _ := meta.parent[meta.key].([]any)
	meta.parent[meta.key] = append(cur, item)
}

func leadingSpaces(s string) int {
	n := 0
	for _, ch := range s {
		if ch == ' ' {
			n++
		} else {
			break
		}
	}
	return n
}

func parseScalar(s string) (any, error) {
	if s == "true" {
		return true, nil
	}
	if s == "false" {
		return false, nil
	}
	if strings.HasPrefix(s, "\"") && strings.HasSuffix(s, "\"") && len(s) >= 2 {
		return s[1 : len(s)-1], nil
	}
	if i, err := strconv.ParseInt(s, 10, 64); err == nil {
		return i, nil
	}
	if f, err := strconv.ParseFloat(s, 64); err == nil {
		return f, nil
	}
	return s, nil
}

func GetPath(m map[string]any, path string) (any, bool) {
	if path == "" {
		return nil, false
	}
	parts := strings.Split(path, ".")
	var cur any = m
	for _, p := range parts {
		mm, ok := cur.(map[string]any)
		if !ok {
			return nil, false
		}
		cur, ok = mm[p]
		if !ok {
			return nil, false
		}
	}
	return cur, true
}

func IsTruthy(v any) bool {
	switch t := v.(type) {
	case nil:
		return false
	case bool:
		return t
	case string:
		return t != "" && t != "false" && t != "0"
	case int:
		return t != 0
	case int64:
		return t != 0
	case float64:
		return t != 0
	default:
		return true
	}
}

func Subtree(m map[string]any, key string) map[string]any {
	if m == nil {
		return map[string]any{}
	}
	v, ok := m[key]
	if !ok {
		return map[string]any{}
	}
	child, ok := v.(map[string]any)
	if !ok {
		return map[string]any{}
	}
	return child
}

func CloneMap(m map[string]any) map[string]any {
	if m == nil {
		return map[string]any{}
	}
	out := make(map[string]any, len(m))
	for k, v := range m {
		if child, ok := v.(map[string]any); ok {
			out[k] = CloneMap(child)
		} else {
			out[k] = v
		}
	}
	return out
}
