package cli

import (
	"fmt"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"siggate/internal/envelope"
	"siggate/internal/profile"
	"siggate/internal/verify"
)

var nowPattern = regexp.MustCompile(`^[0-9]+$`)

type ExitError struct {
	Code    int
	Message string
}

func (e *ExitError) Error() string { return e.Message }

func fail(reason string) error {
	return &ExitError{Code: 2, Message: "error: " + reason + "\n"}
}

func takeFlag(args []string, i int, name string) (value string, next int, ok bool) {
	a := args[i]
	if a == name {
		if i+1 >= len(args) {
			return "", i, false
		}
		return args[i+1], i + 1, true
	}
	prefix := name + "="
	if strings.HasPrefix(a, prefix) {
		return a[len(prefix):], i, true
	}
	return "", i, false
}

func Run(args []string) error {
	if len(args) == 0 || args[0] != "verify" {
		return fail("usage")
	}
	var encPath, keyPath, seenPath, profPath string
	var nowStr string
	var haveEnc, haveKey, haveNow, haveSeen, haveProf bool
	for i := 1; i < len(args); i++ {
		a := args[i]
		switch {
		case a == "--envelope" || strings.HasPrefix(a, "--envelope="):
			if haveEnc {
				return fail("usage")
			}
			v, ni, ok := takeFlag(args, i, "--envelope")
			if !ok {
				return fail("usage")
			}
			encPath = v
			haveEnc = true
			i = ni
		case a == "--keyring" || strings.HasPrefix(a, "--keyring="):
			if haveKey {
				return fail("usage")
			}
			v, ni, ok := takeFlag(args, i, "--keyring")
			if !ok {
				return fail("usage")
			}
			keyPath = v
			haveKey = true
			i = ni
		case a == "--now" || strings.HasPrefix(a, "--now="):
			if haveNow {
				return fail("usage")
			}
			v, ni, ok := takeFlag(args, i, "--now")
			if !ok {
				return fail("usage")
			}
			nowStr = v
			haveNow = true
			i = ni
		case a == "--profile" || strings.HasPrefix(a, "--profile="):
			if haveProf {
				return fail("usage")
			}
			v, ni, ok := takeFlag(args, i, "--profile")
			if !ok {
				return fail("usage")
			}
			profPath = v
			haveProf = true
			i = ni
		case a == "--seen" || strings.HasPrefix(a, "--seen="):
			if haveSeen {
				return fail("usage")
			}
			v, ni, ok := takeFlag(args, i, "--seen")
			if !ok {
				return fail("usage")
			}
			seenPath = v
			haveSeen = true
			i = ni
		default:
			return fail("usage")
		}
	}
	if !haveEnc || !haveKey || !haveNow || !haveProf || !haveSeen {
		return fail("usage")
	}
	if encPath == "" || keyPath == "" || nowStr == "" || profPath == "" || seenPath == "" {
		return fail("usage")
	}
	if !filepath.IsAbs(encPath) || !filepath.IsAbs(keyPath) || !filepath.IsAbs(profPath) || !filepath.IsAbs(seenPath) {
		return fail("usage")
	}
	if !nowPattern.MatchString(nowStr) {
		return fail("usage")
	}
	if len(nowStr) > 1 && nowStr[0] == '0' {
		return fail("usage")
	}
	now, err := strconv.ParseInt(nowStr, 10, 64)
	if err != nil {
		return fail("usage")
	}
	env, err := envelope.Load(encPath)
	if err != nil {
		return fail(err.Error())
	}
	kr, err := envelope.LoadKeyring(keyPath)
	if err != nil {
		return fail(err.Error())
	}
	prof, err := profile.Load(profPath)
	if err != nil {
		return fail(err.Error())
	}
	out, err := verify.Envelope(env, kr, now, seenPath, prof)
	if err != nil {
		return fail(err.Error())
	}
	fmt.Print(out)
	if !strings.HasSuffix(out, "\n") {
		fmt.Print("\n")
	}
	return nil
}
