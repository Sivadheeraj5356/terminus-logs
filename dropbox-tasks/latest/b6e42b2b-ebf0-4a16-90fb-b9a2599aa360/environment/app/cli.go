package app

import (
	"fmt"
	"os"
)

func Run(args []string) int {
	if len(args) < 1 {
		printUsage()
		return 2
	}
	switch args[0] {
	case "reload":
		profile, ok := flagValue(args, "--profile")
		if !ok {
			fmt.Fprintln(os.Stderr, "missing --profile")
			return 2
		}
		ReloadProfile(profile)
		return 0
	case "inspect":
		profile, ok := flagValue(args, "--profile")
		if !ok {
			fmt.Fprintln(os.Stderr, "missing --profile")
			return 2
		}
		InspectProfile(profile)
		return 0
	default:
		printUsage()
		return 2
	}
}

func flagValue(args []string, name string) (string, bool) {
	for i := 0; i < len(args)-1; i++ {
		if args[i] == name {
			return args[i+1], true
		}
	}
	return "", false
}

func printUsage() {
	fmt.Fprintln(os.Stderr, "usage: arctl reload --profile <name>")
	fmt.Fprintln(os.Stderr, "       arctl inspect --profile <name>")
}
