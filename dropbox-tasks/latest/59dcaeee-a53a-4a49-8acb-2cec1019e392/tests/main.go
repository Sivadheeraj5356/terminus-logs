package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

type commandResult struct {
	Code   int
	Stdout string
	Stderr string
}

var binaryPath string

func runCommand(program string, args ...string) commandResult {
	cmd := exec.Command(program, args...)
	var stdout, stderr strings.Builder
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	err := cmd.Run()
	result := commandResult{Stdout: stdout.String(), Stderr: stderr.String()}
	if err != nil {
		if exit, ok := err.(*exec.ExitError); ok {
			result.Code = exit.ExitCode()
		} else {
			result.Code = -1
			if result.Stderr == "" {
				result.Stderr = err.Error()
			}
		}
	}
	return result
}

func buildBinary(appDir, root string) (string, error) {
	binary := filepath.Join(root, "rfimhyst")
	cmd := exec.Command("go", "build", "-o", binary, "./cmd/fieldloop")
	cmd.Dir = appDir
	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("fresh Go build failed: %s", output)
	}
	return binary, nil
}

func main() {
	appDir := os.Getenv("APP_DIR")
	if appDir == "" {
		appDir = "/app/environment"
	}
	root, err := os.MkdirTemp("", "rfim-verifier-")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	defer os.RemoveAll(root)
	binaryPath, err = buildBinary(appDir, root)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	cases := []struct {
		name string
		fn   func() error
	}{
		{"bundled minor-loop study", func() error { return bundledCase(binaryPath, appDir, root) }},
		{"multiple events, threshold ties, and cooperative rounds", func() error { return multiEventTieCase(binaryPath, root) }},
		{"current-field inclusive eligibility", func() error { return currentFieldEligibilityCase(binaryPath, root) }},
		{"array and endpoint-order invariance", func() error { return shuffledCase(binaryPath, root) }},
		{"three-way same-directory continuation", func() error { return splitSameDirectoryCase(binaryPath, root) }},
		{"complete field-history checkpoint binding", func() error { return fieldMutationRejectionCase(binaryPath, root) }},
		{"nested reversal return-point memory", func() error { return returnPointMemoryCase(binaryPath, root) }},
		{"determinism across alternate roots", func() error { return deterministicAlternateRootCase(binaryPath, root) }},
		{"invalid-input stale cleanup", func() error { return invalidCleanupCase(binaryPath, root) }},
		{"completed continuation", func() error { return completeResumeCase(binaryPath, root) }},
	}
	for _, test := range cases {
		if err := test.fn(); err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", test.name, err)
			os.Exit(1)
		}
		fmt.Printf("ok: %s\n", test.name)
	}
}
