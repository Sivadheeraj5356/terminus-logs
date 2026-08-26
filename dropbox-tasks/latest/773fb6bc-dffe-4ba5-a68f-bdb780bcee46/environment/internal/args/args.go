package args

import (
	"fmt"
	"os"
	"strings"
)

type Cmd struct {
	Name string
	Flag map[string]string
	Pos  []string
}

func Parse(argv []string) (Cmd, error) {
	if len(argv) < 2 {
		return Cmd{}, fmt.Errorf("usage: cvctl <command> [flags]")
	}
	c := Cmd{Name: argv[1], Flag: map[string]string{}}
	for i := 2; i < len(argv); i++ {
		a := argv[i]
		if strings.HasPrefix(a, "--") {
			kv := strings.SplitN(strings.TrimPrefix(a, "--"), "=", 2)
			if len(kv) == 2 {
				c.Flag[kv[0]] = kv[1]
			} else if i+1 < len(argv) && !strings.HasPrefix(argv[i+1], "--") {
				i++
				c.Flag[kv[0]] = argv[i]
			} else {
				c.Flag[kv[0]] = "true"
			}
			continue
		}
		c.Pos = append(c.Pos, a)
	}
	return c, nil
}

func Root() string {
	if v := os.Getenv("CVCTL_ROOT"); v != "" {
		return v
	}
	return "/app/environment"
}
