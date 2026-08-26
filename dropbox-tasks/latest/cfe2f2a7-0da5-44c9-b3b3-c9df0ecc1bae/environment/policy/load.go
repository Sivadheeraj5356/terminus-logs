package policy

import (
	"encoding/json"
	"os"
)

type Rule struct {
	Pattern string `json:"pattern"`
	SLAMs   int    `json:"sla_ms"`
}

type Document struct {
	DefaultSLAMs int    `json:"default_sla_ms"`
	Rules        []Rule `json:"rules"`
}

func Load(path string) (Document, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Document{}, err
	}
	var doc Document
	if err := json.Unmarshal(raw, &doc); err != nil {
		return Document{}, err
	}
	return doc, nil
}

func FromMap(m map[string]interface{}) Document {
	doc := Document{}
	if v, ok := m["default_sla_ms"]; ok {
		if n, ok := v.(float64); ok {
			doc.DefaultSLAMs = int(n)
		}
	}
	if rules, ok := m["rules"].([]interface{}); ok {
		for _, item := range rules {
			ruleMap, ok := item.(map[string]interface{})
			if !ok {
				continue
			}
			rule := Rule{}
			if p, ok := ruleMap["pattern"].(string); ok {
				rule.Pattern = p
			}
			if s, ok := ruleMap["sla_ms"].(float64); ok {
				rule.SLAMs = int(s)
			}
			doc.Rules = append(doc.Rules, rule)
		}
	}
	return doc
}
