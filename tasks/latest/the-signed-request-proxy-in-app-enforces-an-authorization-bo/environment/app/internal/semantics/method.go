package semantics

import (
	"fmt"
	"strings"
)

func NormalizeMethod(method string) (string, error) {
	if method == "" {
		return "", fmt.Errorf("empty method")
	}
	for _, c := range method {
		if c < 0x21 || c > 0x7E {
			return "", fmt.Errorf("invalid method character")
		}
	}
	return strings.ToUpper(method), nil
}
