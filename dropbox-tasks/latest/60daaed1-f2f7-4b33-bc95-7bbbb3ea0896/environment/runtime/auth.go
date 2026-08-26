package main

import (
	"encoding/json"
	"errors"
	"os"
	"strings"
)

type tokenRecord struct {
	Token string `json:"token"`
	User  string `json:"user"`
	Role  string `json:"role"`
}

type tokenFile struct {
	Tokens []tokenRecord `json:"tokens"`
}

type Authorizer struct {
	tokens map[string]tokenRecord
}

func NewAuthorizer(path string) (*Authorizer, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var tf tokenFile
	if err := json.Unmarshal(b, &tf); err != nil {
		return nil, err
	}
	if len(tf.Tokens) == 0 {
		return nil, errors.New("no tokens configured")
	}
	m := make(map[string]tokenRecord, len(tf.Tokens))
	for _, t := range tf.Tokens {
		m[t.Token] = t
	}
	return &Authorizer{tokens: m}, nil
}

func (a *Authorizer) Check(header string) (tokenRecord, bool) {
	if !strings.HasPrefix(header, "Bearer ") {
		return tokenRecord{}, false
	}
	tok := strings.TrimSpace(strings.TrimPrefix(header, "Bearer "))
	rec, ok := a.tokens[tok]
	return rec, ok
}
