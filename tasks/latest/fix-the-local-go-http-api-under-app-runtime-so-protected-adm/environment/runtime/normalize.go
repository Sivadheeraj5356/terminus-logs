package main

import (
	"net/url"
	"path"
	"regexp"
	"strings"
)

var multiSlash = regexp.MustCompile(`/+`)

func canonicalDispatchPath(raw string) string {
	if raw == "" {
		return "/"
	}
	p := raw
	for i := 0; i < 3; i++ {
		d, err := url.PathUnescape(p)
		if err != nil || d == p {
			break
		}
		p = d
	}
	p = strings.ToLower(p)
	p = multiSlash.ReplaceAllString(p, "/")
	if !strings.HasPrefix(p, "/") {
		p = "/" + p
	}
	cp := path.Clean(p)
	if cp == "." {
		return "/"
	}
	return cp
}
