package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

// Fetch gate: decide whether an edge node may pull a resource from an upstream
// origin under a route's configured fetch source list.
//
// Reads one JSON object per line from standard input, each of the form
//
//	{"source_list": "...", "url": "...", "origin": "..."}
//
// and writes one line per input to standard output containing either
//
//	ADMIT
//
// or
//
//	BLOCK
//
// in the same order.
//
// The decision must follow the Content-Security-Policy Level 3 URL / source
// list matching algorithm so that legitimate resources are admitted and bypass
// attempts are blocked.
//
// The current implementation is a naive first cut. It only does rough
// scheme/host string checks and does not correctly implement 'self', host
// wildcards, port defaults, path prefixes, opaque schemes, or the CSP keywords,
// so it both admits some bypasses and blocks some legitimate resources.

// naiveHost extracts a lowercased host from the URL and reports whether the URL
// could be parsed at all.
func naiveHost(raw string) (string, bool) {
	if strings.ContainsAny(raw, " <>{}|\\^`\"") {
		return "", false
	}
	i := strings.Index(raw, "://")
	if i < 0 {
		return "", true
	}
	rest := raw[i+3:]
	if idx := strings.IndexAny(rest, "/?#"); idx >= 0 {
		rest = rest[:idx]
	}
	if at := strings.LastIndexByte(rest, '@'); at >= 0 {
		rest = rest[at+1:]
	}
	if c := strings.LastIndexByte(rest, ':'); c >= 0 {
		rest = rest[:c]
	}
	return strings.ToLower(rest), true
}

func admit(sourceList, url, _origin string) bool {
	tokens := strings.Fields(sourceList)
	if len(tokens) == 0 {
		return false
	}
	host, ok := naiveHost(url)
	if !ok {
		return false
	}
	host = strings.ToLower(host)

	for _, tok := range tokens {
		t := strings.ToLower(tok)
		// naive: any host token that appears as a substring of the URL host admits
		if strings.Contains(t, ".") {
			bare := strings.TrimPrefix(t, "*.")
			bare = strings.TrimPrefix(bare, "https://")
			bare = strings.TrimPrefix(bare, "http://")
			if strings.Contains(host, bare) {
				return true
			}
		}
		// naive scheme handling
		if strings.HasSuffix(t, ":") && strings.HasPrefix(strings.ToLower(url), t) {
			return true
		}
	}
	return false
}

type request struct {
	SourceList string `json:"source_list"`
	URL        string `json:"url"`
	Origin     string `json:"origin"`
}

func main() {
	scanner := bufio.NewScanner(os.Stdin)
	scanner.Buffer(make([]byte, 0, 1024*1024), 16*1024*1024)
	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var req request
		if err := json.Unmarshal([]byte(line), &req); err != nil {
			fmt.Fprintln(os.Stderr, "invalid input line:", err)
			os.Exit(1)
		}
		if admit(req.SourceList, req.URL, req.Origin) {
			fmt.Fprintln(w, "ADMIT")
		} else {
			fmt.Fprintln(w, "BLOCK")
		}
	}
}
