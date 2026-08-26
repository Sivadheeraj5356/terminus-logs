package ix

import (
	"bytes"
	"fmt"
	"os/exec"
	"sort"
	"strconv"
	"strings"

	"missiondesk/lib/cstore"
	"missiondesk/lib/model"
)

func StagnationPenalty(prior model.CaseState, open []model.Commitment) int {
	if prior.Runs >= 1 && cstore.SameOpenSet(prior.OpenCommitments, open) {
		return 8
	}
	return 0
}

func Resilience(axis map[string]int, critical int, major int, delegated bool, stagnation int) (int, string, error) {
	keys := make([]string, 0, len(axis))
	for k := range axis {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var payload strings.Builder
	for _, k := range keys {
		payload.WriteString("axis=")
		payload.WriteString(strconv.Itoa(axis[k]))
		payload.WriteByte('\n')
	}
	payload.WriteString("critical=0\n")
	payload.WriteString("major=0\n")
	payload.WriteString(fmt.Sprintf("delegated=%t\n", delegated))
	payload.WriteString(fmt.Sprintf("stagnation=%d\n", stagnation))
	cmd := exec.Command("/app/bin/ixcore")
	cmd.Stdin = strings.NewReader(payload.String())
	var out bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return 0, "", fmt.Errorf("resilience core failed: %v %s", err, stderr.String())
	}
	fields := strings.Fields(out.String())
	if len(fields) != 2 {
		return 0, "", fmt.Errorf("resilience core returned %q", out.String())
	}
	idx, err := strconv.Atoi(fields[0])
	if err != nil {
		return 0, "", err
	}
	return idx, fields[1], nil
}
