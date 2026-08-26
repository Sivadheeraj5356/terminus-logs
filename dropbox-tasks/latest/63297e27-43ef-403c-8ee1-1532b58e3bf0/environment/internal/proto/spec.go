package proto

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
)

type FrameSpec struct {
	Kind     string
	Content  string
	Portal   string
	Stmt     string
	Fill     int
	Params   []int
	Count    int
	ElemSize int
}

func LoadSpec(path string) (*FrameSpec, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	spec := &FrameSpec{}
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, val, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		key = strings.TrimSpace(key)
		val = strings.TrimSpace(val)
		switch key {
		case "kind":
			spec.Kind = val
		case "content":
			spec.Content = val
		case "portal":
			spec.Portal = val
		case "stmt":
			spec.Stmt = val
		case "fill":
			spec.Fill, err = strconv.Atoi(val)
			if err != nil {
				return nil, fmt.Errorf("spec: bad fill %q: %v", val, err)
			}
		case "count":
			spec.Count, err = strconv.Atoi(val)
			if err != nil {
				return nil, fmt.Errorf("spec: bad count %q: %v", val, err)
			}
		case "elemsize":
			spec.ElemSize, err = strconv.Atoi(val)
			if err != nil {
				return nil, fmt.Errorf("spec: bad elemsize %q: %v", val, err)
			}
		case "params":
			spec.Params = nil
			for _, tok := range strings.Split(val, ",") {
				tok = strings.TrimSpace(tok)
				if tok == "" {
					continue
				}
				n, err := strconv.Atoi(tok)
				if err != nil {
					return nil, fmt.Errorf("spec: bad param length %q: %v", tok, err)
				}
				spec.Params = append(spec.Params, n)
			}
		}
	}
	if err := sc.Err(); err != nil {
		return nil, err
	}
	if spec.Kind == "" {
		return nil, fmt.Errorf("spec: missing kind")
	}
	return spec, nil
}

func (s *FrameSpec) Build() (FrontendMessage, error) {
	switch s.Kind {
	case "query":
		return &QueryMessage{Query: s.Content, Fill: s.Fill}, nil
	case "bind":
		params := make([]Param, 0, len(s.Params))
		for _, n := range s.Params {
			params = append(params, Param{DeclaredLen: n})
		}
		return &BindMessage{Portal: s.Portal, Statement: s.Stmt, Params: params}, nil
	case "copydata":
		return &CopyDataMessage{DeclaredLen: s.Fill, Data: []byte(s.Content)}, nil
	case "parse":
		return &ParseMessage{Name: s.Stmt, Query: s.Content, Fill: s.Fill}, nil
	case "execute":
		return &ExecuteMessage{Portal: s.Portal}, nil
	case "funcall":
		return &FunctionCallMessage{Args: []byte(s.Content), DeclaredLen: s.Fill}, nil
	case "batch":
		return &BatchMessage{Count: s.Count, ElemSize: s.ElemSize}, nil
	case "formats":
		return &FormatCodesMessage{Count: s.Count}, nil
	default:
		return nil, fmt.Errorf("spec: unknown kind %q", s.Kind)
	}
}
