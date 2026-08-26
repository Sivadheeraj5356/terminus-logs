package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"sort"
	"strconv"
	"strings"
	"syscall"
)

const (
	taskDir    = "/app/task_file"
	inputDir   = taskDir + "/input"
	outputDir  = taskDir + "/output"
	srcPath    = taskDir + "/src/token_audit.go"
	binPath    = taskDir + "/bin/token_audit"
	specPath   = taskDir + "/oidc_exchange_audit_spec.txt"
	publicPath = inputDir + "/public_exchange.txt"
	publicSHA  = "bbc11f687db0aa43c0b8b1bb744e0f91266efbb8411713af65e28b0f9e6ffce8"
	nobodyUID  = 65534
	nobodyGID  = 65534
)

type Issuer struct {
	ID   string
	Skew int64
}

type Key struct {
	ID        string
	Issuer    string
	Alg       string
	NotBefore int64
	NotAfter  int64
	Status    string
}

type Client struct {
	ID          string
	Issuer      string
	Status      string
	Tier        int64
	MaxTTL      int64
	RequirePKCE bool
	RequireDPOP bool
	Grants      map[string]bool
	Audiences   map[string]bool
}

type Resource struct {
	Audience string
	MinTier  int64
	Scopes   map[string]bool
}

type Action struct {
	ID         string
	Type       string
	Target     string
	Impact     int64
	Confidence int64
}

type ActionConflict struct {
	A string
	B string
}

type ActionPrerequisite struct {
	Child  string
	Parent string
}

type ActionBonus struct {
	A     string
	B     string
	Delta int64
}

type RemediationConfig struct {
	MaxActions           int
	MaxImpact            int64
	MinConfidence        int64
	Actions              []Action
	Conflicts            []ActionConflict
	Prerequisites        []ActionPrerequisite
	TypeLimits           map[string]int
	CoveredClientPenalty int64
	CoveredRootPenalty   int64
	Bonuses              []ActionBonus
}

type Event struct {
	ID              string
	Ts              int64
	Shard           string
	Seq             int64
	Client          string
	Subject         string
	Op              string
	JTI             string
	Parent          string
	Key             string
	Alg             string
	Grant           string
	Audience        string
	Scopes          []string
	ScopeSet        map[string]bool
	TTL             int64
	PKCE            string
	DPOP            string
	Nonce           string
	Depth           int64
	RootGrant       string
	RootPKCEGap     bool
	LineageWeakDPOP bool
}

type Case struct {
	Version          string
	Now              int64
	Issuers          map[string]Issuer
	Keys             map[string]Key
	Clients          map[string]Client
	Resources        map[string]Resource
	MaxExchangeDepth int64
	MaxChainLifetime int64
	Events           []Event
	Retractions      map[string]bool
	Remediation      RemediationConfig
}

type Token struct {
	JTI             string
	Client          string
	Subject         string
	Audience        string
	Scopes          []string
	ScopeSet        map[string]bool
	Expires         int64
	Key             string
	Risk            int64
	Revoked         bool
	RootJTI         string
	Depth           int64
	RootIssuedAt    int64
	RootGrant       string
	RootPKCEGap     bool
	LineageWeakDPOP bool
	ParentJTI       string
}

type Totals struct {
	Issued         int   `json:"issued"`
	RejectedEvents int   `json:"rejected_events"`
	Active         int   `json:"active"`
	Revoked        int   `json:"revoked"`
	Risk           int64 `json:"risk"`
}

type ActiveRow struct {
	JTI       string   `json:"jti"`
	Client    string   `json:"client"`
	Subject   string   `json:"subject"`
	Audience  string   `json:"audience"`
	Scopes    []string `json:"scopes"`
	ExpiresAt int64    `json:"expires_at"`
	Key       string   `json:"key"`
	Root      string   `json:"root"`
	Depth     int64    `json:"depth"`
	Risk      int64    `json:"risk"`
}

type RejectedRow struct {
	Event   string   `json:"event"`
	Reasons []string `json:"reasons"`
}

type ClientRow struct {
	Client         string `json:"client"`
	Issued         int    `json:"issued"`
	Active         int    `json:"active"`
	RejectedEvents int    `json:"rejected_events"`
	Risk           int64  `json:"risk"`
}

type RemediationTotals struct {
	Actions       int   `json:"actions"`
	Impact        int64 `json:"impact"`
	CoveredTokens int   `json:"covered_tokens"`
	Confidence    int64 `json:"confidence"`
}

type SelectedActionRow struct {
	ID         string   `json:"id"`
	Type       string   `json:"type"`
	Target     string   `json:"target"`
	Covers     []string `json:"covers"`
	Impact     int64    `json:"impact"`
	Confidence int64    `json:"confidence"`
}

type RejectedActionRow struct {
	ID      string   `json:"id"`
	Reasons []string `json:"reasons"`
}

type RemediationReport struct {
	Score        int64               `json:"score"`
	ResidualRisk int64               `json:"residual_risk"`
	Totals       RemediationTotals   `json:"totals"`
	Selected     []SelectedActionRow `json:"selected"`
	Rejected     []RejectedActionRow `json:"rejected"`
}

type Report struct {
	Now         int64             `json:"now"`
	Totals      Totals            `json:"totals"`
	Active      []ActiveRow       `json:"active"`
	Rejected    []RejectedRow     `json:"rejected"`
	Clients     []ClientRow       `json:"clients"`
	Remediation RemediationReport `json:"remediation"`
}

type clientStats struct {
	issued   int
	active   int
	rejected int
	risk     int64
}

type parser struct {
	tokens []string
	pos    int
}

type actionCandidate struct {
	Action Action
	Covers []string
}

type planChoice struct {
	Selected []int
	Score    int64
	Covered  int
	Impact   int64
	Conf     int64
	IDs      []string
}

type namedCase struct {
	name string
	text string
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run() error {
	fmt.Println("Building candidate")
	if err := buildCandidate(); err != nil {
		return err
	}
	if err := sealVerifierPaths(); err != nil {
		return err
	}

	checks := []struct {
		name string
		fn   func() error
	}{
		{"public_input_integrity", testPublicInputIntegrity},
		{"required_go_artifacts_exist_and_are_native", testRequiredGoArtifactsExistAndAreNative},
		{"cli_rejects_wrong_argument_order", testCLIRejectsWrongArgumentOrder},
		{"cli_rejects_extra_arguments", testCLIRejectsExtraArguments},
		{"cli_rejects_repeated_arguments", testCLIRejectsRepeatedArguments},
		{"cli_rejects_missing_arguments", testCLIRejectsMissingArguments},
		{"malformed_input_rejected", testMalformedInputRejected},
		{"public_case_matches_spec", testPublicCaseMatchesSpec},
	}
	fmt.Println("Running behavior checks")
	for _, check := range checks {
		if err := check.fn(); err != nil {
			return fmt.Errorf("%s: %w", check.name, err)
		}
		fmt.Printf("PASS %s\n", check.name)
	}

	fmt.Println("Running hidden cases")
	for _, tc := range hiddenCases() {
		if err := assertCaseMatches(tc.name, tc.text); err != nil {
			return fmt.Errorf("%s: %w", tc.name, err)
		}
		fmt.Printf("PASS %s\n", tc.name)
	}
	return nil
}

func buildCandidate() error {
	source, err := os.ReadFile(srcPath)
	if err != nil {
		return fmt.Errorf("missing %s: %w", srcPath, err)
	}
	sourceText := string(source)
	forbidden := []string{
		"os/exec",
		"exec.Command",
		"python",
		"curl ",
		"wget ",
		"/tests",
		"/solution",
		"syscall",
		"StartProcess",
		"ForkExec",
		"SysProcAttr",
	}
	found := []string{}
	for _, needle := range forbidden {
		if strings.Contains(sourceText, needle) {
			found = append(found, needle)
		}
	}
	if len(found) > 0 {
		return fmt.Errorf("source shells out or delegates work: %v", found)
	}

	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(binPath), 0o755); err != nil {
		return err
	}
	_ = os.Remove(binPath)
	cmd := exec.Command("go", "build", "-o", binPath, srcPath)
	cmd.Dir = "/app"
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("go build failed: %v\n%s", err, string(out))
	}
	return nil
}

func sealVerifierPaths() error {
	for _, path := range []string{"/tests"} {
		if err := filepath.Walk(path, func(current string, info os.FileInfo, err error) error {
			if err != nil {
				return err
			}
			if info.IsDir() {
				return os.Chmod(current, 0o700)
			}
			return os.Chmod(current, 0o600)
		}); err != nil {
			return fmt.Errorf("failed to seal %s: %w", path, err)
		}
	}
	return nil
}

func testPublicInputIntegrity() error {
	sum, err := sha256File(publicPath)
	if err != nil {
		return err
	}
	if sum != publicSHA {
		return fmt.Errorf("public input sha256 mismatch: got %s", sum)
	}
	return nil
}

func testRequiredGoArtifactsExistAndAreNative() error {
	for _, path := range []string{srcPath, specPath, binPath} {
		if _, err := os.Stat(path); err != nil {
			return fmt.Errorf("missing %s", path)
		}
	}
	info, err := os.Stat(binPath)
	if err != nil {
		return err
	}
	if info.Mode()&0o100 == 0 {
		return fmt.Errorf("binary is not executable")
	}
	header, err := os.ReadFile(binPath)
	if err != nil {
		return err
	}
	if len(header) < 4 || !bytes.Equal(header[:4], []byte{0x7f, 'E', 'L', 'F'}) {
		return fmt.Errorf("token_audit must be a native ELF binary")
	}
	return nil
}

func testCLIRejectsWrongArgumentOrder() error {
	tmpDir, err := os.MkdirTemp("", "oidc-wrong-order-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tmpDir)
	if err := os.Chmod(tmpDir, 0o777); err != nil {
		return err
	}
	outputPath := filepath.Join(tmpDir, "wrong_order.json")
	code, _, err := runCandidate([]string{"--output", outputPath, "--input", publicPath})
	if err != nil {
		return err
	}
	if code == 0 {
		return fmt.Errorf("expected non-zero exit code")
	}
	if _, err := os.Stat(outputPath); err == nil {
		return fmt.Errorf("output file should not be created")
	}
	return nil
}

func testCLIRejectsExtraArguments() error {
	tmpDir, err := os.MkdirTemp("", "oidc-extra-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tmpDir)
	if err := os.Chmod(tmpDir, 0o777); err != nil {
		return err
	}
	outputPath := filepath.Join(tmpDir, "extra.json")
	code, _, err := runCandidate([]string{"--input", publicPath, "--output", outputPath, "--verbose"})
	if err != nil {
		return err
	}
	if code == 0 {
		return fmt.Errorf("expected non-zero exit code")
	}
	if _, err := os.Stat(outputPath); err == nil {
		return fmt.Errorf("output file should not be created")
	}
	return nil
}

func testCLIRejectsRepeatedArguments() error {
	tmpDir, err := os.MkdirTemp("", "oidc-repeat-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tmpDir)
	if err := os.Chmod(tmpDir, 0o777); err != nil {
		return err
	}
	outputPath := filepath.Join(tmpDir, "repeat.json")
	code, _, err := runCandidate([]string{"--input", publicPath, "--output", outputPath, "--output", filepath.Join(tmpDir, "other.json")})
	if err != nil {
		return err
	}
	if code == 0 {
		return fmt.Errorf("expected non-zero exit code")
	}
	if _, err := os.Stat(outputPath); err == nil {
		return fmt.Errorf("output file should not be created")
	}
	return nil
}

func testCLIRejectsMissingArguments() error {
	code, _, err := runCandidate([]string{"--input", publicPath})
	if err != nil {
		return err
	}
	if code == 0 {
		return fmt.Errorf("expected non-zero exit code")
	}
	return nil
}

func testMalformedInputRejected() error {
	tmpDir, err := os.MkdirTemp("", "oidc-bad-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tmpDir)
	if err := os.Chmod(tmpDir, 0o777); err != nil {
		return err
	}
	inputPath := filepath.Join(tmpDir, "bad.txt")
	outputPath := filepath.Join(tmpDir, "bad.json")
	if err := os.WriteFile(inputPath, []byte("OIDC_EXCHANGE_AUDIT 1\nBROKEN\n"), 0o644); err != nil {
		return err
	}
	code, _, err := runCandidate([]string{"--input", inputPath, "--output", outputPath})
	if err != nil {
		return err
	}
	if code == 0 {
		return fmt.Errorf("expected non-zero exit code")
	}
	if _, err := os.Stat(outputPath); err == nil {
		return fmt.Errorf("output file should not be created")
	}
	return nil
}

func testPublicCaseMatchesSpec() error {
	data, err := os.ReadFile(publicPath)
	if err != nil {
		return err
	}
	return assertCaseMatches("public_exchange", string(data))
}

func hiddenCases() []namedCase {
	cases := []namedCase{
		{"empty_ledger", emptyCase()},
		{"edge_boundaries", edgeCase()},
		{"lineage_dependencies", lineageDependencyCase()},
		{"retraction_lineage", retractionLineageCase()},
		{"v3_bonus_penalty", v3BonusPenaltyCase()},
		{"v3_type_limit_closure", v3TypeLimitClosureCase()},
	}
	for i := 0; i < 24; i++ {
		version := []int{1, 2, 3}[i%3]
		cases = append(cases, namedCase{
			name: fmt.Sprintf("generated_v%d_%d", version, i),
			text: generatedCase(i, version, i%4 == 1, i%3 == 2),
		})
	}
	return cases
}

func assertCaseMatches(caseName, caseText string) error {
	tmpDir, err := os.MkdirTemp("", "oidc-case-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tmpDir)
	if err := os.Chmod(tmpDir, 0o777); err != nil {
		return err
	}
	inputPath := filepath.Join(tmpDir, caseName+".txt")
	outputPath := filepath.Join(tmpDir, caseName+".json")
	if err := os.WriteFile(inputPath, []byte(caseText), 0o644); err != nil {
		return err
	}
	expected := audit(parseCaseText(caseText))
	code, out, err := runCandidate([]string{"--input", inputPath, "--output", outputPath})
	if err != nil {
		return err
	}
	if code != 0 {
		return fmt.Errorf("candidate failed with exit %d\n%s", code, out)
	}
	actualBytes, err := os.ReadFile(outputPath)
	if err != nil {
		return err
	}
	if err := validateSchema(actualBytes); err != nil {
		return err
	}
	return compareJSON(actualBytes, expected)
}

func runCandidate(args []string) (int, string, error) {
	cmd := exec.Command(binPath, args...)
	cmd.Dir = "/app"
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Credential: &syscall.Credential{
			Uid: nobodyUID,
			Gid: nobodyGID,
		},
	}
	output, err := cmd.CombinedOutput()
	if err == nil {
		return 0, string(output), nil
	}
	var exitErr *exec.ExitError
	if errors.As(err, &exitErr) {
		return exitErr.ExitCode(), string(output), nil
	}
	return -1, string(output), err
}

func validateSchema(actualBytes []byte) error {
	var data map[string]any
	if err := json.Unmarshal(actualBytes, &data); err != nil {
		return fmt.Errorf("invalid json: %w", err)
	}
	if !keysEqual(data, []string{"now", "totals", "active", "rejected", "clients", "remediation"}) {
		return fmt.Errorf("top-level keys mismatch")
	}
	if _, ok := data["now"].(float64); !ok {
		return fmt.Errorf("now must be integer")
	}
	totals, ok := data["totals"].(map[string]any)
	if !ok || !keysEqual(totals, []string{"issued", "rejected_events", "active", "revoked", "risk"}) {
		return fmt.Errorf("totals schema mismatch")
	}
	for _, field := range []string{"issued", "rejected_events", "active", "revoked", "risk"} {
		if _, ok := totals[field].(float64); !ok {
			return fmt.Errorf("totals.%s must be integer", field)
		}
	}
	active, ok := data["active"].([]any)
	if !ok {
		return fmt.Errorf("active must be array")
	}
	activeJTIs := []string{}
	for _, item := range active {
		row, ok := item.(map[string]any)
		if !ok || !keysEqual(row, []string{"jti", "client", "subject", "audience", "scopes", "expires_at", "key", "root", "depth", "risk"}) {
			return fmt.Errorf("active row schema mismatch")
		}
		for _, field := range []string{"jti", "client", "subject", "audience", "key", "root"} {
			if _, ok := row[field].(string); !ok {
				return fmt.Errorf("active.%s must be string", field)
			}
		}
		scopes, ok := row["scopes"].([]any)
		if !ok {
			return fmt.Errorf("scopes must be array")
		}
		scopeStrings := []string{}
		for _, scope := range scopes {
			s, ok := scope.(string)
			if !ok {
				return fmt.Errorf("scope must be string")
			}
			scopeStrings = append(scopeStrings, s)
		}
		if !sort.StringsAreSorted(scopeStrings) {
			return fmt.Errorf("scopes must be sorted")
		}
		if _, ok := row["expires_at"].(float64); !ok {
			return fmt.Errorf("expires_at must be integer")
		}
		if _, ok := row["depth"].(float64); !ok {
			return fmt.Errorf("depth must be integer")
		}
		if _, ok := row["risk"].(float64); !ok {
			return fmt.Errorf("risk must be integer")
		}
		activeJTIs = append(activeJTIs, row["jti"].(string))
	}
	if !sort.StringsAreSorted(activeJTIs) {
		return fmt.Errorf("active must be sorted by jti")
	}
	rejected, ok := data["rejected"].([]any)
	if !ok {
		return fmt.Errorf("rejected must be array")
	}
	for _, item := range rejected {
		row, ok := item.(map[string]any)
		if !ok || !keysEqual(row, []string{"event", "reasons"}) {
			return fmt.Errorf("rejected row schema mismatch")
		}
		if _, ok := row["event"].(string); !ok {
			return fmt.Errorf("rejected.event must be string")
		}
		reasons, ok := row["reasons"].([]any)
		if !ok {
			return fmt.Errorf("rejected.reasons must be array")
		}
		for _, reason := range reasons {
			if _, ok := reason.(string); !ok {
				return fmt.Errorf("rejected reason must be string")
			}
		}
	}
	clients, ok := data["clients"].([]any)
	if !ok {
		return fmt.Errorf("clients must be array")
	}
	clientIDs := []string{}
	for _, item := range clients {
		row, ok := item.(map[string]any)
		if !ok || !keysEqual(row, []string{"client", "issued", "active", "rejected_events", "risk"}) {
			return fmt.Errorf("clients row schema mismatch")
		}
		id, ok := row["client"].(string)
		if !ok {
			return fmt.Errorf("clients.client must be string")
		}
		clientIDs = append(clientIDs, id)
		for _, field := range []string{"issued", "active", "rejected_events", "risk"} {
			if _, ok := row[field].(float64); !ok {
				return fmt.Errorf("clients.%s must be integer", field)
			}
		}
	}
	if !sort.StringsAreSorted(clientIDs) {
		return fmt.Errorf("clients must be sorted")
	}
	rem, ok := data["remediation"].(map[string]any)
	if !ok || !keysEqual(rem, []string{"score", "residual_risk", "totals", "selected", "rejected"}) {
		return fmt.Errorf("remediation schema mismatch")
	}
	for _, field := range []string{"score", "residual_risk"} {
		if _, ok := rem[field].(float64); !ok {
			return fmt.Errorf("remediation.%s must be integer", field)
		}
	}
	remTotals, ok := rem["totals"].(map[string]any)
	if !ok || !keysEqual(remTotals, []string{"actions", "impact", "covered_tokens", "confidence"}) {
		return fmt.Errorf("remediation.totals schema mismatch")
	}
	for _, field := range []string{"actions", "impact", "covered_tokens", "confidence"} {
		if _, ok := remTotals[field].(float64); !ok {
			return fmt.Errorf("remediation.totals.%s must be integer", field)
		}
	}
	selected, ok := rem["selected"].([]any)
	if !ok {
		return fmt.Errorf("remediation.selected must be array")
	}
	selectedIDs := []string{}
	for _, item := range selected {
		row, ok := item.(map[string]any)
		if !ok || !keysEqual(row, []string{"id", "type", "target", "covers", "impact", "confidence"}) {
			return fmt.Errorf("selected row schema mismatch")
		}
		for _, field := range []string{"id", "type", "target"} {
			if _, ok := row[field].(string); !ok {
				return fmt.Errorf("selected.%s must be string", field)
			}
		}
		selectedIDs = append(selectedIDs, row["id"].(string))
		covers, ok := row["covers"].([]any)
		if !ok {
			return fmt.Errorf("selected.covers must be array")
		}
		coverIDs := []string{}
		for _, cover := range covers {
			s, ok := cover.(string)
			if !ok {
				return fmt.Errorf("cover must be string")
			}
			coverIDs = append(coverIDs, s)
		}
		if !sort.StringsAreSorted(coverIDs) {
			return fmt.Errorf("selected.covers must be sorted")
		}
		for _, field := range []string{"impact", "confidence"} {
			if _, ok := row[field].(float64); !ok {
				return fmt.Errorf("selected.%s must be integer", field)
			}
		}
	}
	if !sort.StringsAreSorted(selectedIDs) {
		return fmt.Errorf("selected must be sorted by id")
	}
	rejectedActions, ok := rem["rejected"].([]any)
	if !ok {
		return fmt.Errorf("remediation.rejected must be array")
	}
	rejectedIDs := []string{}
	for _, item := range rejectedActions {
		row, ok := item.(map[string]any)
		if !ok || !keysEqual(row, []string{"id", "reasons"}) {
			return fmt.Errorf("rejected action schema mismatch")
		}
		id, ok := row["id"].(string)
		if !ok {
			return fmt.Errorf("rejected action id must be string")
		}
		rejectedIDs = append(rejectedIDs, id)
		reasons, ok := row["reasons"].([]any)
		if !ok {
			return fmt.Errorf("rejected action reasons must be array")
		}
		for _, reason := range reasons {
			if _, ok := reason.(string); !ok {
				return fmt.Errorf("rejected action reason must be string")
			}
		}
	}
	if !sort.StringsAreSorted(rejectedIDs) {
		return fmt.Errorf("rejected actions must be sorted by id")
	}
	return nil
}

func compareJSON(actualBytes []byte, expected Report) error {
	var actual any
	if err := json.Unmarshal(actualBytes, &actual); err != nil {
		return err
	}
	expectedBytes, err := json.Marshal(expected)
	if err != nil {
		return err
	}
	var expectedAny any
	if err := json.Unmarshal(expectedBytes, &expectedAny); err != nil {
		return err
	}
	if !reflect.DeepEqual(actual, expectedAny) {
		prettyExpected, _ := json.MarshalIndent(expectedAny, "", "  ")
		prettyActual, _ := json.MarshalIndent(actual, "", "  ")
		return fmt.Errorf("output mismatch\nexpected:\n%s\nactual:\n%s", string(prettyExpected), string(prettyActual))
	}
	return nil
}

func compareJSONBytes(actualBytes []byte, expectedBytes []byte) error {
	var actual any
	if err := json.Unmarshal(actualBytes, &actual); err != nil {
		return err
	}
	var expected any
	if err := json.Unmarshal(expectedBytes, &expected); err != nil {
		return err
	}
	if !reflect.DeepEqual(actual, expected) {
		prettyExpected, _ := json.MarshalIndent(expected, "", "  ")
		prettyActual, _ := json.MarshalIndent(actual, "", "  ")
		return fmt.Errorf("output mismatch\nexpected:\n%s\nactual:\n%s", string(prettyExpected), string(prettyActual))
	}
	return nil
}

func keysEqual(m map[string]any, expected []string) bool {
	if len(m) != len(expected) {
		return false
	}
	for _, key := range expected {
		if _, ok := m[key]; !ok {
			return false
		}
	}
	return true
}

func sha256File(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(data)
	return fmt.Sprintf("%x", sum[:]), nil
}

func newParser(data string) *parser {
	return &parser{tokens: strings.Fields(data)}
}

func (p *parser) take() string {
	if p.pos >= len(p.tokens) {
		panic("unexpected end of input")
	}
	value := p.tokens[p.pos]
	p.pos++
	return value
}

func (p *parser) expect(expected string) {
	value := p.take()
	if value != expected {
		panic(fmt.Sprintf("expected %s, got %s", expected, value))
	}
}

func (p *parser) int64() int64 {
	value, err := strconv.ParseInt(p.take(), 10, 64)
	if err != nil {
		panic(err)
	}
	return value
}

func boolYes(value string) bool {
	return value == "yes"
}

func csvSet(value string) (map[string]bool, []string) {
	out := map[string]bool{}
	if value == "-" {
		return out, []string{}
	}
	for _, item := range strings.Split(value, ",") {
		if item == "" {
			continue
		}
		out[item] = true
	}
	keys := make([]string, 0, len(out))
	for key := range out {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return out, keys
}

func subset(a map[string]bool, b map[string]bool) bool {
	for item := range a {
		if !b[item] {
			return false
		}
	}
	return true
}

func parseCaseText(data string) Case {
	p := newParser(data)
	p.expect("OIDC_EXCHANGE_AUDIT")
	version := p.take()
	c := Case{
		Version:     version,
		Issuers:     map[string]Issuer{},
		Keys:        map[string]Key{},
		Clients:     map[string]Client{},
		Resources:   map[string]Resource{},
		Retractions: map[string]bool{},
		Remediation: RemediationConfig{
			TypeLimits: map[string]int{},
		},
	}
	p.expect("NOW")
	c.Now = p.int64()

	p.expect("ISSUERS")
	issuerCount := p.int64()
	for i := int64(0); i < issuerCount; i++ {
		p.expect("ISSUER")
		id := p.take()
		c.Issuers[id] = Issuer{ID: id, Skew: p.int64()}
	}

	p.expect("KEYS")
	keyCount := p.int64()
	for i := int64(0); i < keyCount; i++ {
		p.expect("KEY")
		id := p.take()
		c.Keys[id] = Key{
			ID:        id,
			Issuer:    p.take(),
			Alg:       p.take(),
			NotBefore: p.int64(),
			NotAfter:  p.int64(),
			Status:    p.take(),
		}
	}

	p.expect("CLIENTS")
	clientCount := p.int64()
	for i := int64(0); i < clientCount; i++ {
		p.expect("CLIENT")
		id := p.take()
		issuer := p.take()
		status := p.take()
		tier := p.int64()
		maxTTL := p.int64()
		requirePKCE := boolYes(p.take())
		requireDPOP := boolYes(p.take())
		grants, _ := csvSet(p.take())
		audiences, _ := csvSet(p.take())
		c.Clients[id] = Client{
			ID:          id,
			Issuer:      issuer,
			Status:      status,
			Tier:        tier,
			MaxTTL:      maxTTL,
			RequirePKCE: requirePKCE,
			RequireDPOP: requireDPOP,
			Grants:      grants,
			Audiences:   audiences,
		}
	}

	p.expect("RESOURCES")
	resourceCount := p.int64()
	for i := int64(0); i < resourceCount; i++ {
		p.expect("RESOURCE")
		aud := p.take()
		minTier := p.int64()
		scopes, _ := csvSet(p.take())
		c.Resources[aud] = Resource{Audience: aud, MinTier: minTier, Scopes: scopes}
	}

	p.expect("POLICY")
	c.MaxExchangeDepth = p.int64()
	c.MaxChainLifetime = p.int64()

	p.expect("EVENTS")
	eventCount := p.int64()
	for i := int64(0); i < eventCount; i++ {
		p.expect("EVENT")
		ev := Event{
			ID:      p.take(),
			Ts:      p.int64(),
			Shard:   p.take(),
			Seq:     p.int64(),
			Client:  p.take(),
			Subject: p.take(),
			Op:      p.take(),
		}
		switch ev.Op {
		case "MINT":
			ev.JTI = p.take()
			ev.Key = p.take()
			ev.Alg = p.take()
			ev.Grant = p.take()
			ev.Audience = p.take()
			ev.ScopeSet, ev.Scopes = csvSet(p.take())
			ev.TTL = p.int64()
			ev.PKCE = p.take()
			ev.DPOP = p.take()
			ev.Nonce = p.take()
		case "EXCHANGE":
			ev.JTI = p.take()
			ev.Parent = p.take()
			ev.Key = p.take()
			ev.Alg = p.take()
			ev.Grant = "exchange"
			ev.Audience = p.take()
			ev.ScopeSet, ev.Scopes = csvSet(p.take())
			ev.TTL = p.int64()
			ev.DPOP = p.take()
			ev.Nonce = p.take()
		case "REVOKE":
			ev.JTI = p.take()
		default:
			panic("unknown operation " + ev.Op)
		}
		c.Events = append(c.Events, ev)
	}

	if c.Version != "1" {
		p.expect("RETRACTIONS")
		retractionCount := p.int64()
		for i := int64(0); i < retractionCount; i++ {
			p.expect("RETRACT")
			c.Retractions[p.take()] = true
		}
	}
	p.expect("REMEDIATION")
	c.Remediation.MaxActions = int(p.int64())
	c.Remediation.MaxImpact = p.int64()
	c.Remediation.MinConfidence = p.int64()

	p.expect("ACTIONS")
	actionCount := p.int64()
	for i := int64(0); i < actionCount; i++ {
		p.expect("ACTION")
		c.Remediation.Actions = append(c.Remediation.Actions, Action{
			ID:         p.take(),
			Type:       p.take(),
			Target:     p.take(),
			Impact:     p.int64(),
			Confidence: p.int64(),
		})
	}

	p.expect("ACTION_CONFLICTS")
	conflictCount := p.int64()
	for i := int64(0); i < conflictCount; i++ {
		p.expect("ACTION_CONFLICT")
		c.Remediation.Conflicts = append(c.Remediation.Conflicts, ActionConflict{A: p.take(), B: p.take()})
	}

	p.expect("ACTION_PREREQUISITES")
	prereqCount := p.int64()
	for i := int64(0); i < prereqCount; i++ {
		p.expect("ACTION_PREREQ")
		c.Remediation.Prerequisites = append(c.Remediation.Prerequisites, ActionPrerequisite{Child: p.take(), Parent: p.take()})
	}

	if c.Version == "3" {
		p.expect("ACTION_TYPE_LIMITS")
		typeLimitCount := p.int64()
		for i := int64(0); i < typeLimitCount; i++ {
			p.expect("ACTION_TYPE_LIMIT")
			c.Remediation.TypeLimits[p.take()] = int(p.int64())
		}
		p.expect("PLAN_TUNING")
		c.Remediation.CoveredClientPenalty = p.int64()
		c.Remediation.CoveredRootPenalty = p.int64()
		p.expect("ACTION_BONUSES")
		bonusCount := p.int64()
		for i := int64(0); i < bonusCount; i++ {
			p.expect("ACTION_BONUS")
			c.Remediation.Bonuses = append(c.Remediation.Bonuses, ActionBonus{
				A:     p.take(),
				B:     p.take(),
				Delta: p.int64(),
			})
		}
	}

	p.expect("END")
	if p.pos != len(p.tokens) {
		panic("trailing tokens")
	}
	return c
}

func orderedEvents(c Case) []Event {
	events := make([]Event, 0, len(c.Events))
	for _, ev := range c.Events {
		if c.Retractions[ev.ID] {
			continue
		}
		events = append(events, ev)
	}
	sort.Slice(events, func(i, j int) bool {
		a, b := events[i], events[j]
		if a.Ts != b.Ts {
			return a.Ts < b.Ts
		}
		if a.Shard != b.Shard {
			return a.Shard < b.Shard
		}
		if a.Seq != b.Seq {
			return a.Seq < b.Seq
		}
		return a.ID < b.ID
	})
	return events
}

func keyActive(c Case, key Key, ev Event, client Client, clientOK bool) bool {
	skew := int64(0)
	if issuer, ok := c.Issuers[key.Issuer]; ok {
		skew = issuer.Skew
	}
	if key.Status != "active" {
		return false
	}
	if clientOK && key.Issuer != client.Issuer {
		return false
	}
	return key.NotBefore-skew <= ev.Ts && ev.Ts <= key.NotAfter+skew
}

func tokenReasons(c Case, ev Event, tokens map[string]*Token, nonces map[string]map[string]bool) []string {
	reasons := []string{}
	client, clientOK := c.Clients[ev.Client]
	if !clientOK {
		reasons = append(reasons, "unknown_client")
	} else if client.Status != "active" {
		reasons = append(reasons, "client_disabled")
	}

	key, keyOK := c.Keys[ev.Key]
	if !keyOK {
		reasons = append(reasons, "unknown_key")
	} else {
		if !keyActive(c, key, ev, client, clientOK) {
			reasons = append(reasons, "key_inactive")
		}
		if ev.Alg != key.Alg {
			reasons = append(reasons, "alg_mismatch")
		}
	}

	resource, resourceOK := c.Resources[ev.Audience]
	if !resourceOK {
		reasons = append(reasons, "unknown_resource")
	}
	if clientOK && resourceOK && client.Tier < resource.MinTier {
		reasons = append(reasons, "tier_insufficient")
	}
	if clientOK && !client.Grants[ev.Grant] {
		reasons = append(reasons, "grant_not_allowed")
	}
	if clientOK && !client.Audiences[ev.Audience] {
		reasons = append(reasons, "audience_not_allowed")
	}
	if resourceOK && !subset(ev.ScopeSet, resource.Scopes) {
		reasons = append(reasons, "scope_not_allowed")
	}
	if clientOK && ev.TTL > client.MaxTTL {
		reasons = append(reasons, "ttl_exceeded")
	}
	if ev.Op == "MINT" && clientOK && client.RequirePKCE && ev.PKCE != "yes" {
		reasons = append(reasons, "pkce_required")
	}
	if clientOK && client.RequireDPOP && ev.DPOP != "yes" {
		reasons = append(reasons, "dpop_required")
	}

	if ev.Op == "EXCHANGE" {
		parent, parentOK := tokens[ev.Parent]
		if !parentOK {
			reasons = append(reasons, "parent_missing")
		} else {
			if parent.Revoked || ev.Ts >= parent.Expires {
				reasons = append(reasons, "parent_inactive")
			}
			if parent.Client != ev.Client || parent.Subject != ev.Subject {
				reasons = append(reasons, "subject_mismatch")
			}
			if !subset(ev.ScopeSet, parent.ScopeSet) {
				reasons = append(reasons, "scope_escalation")
			}
			if parent.Depth+1 > c.MaxExchangeDepth {
				reasons = append(reasons, "depth_exceeded")
			}
			if ev.Ts+ev.TTL > parent.RootIssuedAt+c.MaxChainLifetime {
				reasons = append(reasons, "chain_expiry_exceeded")
			}
		}
	}

	if ev.Nonce != "-" {
		key := ev.Client + "\x00" + ev.Subject
		if nonces[key] != nil && nonces[key][ev.Nonce] {
			reasons = append(reasons, "replay_nonce")
		}
	}
	return reasons
}

func tokenRisk(c Case, ev Event) int64 {
	resource := c.Resources[ev.Audience]
	risk := ev.TTL + 5*int64(len(ev.Scopes)) + 10*resource.MinTier
	switch ev.Grant {
	case "password":
		risk += 100
	case "client_credentials":
		risk += 25
	case "exchange":
		risk += 40
	default:
		risk += 10
	}
	if ev.DPOP == "no" {
		risk += 40
	}
	if ev.Op == "MINT" && ev.PKCE == "no" {
		risk += 20
	}
	risk += 15 * ev.Depth
	switch ev.RootGrant {
	case "password":
		risk += 35
	case "client_credentials":
		risk += 15
	}
	if ev.LineageWeakDPOP {
		risk += 20
	}
	if ev.RootPKCEGap {
		risk += 10
	}
	return risk
}

func activeTokenMap(c Case, tokens map[string]*Token) map[string]*Token {
	active := map[string]*Token{}
	for jti, token := range tokens {
		if !token.Revoked && c.Now < token.Expires {
			active[jti] = token
		}
	}
	return active
}

func sortedKeys(m map[string]bool) []string {
	keys := make([]string, 0, len(m))
	for key := range m {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func isDescendant(token *Token, ancestorJTI string, tokens map[string]*Token) bool {
	current := token
	for current != nil {
		if current.JTI == ancestorJTI {
			return true
		}
		if current.ParentJTI == "" {
			return false
		}
		current = tokens[current.ParentJTI]
	}
	return false
}

func actionCovers(c Case, action Action, tokens map[string]*Token, active map[string]*Token) (bool, []string) {
	covered := map[string]bool{}
	targetKnown := false

	switch action.Type {
	case "REVOKE_TOKEN":
		if _, ok := tokens[action.Target]; ok {
			targetKnown = true
			if active[action.Target] != nil {
				covered[action.Target] = true
			}
		}
	case "REVOKE_LINEAGE":
		if _, ok := tokens[action.Target]; ok {
			targetKnown = true
			for jti, token := range active {
				if isDescendant(token, action.Target, tokens) {
					covered[jti] = true
				}
			}
		}
	case "DISABLE_CLIENT":
		if _, ok := c.Clients[action.Target]; ok {
			targetKnown = true
			for jti, token := range active {
				if token.Client == action.Target {
					covered[jti] = true
				}
			}
		}
	case "RETIRE_KEY":
		if _, ok := c.Keys[action.Target]; ok {
			targetKnown = true
			for jti, token := range active {
				if token.Key == action.Target {
					covered[jti] = true
				}
			}
		}
	case "QUARANTINE_SUBJECT":
		for _, token := range tokens {
			if token.Subject == action.Target {
				targetKnown = true
				break
			}
		}
		if targetKnown {
			for jti, token := range active {
				if token.Subject == action.Target {
					covered[jti] = true
				}
			}
		}
	case "LIMIT_AUDIENCE":
		if _, ok := c.Resources[action.Target]; ok {
			targetKnown = true
			for jti, token := range active {
				if token.Audience == action.Target {
					covered[jti] = true
				}
			}
		}
	}
	return targetKnown, sortedKeys(covered)
}

func actionReasons(c Case, action Action, tokens map[string]*Token, active map[string]*Token) ([]string, []string) {
	reasons := []string{}
	knownType := map[string]bool{
		"REVOKE_TOKEN":       true,
		"REVOKE_LINEAGE":     true,
		"DISABLE_CLIENT":     true,
		"RETIRE_KEY":         true,
		"QUARANTINE_SUBJECT": true,
		"LIMIT_AUDIENCE":     true,
	}[action.Type]
	if !knownType {
		reasons = append(reasons, "unknown_action_type")
	} else {
		targetKnown, covers := actionCovers(c, action, tokens, active)
		if !targetKnown {
			reasons = append(reasons, "unknown_target")
		} else if len(covers) == 0 {
			reasons = append(reasons, "no_active_coverage")
		}
		if action.Confidence < c.Remediation.MinConfidence {
			reasons = append(reasons, "low_confidence")
		}
		if action.Impact > c.Remediation.MaxImpact {
			reasons = append(reasons, "impact_exceeds_budget")
		}
		return reasons, covers
	}
	if action.Confidence < c.Remediation.MinConfidence {
		reasons = append(reasons, "low_confidence")
	}
	if action.Impact > c.Remediation.MaxImpact {
		reasons = append(reasons, "impact_exceeds_budget")
	}
	return reasons, []string{}
}

func conflictKey(a, b string) string {
	if a > b {
		a, b = b, a
	}
	return a + "\x00" + b
}

func lexLess(a, b []string) bool {
	for i := 0; i < len(a) && i < len(b); i++ {
		if a[i] != b[i] {
			return a[i] < b[i]
		}
	}
	return len(a) < len(b)
}

func betterPlan(a, b planChoice) bool {
	if a.Score != b.Score {
		return a.Score > b.Score
	}
	if a.Covered != b.Covered {
		return a.Covered > b.Covered
	}
	if a.Impact != b.Impact {
		return a.Impact < b.Impact
	}
	if a.Conf != b.Conf {
		return a.Conf > b.Conf
	}
	if len(a.Selected) != len(b.Selected) {
		return len(a.Selected) < len(b.Selected)
	}
	return lexLess(a.IDs, b.IDs)
}

func evaluatePlan(c Case, selected []int, candidates []actionCandidate, active map[string]*Token) planChoice {
	covered := map[string]bool{}
	coveredClients := map[string]bool{}
	coveredRoots := map[string]bool{}
	selectedIDs := map[string]bool{}
	choice := planChoice{Selected: append([]int{}, selected...)}
	for _, idx := range selected {
		action := candidates[idx].Action
		choice.Impact += action.Impact
		choice.Conf += action.Confidence
		choice.IDs = append(choice.IDs, action.ID)
		selectedIDs[action.ID] = true
		for _, jti := range candidates[idx].Covers {
			covered[jti] = true
		}
	}
	sort.Strings(choice.IDs)
	for jti := range covered {
		token := active[jti]
		choice.Score += token.Risk
		coveredClients[token.Client] = true
		coveredRoots[token.RootJTI] = true
	}
	for _, bonus := range c.Remediation.Bonuses {
		if selectedIDs[bonus.A] && selectedIDs[bonus.B] {
			choice.Score += bonus.Delta
		}
	}
	choice.Score -= c.Remediation.CoveredClientPenalty * int64(len(coveredClients))
	choice.Score -= c.Remediation.CoveredRootPenalty * int64(len(coveredRoots))
	choice.Covered = len(covered)
	return choice
}

func buildRemediation(c Case, tokens map[string]*Token, totalRisk int64) RemediationReport {
	active := activeTokenMap(c, tokens)
	rejected := []RejectedActionRow{}
	candidates := []actionCandidate{}

	for _, action := range c.Remediation.Actions {
		reasons, covers := actionReasons(c, action, tokens, active)
		if len(reasons) > 0 {
			rejected = append(rejected, RejectedActionRow{ID: action.ID, Reasons: reasons})
			continue
		}
		candidates = append(candidates, actionCandidate{Action: action, Covers: covers})
	}
	sort.Slice(rejected, func(i, j int) bool { return rejected[i].ID < rejected[j].ID })

	conflicts := map[string]bool{}
	for _, pair := range c.Remediation.Conflicts {
		conflicts[conflictKey(pair.A, pair.B)] = true
	}
	candidateIndex := map[string]int{}
	for idx, candidate := range candidates {
		candidateIndex[candidate.Action.ID] = idx
	}
	prerequisites := map[int]map[int]bool{}
	for _, edge := range c.Remediation.Prerequisites {
		childIdx, childOK := candidateIndex[edge.Child]
		parentIdx, parentOK := candidateIndex[edge.Parent]
		if !childOK || !parentOK {
			continue
		}
		if prerequisites[childIdx] == nil {
			prerequisites[childIdx] = map[int]bool{}
		}
		prerequisites[childIdx][parentIdx] = true
	}

	closure := func(selected []int) []int {
		out := map[int]bool{}
		stack := append([]int{}, selected...)
		for len(stack) > 0 {
			last := stack[len(stack)-1]
			stack = stack[:len(stack)-1]
			if out[last] {
				continue
			}
			out[last] = true
			for parent := range prerequisites[last] {
				if !out[parent] {
					stack = append(stack, parent)
				}
			}
		}
		result := make([]int, 0, len(out))
		for idx := range out {
			result = append(result, idx)
		}
		sort.Ints(result)
		return result
	}

	validSelection := func(selected []int) bool {
		if len(selected) > c.Remediation.MaxActions {
			return false
		}
		impact := int64(0)
		typeCounts := map[string]int{}
		for _, idx := range selected {
			action := candidates[idx].Action
			impact += action.Impact
			typeCounts[action.Type]++
		}
		if impact > c.Remediation.MaxImpact {
			return false
		}
		for actionType, limit := range c.Remediation.TypeLimits {
			if typeCounts[actionType] > limit {
				return false
			}
		}
		for i := 0; i < len(selected); i++ {
			for j := i + 1; j < len(selected); j++ {
				if conflicts[conflictKey(candidates[selected[i]].Action.ID, candidates[selected[j]].Action.ID)] {
					return false
				}
			}
		}
		return true
	}

	best := evaluatePlan(c, nil, candidates, active)
	seen := map[string]bool{}
	var dfs func(int, []int)
	dfs = func(pos int, selected []int) {
		keyParts := make([]string, len(selected))
		for i, idx := range selected {
			keyParts[i] = strconv.Itoa(idx)
		}
		stateKey := fmt.Sprintf("%d|%s", pos, strings.Join(keyParts, ","))
		if seen[stateKey] {
			return
		}
		seen[stateKey] = true

		if pos == len(candidates) {
			choice := evaluatePlan(c, selected, candidates, active)
			if betterPlan(choice, best) {
				best = choice
			}
			return
		}

		dfs(pos+1, selected)

		next := closure(append(append([]int{}, selected...), pos))
		if !validSelection(next) {
			return
		}
		dfs(pos+1, next)
	}
	dfs(0, nil)

	selectedRows := []SelectedActionRow{}
	for _, idx := range best.Selected {
		candidate := candidates[idx]
		selectedRows = append(selectedRows, SelectedActionRow{
			ID:         candidate.Action.ID,
			Type:       candidate.Action.Type,
			Target:     candidate.Action.Target,
			Covers:     append([]string{}, candidate.Covers...),
			Impact:     candidate.Action.Impact,
			Confidence: candidate.Action.Confidence,
		})
	}
	sort.Slice(selectedRows, func(i, j int) bool { return selectedRows[i].ID < selectedRows[j].ID })

	return RemediationReport{
		Score:        best.Score,
		ResidualRisk: totalRisk - best.Score,
		Totals: RemediationTotals{
			Actions:       len(best.Selected),
			Impact:        best.Impact,
			CoveredTokens: best.Covered,
			Confidence:    best.Conf,
		},
		Selected: selectedRows,
		Rejected: rejected,
	}
}

func audit(c Case) Report {
	stats := map[string]*clientStats{}
	clientIDs := make([]string, 0, len(c.Clients))
	for id := range c.Clients {
		stats[id] = &clientStats{}
		clientIDs = append(clientIDs, id)
	}
	sort.Strings(clientIDs)

	tokens := map[string]*Token{}
	nonces := map[string]map[string]bool{}
	seenEvents := map[string]bool{}
	rejected := []RejectedRow{}
	issued := 0

	addRejected := func(ev Event, reasons []string) {
		rejected = append(rejected, RejectedRow{Event: ev.ID, Reasons: reasons})
		if st := stats[ev.Client]; st != nil {
			st.rejected++
		}
	}

	for _, ev := range orderedEvents(c) {
		if seenEvents[ev.ID] {
			addRejected(ev, []string{"duplicate_event"})
			continue
		}
		seenEvents[ev.ID] = true

		switch ev.Op {
		case "MINT", "EXCHANGE":
			reasons := tokenReasons(c, ev, tokens, nonces)
			if len(reasons) > 0 {
				addRejected(ev, reasons)
				continue
			}
			rootJTI := ev.JTI
			depth := int64(0)
			rootIssuedAt := ev.Ts
			rootGrant := ev.Grant
			rootPKCEGap := ev.PKCE == "no"
			lineageWeakDPOP := ev.DPOP == "no"
			parentJTI := ""
			if ev.Op == "EXCHANGE" {
				parent := tokens[ev.Parent]
				rootJTI = parent.RootJTI
				depth = parent.Depth + 1
				rootIssuedAt = parent.RootIssuedAt
				rootGrant = parent.RootGrant
				rootPKCEGap = parent.RootPKCEGap
				lineageWeakDPOP = parent.LineageWeakDPOP || ev.DPOP == "no"
				parentJTI = ev.Parent
			}
			ev.Depth = depth
			ev.RootGrant = rootGrant
			ev.RootPKCEGap = rootPKCEGap
			ev.LineageWeakDPOP = lineageWeakDPOP
			token := &Token{
				JTI:             ev.JTI,
				Client:          ev.Client,
				Subject:         ev.Subject,
				Audience:        ev.Audience,
				Scopes:          append([]string{}, ev.Scopes...),
				ScopeSet:        ev.ScopeSet,
				Expires:         ev.Ts + ev.TTL,
				Key:             ev.Key,
				Risk:            tokenRisk(c, ev),
				RootJTI:         rootJTI,
				Depth:           depth,
				RootIssuedAt:    rootIssuedAt,
				RootGrant:       rootGrant,
				RootPKCEGap:     rootPKCEGap,
				LineageWeakDPOP: lineageWeakDPOP,
				ParentJTI:       parentJTI,
			}
			tokens[ev.JTI] = token
			issued++
			stats[ev.Client].issued++
			if ev.Nonce != "-" {
				nonceKey := ev.Client + "\x00" + ev.Subject
				if nonces[nonceKey] == nil {
					nonces[nonceKey] = map[string]bool{}
				}
				nonces[nonceKey][ev.Nonce] = true
			}
		case "REVOKE":
			reasons := []string{}
			if _, ok := c.Clients[ev.Client]; !ok {
				reasons = append(reasons, "unknown_client")
			}
			token, tokenOK := tokens[ev.JTI]
			if !tokenOK {
				reasons = append(reasons, "token_missing")
			} else if token.Client != ev.Client || token.Subject != ev.Subject {
				reasons = append(reasons, "subject_mismatch")
			}
			if len(reasons) > 0 {
				addRejected(ev, reasons)
				continue
			}
			token.Revoked = true
		}
	}

	activeRows := []ActiveRow{}
	revoked := 0
	totalRisk := int64(0)
	for _, token := range tokens {
		if token.Revoked {
			revoked++
		}
		if !token.Revoked && c.Now < token.Expires {
			activeRows = append(activeRows, ActiveRow{
				JTI:       token.JTI,
				Client:    token.Client,
				Subject:   token.Subject,
				Audience:  token.Audience,
				Scopes:    append([]string{}, token.Scopes...),
				ExpiresAt: token.Expires,
				Key:       token.Key,
				Root:      token.RootJTI,
				Depth:     token.Depth,
				Risk:      token.Risk,
			})
			stats[token.Client].active++
			stats[token.Client].risk += token.Risk
			totalRisk += token.Risk
		}
	}
	sort.Slice(activeRows, func(i, j int) bool {
		return activeRows[i].JTI < activeRows[j].JTI
	})

	clientRows := make([]ClientRow, 0, len(clientIDs))
	for _, id := range clientIDs {
		st := stats[id]
		clientRows = append(clientRows, ClientRow{
			Client:         id,
			Issued:         st.issued,
			Active:         st.active,
			RejectedEvents: st.rejected,
			Risk:           st.risk,
		})
	}

	return Report{
		Now: c.Now,
		Totals: Totals{
			Issued:         issued,
			RejectedEvents: len(rejected),
			Active:         len(activeRows),
			Revoked:        revoked,
			Risk:           totalRisk,
		},
		Active:      activeRows,
		Rejected:    rejected,
		Clients:     clientRows,
		Remediation: buildRemediation(c, tokens, totalRisk),
	}
}

func buildCase(now int, issuers, keys, clients, resources, events [][]string, version int, retractions []string, policy [2]int, remediation map[string]any) string {
	lines := []string{fmt.Sprintf("OIDC_EXCHANGE_AUDIT %d", version), fmt.Sprintf("NOW %d", now), fmt.Sprintf("ISSUERS %d", len(issuers))}
	for _, row := range issuers {
		lines = append(lines, "ISSUER "+strings.Join(row, " "))
	}
	lines = append(lines, fmt.Sprintf("KEYS %d", len(keys)))
	for _, row := range keys {
		lines = append(lines, "KEY "+strings.Join(row, " "))
	}
	lines = append(lines, fmt.Sprintf("CLIENTS %d", len(clients)))
	for _, row := range clients {
		lines = append(lines, "CLIENT "+strings.Join(row, " "))
	}
	lines = append(lines, fmt.Sprintf("RESOURCES %d", len(resources)))
	for _, row := range resources {
		lines = append(lines, "RESOURCE "+strings.Join(row, " "))
	}
	lines = append(lines, fmt.Sprintf("POLICY %d %d", policy[0], policy[1]))
	lines = append(lines, fmt.Sprintf("EVENTS %d", len(events)))
	for _, row := range events {
		lines = append(lines, "EVENT "+strings.Join(row, " "))
	}
	if version != 1 {
		lines = append(lines, fmt.Sprintf("RETRACTIONS %d", len(retractions)))
		for _, eventID := range retractions {
			lines = append(lines, "RETRACT "+eventID)
		}
	}
	limits := remediation["limits"].([]int)
	lines = append(lines, fmt.Sprintf("REMEDIATION %d %d %d", limits[0], limits[1], limits[2]))
	actions := remediation["actions"].([][]string)
	lines = append(lines, fmt.Sprintf("ACTIONS %d", len(actions)))
	for _, row := range actions {
		lines = append(lines, "ACTION "+strings.Join(row, " "))
	}
	conflicts := remediation["conflicts"].([][]string)
	lines = append(lines, fmt.Sprintf("ACTION_CONFLICTS %d", len(conflicts)))
	for _, row := range conflicts {
		lines = append(lines, "ACTION_CONFLICT "+strings.Join(row, " "))
	}
	prereqs := remediation["prerequisites"].([][]string)
	lines = append(lines, fmt.Sprintf("ACTION_PREREQUISITES %d", len(prereqs)))
	for _, row := range prereqs {
		lines = append(lines, "ACTION_PREREQ "+strings.Join(row, " "))
	}
	if version == 3 {
		typeLimits := [][]string{}
		if raw, ok := remediation["type_limits"]; ok {
			typeLimits = raw.([][]string)
		}
		lines = append(lines, fmt.Sprintf("ACTION_TYPE_LIMITS %d", len(typeLimits)))
		for _, row := range typeLimits {
			lines = append(lines, "ACTION_TYPE_LIMIT "+strings.Join(row, " "))
		}
		planTuning := []int{0, 0}
		if raw, ok := remediation["plan_tuning"]; ok {
			planTuning = raw.([]int)
		}
		lines = append(lines, fmt.Sprintf("PLAN_TUNING %d %d", planTuning[0], planTuning[1]))
		bonuses := [][]string{}
		if raw, ok := remediation["bonuses"]; ok {
			bonuses = raw.([][]string)
		}
		lines = append(lines, fmt.Sprintf("ACTION_BONUSES %d", len(bonuses)))
		for _, row := range bonuses {
			lines = append(lines, "ACTION_BONUS "+strings.Join(row, " "))
		}
	}
	lines = append(lines, "END")
	return strings.Join(lines, "\n") + "\n"
}

var baseIssuers = [][]string{{"corp", "30"}, {"ext", "10"}}

var baseKeys = [][]string{
	{"k-main", "corp", "RS256", "1000", "4000", "active"},
	{"k-es", "corp", "ES256", "1100", "2300", "active"},
	{"k-ret", "corp", "RS256", "900", "3000", "retired"},
	{"ext-k", "ext", "RS256", "1000", "4000", "active"},
}

var baseClients = [][]string{
	{"web", "corp", "active", "2", "700", "yes", "yes", "authorization_code,exchange", "api,admin"},
	{"svc", "corp", "active", "1", "1500", "no", "no", "client_credentials,exchange", "api"},
	{"off", "corp", "disabled", "1", "500", "no", "no", "password", "api"},
	{"extapp", "ext", "active", "1", "600", "yes", "no", "authorization_code", "partner"},
}

var baseResources = [][]string{
	{"api", "1", "read,write,profile"},
	{"admin", "2", "read,write,admin,profile"},
	{"partner", "1", "read,export"},
}

func remediationForSeed(seed int, user string) map[string]any {
	return map[string]any{
		"limits": []int{3, 7 + seed%3, 60},
		"actions": [][]string{
			{fmt.Sprintf("act%d_disable_ext", seed), "DISABLE_CLIENT", "extapp", "3", "85"},
			{fmt.Sprintf("act%d_disable_web", seed), "DISABLE_CLIENT", "web", "5", "72"},
			{fmt.Sprintf("act%d_limit_api", seed), "LIMIT_AUDIENCE", "api", "4", "75"},
			{fmt.Sprintf("act%d_limit_partner", seed), "LIMIT_AUDIENCE", "partner", "2", "88"},
			{fmt.Sprintf("act%d_lowconf_extkey", seed), "RETIRE_KEY", "ext-k", "1", "40"},
			{fmt.Sprintf("act%d_missing", seed), "REVOKE_TOKEN", fmt.Sprintf("missing%d", seed), "1", "99"},
			{fmt.Sprintf("act%d_quarantine", seed), "QUARANTINE_SUBJECT", user, "5", "93"},
			{fmt.Sprintf("act%d_retire_main", seed), "RETIRE_KEY", "k-main", "4", strconv.Itoa(65 + seed%20)},
			{fmt.Sprintf("act%d_revoke_child", seed), "REVOKE_TOKEN", fmt.Sprintf("child%d", seed), "1", "94"},
			{fmt.Sprintf("act%d_revoke_ext", seed), "REVOKE_TOKEN", fmt.Sprintf("ext%d", seed), "2", "82"},
			{fmt.Sprintf("act%d_revoke_parent", seed), "REVOKE_TOKEN", fmt.Sprintf("parent%d", seed), "2", "96"},
			{fmt.Sprintf("act%d_lineage_parent", seed), "REVOKE_LINEAGE", fmt.Sprintf("parent%d", seed), "4", "91"},
			{fmt.Sprintf("act%d_lineage_svc", seed), "REVOKE_LINEAGE", fmt.Sprintf("svcroot%d", seed), "3", "79"},
			{fmt.Sprintf("act%d_revoke_svc", seed), "REVOKE_TOKEN", fmt.Sprintf("svcroot%d", seed), "2", "83"},
			{fmt.Sprintf("act%d_too_heavy", seed), "DISABLE_CLIENT", "web", "20", "99"},
			{fmt.Sprintf("act%d_unknown_type", seed), "ROTATE_SECRET", "web", "1", "99"},
		},
		"conflicts": [][]string{
			{fmt.Sprintf("act%d_quarantine", seed), fmt.Sprintf("act%d_disable_ext", seed)},
			{fmt.Sprintf("act%d_disable_web", seed), fmt.Sprintf("act%d_limit_api", seed)},
			{fmt.Sprintf("act%d_retire_main", seed), fmt.Sprintf("act%d_revoke_parent", seed)},
			{fmt.Sprintf("act%d_lineage_parent", seed), fmt.Sprintf("act%d_retire_main", seed)},
		},
		"prerequisites": [][]string{
			{fmt.Sprintf("act%d_revoke_ext", seed), fmt.Sprintf("act%d_disable_ext", seed)},
			{fmt.Sprintf("act%d_lineage_parent", seed), fmt.Sprintf("act%d_quarantine", seed)},
			{fmt.Sprintf("act%d_retire_main", seed), fmt.Sprintf("act%d_disable_web", seed)},
		},
		"type_limits": [][]string{
			{"DISABLE_CLIENT", "1"},
			{"LIMIT_AUDIENCE", "1"},
			{"REVOKE_LINEAGE", "1"},
			{"REVOKE_TOKEN", "2"},
		},
		"plan_tuning": []int{22 + seed%4, 60 + 10*(seed%3)},
		"bonuses": [][]string{
			{fmt.Sprintf("act%d_lineage_parent", seed), fmt.Sprintf("act%d_revoke_ext", seed), strconv.Itoa(45 + 5*(seed%3))},
			{fmt.Sprintf("act%d_disable_ext", seed), fmt.Sprintf("act%d_limit_partner", seed), "30"},
			{fmt.Sprintf("act%d_retire_main", seed), fmt.Sprintf("act%d_limit_api", seed), "-70"},
			{fmt.Sprintf("act%d_revoke_child", seed), fmt.Sprintf("act%d_revoke_parent", seed), "-15"},
		},
	}
}

func generatedCase(seed int, version int, retractBad bool, revokeParent bool) string {
	base := 1200 + seed*7
	user := fmt.Sprintf("user%d", seed)
	policy := [2]int{2 + (seed % 2), 430 + 15*(seed%4)}
	events := [][]string{
		{fmt.Sprintf("s%de05", seed), strconv.Itoa(base + 15), "b", "5", "web", user, "EXCHANGE", fmt.Sprintf("child%d", seed), fmt.Sprintf("parent%d", seed), "k-es", "ES256", "admin", "read", "300", "yes", fmt.Sprintf("nx%d", seed)},
		{fmt.Sprintf("s%de01", seed), strconv.Itoa(base), "c", "3", "web", user, "MINT", fmt.Sprintf("parent%d", seed), "k-main", "RS256", "authorization_code", "api", "read,profile", "700", "yes", "yes", fmt.Sprintf("n%da", seed)},
		{fmt.Sprintf("s%de02", seed), strconv.Itoa(base + 1), "a", "2", "web", user, "MINT", fmt.Sprintf("replay%d", seed), "k-main", "RS256", "authorization_code", "api", "read", "100", "yes", "yes", fmt.Sprintf("n%da", seed)},
		{fmt.Sprintf("s%de03", seed), strconv.Itoa(base + 2), "a", "3", "off", "bad", "MINT", fmt.Sprintf("disabled%d", seed), "k-main", "RS256", "password", "api", "read", "100", "no", "no", fmt.Sprintf("n%db", seed)},
		{fmt.Sprintf("s%dbad", seed), strconv.Itoa(base + 3), "a", "4", "web", user, "MINT", fmt.Sprintf("bad%d", seed), "missing", "RS256", "authorization_code", "unknown", "delete", "900", "no", "no", fmt.Sprintf("n%dc", seed)},
		{fmt.Sprintf("s%de04", seed), strconv.Itoa(base + 10), "a", "5", "web", user, "EXCHANGE", fmt.Sprintf("escalate%d", seed), fmt.Sprintf("parent%d", seed), "k-es", "ES256", "admin", "write", "200", "yes", fmt.Sprintf("n%dd", seed)},
		{fmt.Sprintf("s%ddeep1", seed), strconv.Itoa(base + 16), "a", "5", "web", user, "EXCHANGE", fmt.Sprintf("grand%d", seed), fmt.Sprintf("child%d", seed), "k-es", "ES256", "api", "read", "180", "yes", fmt.Sprintf("ng%d", seed)},
		{fmt.Sprintf("s%ddeep2", seed), strconv.Itoa(base + 17), "a", "6", "web", user, "EXCHANGE", fmt.Sprintf("too_deep%d", seed), fmt.Sprintf("grand%d", seed), "k-es", "ES256", "api", "read", "90", "yes", fmt.Sprintf("nd%d", seed)},
		{fmt.Sprintf("s%dcap", seed), strconv.Itoa(base + 18), "a", "7", "web", user, "EXCHANGE", fmt.Sprintf("too_long%d", seed), fmt.Sprintf("child%d", seed), "k-es", "ES256", "api", "read", "420", "yes", fmt.Sprintf("nl%d", seed)},
		{fmt.Sprintf("s%de06", seed), strconv.Itoa(base + 20), "a", "6", "web", fmt.Sprintf("other%d", seed), "EXCHANGE", fmt.Sprintf("wrongsub%d", seed), fmt.Sprintf("parent%d", seed), "k-es", "ES256", "api", "read", "100", "yes", fmt.Sprintf("n%de", seed)},
		{fmt.Sprintf("s%dsvc1", seed), strconv.Itoa(base + 22), "a", "7", "svc", "daemon", "MINT", fmt.Sprintf("svcroot%d", seed), "k-main", "RS256", "client_credentials", "api", "read,write", "600", "no", "no", "-"},
		{fmt.Sprintf("s%dsvc2", seed), strconv.Itoa(base + 23), "a", "8", "svc", "daemon", "EXCHANGE", fmt.Sprintf("svcchild%d", seed), fmt.Sprintf("svcroot%d", seed), "k-main", "RS256", "api", "read", "300", "no", "-"},
		{fmt.Sprintf("s%de07", seed), strconv.Itoa(base + 25), "a", "9", "svc", "daemon", "MINT", fmt.Sprintf("svcadmin%d", seed), "k-main", "RS256", "client_credentials", "admin", "read", "300", "no", "no", "-"},
		{fmt.Sprintf("s%de08", seed), strconv.Itoa(base + 27), "a", "10", "extapp", "carol", "MINT", fmt.Sprintf("ext%d", seed), "ext-k", "RS256", "authorization_code", "partner", "read,export", "600", "yes", "no", fmt.Sprintf("pe%d", seed)},
		{fmt.Sprintf("s%de01", seed), strconv.Itoa(base + 28), "z", "11", "web", user, "MINT", fmt.Sprintf("dupe%d", seed), "k-main", "RS256", "authorization_code", "api", "read", "100", "yes", "yes", fmt.Sprintf("n%dz", seed)},
	}
	if revokeParent {
		events = append(events,
			[]string{fmt.Sprintf("s%drv", seed), strconv.Itoa(base + 30), "a", "12", "web", user, "REVOKE", fmt.Sprintf("parent%d", seed)},
			[]string{fmt.Sprintf("s%dlate", seed), strconv.Itoa(base + 31), "a", "13", "web", user, "EXCHANGE", fmt.Sprintf("late%d", seed), fmt.Sprintf("parent%d", seed), "k-es", "ES256", "api", "read", "100", "yes", fmt.Sprintf("n%dl", seed)},
			[]string{fmt.Sprintf("s%drv2", seed), strconv.Itoa(base + 32), "a", "14", "web", user, "REVOKE", fmt.Sprintf("parent%d", seed)},
		)
	}
	if seed%2 == 0 {
		events = append(events, []string{fmt.Sprintf("s%dret", seed), strconv.Itoa(base + 33), "a", "15", "svc", "daemon", "MINT", fmt.Sprintf("ret%d", seed), "k-ret", "RS256", "client_credentials", "api", "read", "300", "no", "no", "-"})
	}
	if seed%3 == 0 {
		events = append(events, []string{fmt.Sprintf("s%dparentmiss", seed), strconv.Itoa(base + 34), "a", "16", "svc", "daemon", "EXCHANGE", fmt.Sprintf("nopar%d", seed), fmt.Sprintf("none%d", seed), "k-main", "RS256", "api", "read", "50", "no", "-"})
	}
	retractions := []string{}
	if retractBad {
		retractions = append(retractions, fmt.Sprintf("s%dbad", seed))
	}
	reversed := make([][]string, 0, len(events))
	for i := len(events) - 1; i >= 0; i-- {
		reversed = append(reversed, events[i])
	}
	return buildCase(base+500, baseIssuers, baseKeys, baseClients, baseResources, reversed, version, retractions, policy, remediationForSeed(seed, user))
}

func edgeCase() string {
	issuers := [][]string{{"edge", "20"}}
	keys := [][]string{{"early", "edge", "RS256", "100", "200", "active"}, {"main", "edge", "RS256", "100", "400", "active"}}
	clients := [][]string{{"cli", "edge", "active", "1", "100", "no", "no", "authorization_code,exchange", "api"}}
	resources := [][]string{{"api", "1", "read,write"}}
	policy := [2]int{1, 140}
	events := [][]string{
		{"b1", "80", "s", "1", "cli", "ann", "MINT", "at_lower_skew", "early", "RS256", "authorization_code", "api", "read", "100", "no", "no", "n1"},
		{"b1x", "120", "s", "1", "cli", "ann", "EXCHANGE", "child_ok", "at_lower_skew", "main", "RS256", "api", "read", "60", "no", "n1x"},
		{"b1y", "121", "s", "2", "cli", "ann", "EXCHANGE", "child_too_deep", "child_ok", "main", "RS256", "api", "read", "50", "no", "n1y"},
		{"b2", "221", "s", "2", "cli", "ann", "MINT", "outside_upper_skew", "early", "RS256", "authorization_code", "api", "read", "100", "no", "no", "n2"},
		{"b3", "250", "s", "3", "cli", "ann", "MINT", "expires_exact", "main", "RS256", "authorization_code", "api", "read", "50", "no", "no", "n3"},
		{"b4", "260", "s", "4", "ghost", "ann", "REVOKE", "missing"},
		{"b5", "270", "s", "5", "cli", "bob", "REVOKE", "at_lower_skew"},
		{"b6", "280", "s", "6", "cli", "ann", "REVOKE", "at_lower_skew"},
		{"b7", "281", "s", "7", "cli", "ann", "REVOKE", "at_lower_skew"},
	}
	remediation := map[string]any{
		"limits": []int{2, 4, 50},
		"actions": [][]string{
			{"edge_disable_cli", "DISABLE_CLIENT", "cli", "2", "90"},
			{"edge_missing", "REVOKE_TOKEN", "never", "1", "90"},
			{"edge_quarantine_ann", "QUARANTINE_SUBJECT", "ann", "2", "90"},
			{"edge_lineage", "REVOKE_LINEAGE", "at_lower_skew", "3", "88"},
			{"edge_unknown_type", "LOCK_SESSION", "ann", "1", "90"},
		},
		"conflicts":     [][]string{{"edge_disable_cli", "edge_quarantine_ann"}},
		"prerequisites": [][]string{{"edge_lineage", "edge_quarantine_ann"}},
	}
	return buildCase(300, issuers, keys, clients, resources, events, 1, nil, policy, remediation)
}

func emptyCase() string {
	return buildCase(
		1000,
		[][]string{{"corp", "0"}},
		[][]string{{"k", "corp", "RS256", "0", "2000", "active"}},
		[][]string{{"c", "corp", "active", "1", "10", "no", "no", "authorization_code", "api"}},
		[][]string{{"api", "1", "read"}},
		nil,
		1,
		nil,
		[2]int{1, 50},
		map[string]any{
			"limits": []int{1, 2, 50},
			"actions": [][]string{
				{"empty_disable", "DISABLE_CLIENT", "c", "1", "90"},
				{"empty_unknown", "REVOKE_TOKEN", "none", "1", "90"},
			},
			"conflicts":     [][]string{},
			"prerequisites": [][]string{},
		},
	)
}

func lineageDependencyCase() string {
	issuers := [][]string{{"corp", "0"}}
	keys := [][]string{
		{"k1", "corp", "RS256", "0", "5000", "active"},
		{"k2", "corp", "ES256", "0", "5000", "active"},
	}
	clients := [][]string{
		{"web", "corp", "active", "2", "900", "yes", "yes", "authorization_code,exchange", "api,admin"},
		{"svc", "corp", "active", "1", "900", "no", "no", "client_credentials,exchange", "api"},
	}
	resources := [][]string{
		{"api", "1", "read,write"},
		{"admin", "2", "read,admin"},
	}
	events := [][]string{
		{"ld1", "100", "a", "1", "web", "alice", "MINT", "rootA", "k1", "RS256", "authorization_code", "api", "read,write", "700", "yes", "yes", "na"},
		{"ld2", "120", "a", "2", "web", "alice", "EXCHANGE", "childA1", "rootA", "k2", "ES256", "admin", "read", "300", "yes", "nb"},
		{"ld3", "140", "a", "3", "web", "alice", "EXCHANGE", "childA2", "childA1", "k2", "ES256", "api", "read", "250", "yes", "nc"},
		{"ld4", "200", "a", "4", "svc", "daemon", "MINT", "rootS", "k1", "RS256", "client_credentials", "api", "read,write", "800", "no", "no", "-"},
		{"ld5", "220", "a", "5", "svc", "daemon", "EXCHANGE", "childS1", "rootS", "k1", "RS256", "api", "read", "300", "no", "-"},
		{"ld6", "240", "a", "6", "svc", "daemon", "EXCHANGE", "childS2", "childS1", "k1", "RS256", "api", "read", "200", "no", "-"},
		{"ld7", "260", "a", "7", "web", "alice", "EXCHANGE", "tooDeep", "childA2", "k2", "ES256", "api", "read", "100", "yes", "nd"},
	}
	remediation := map[string]any{
		"limits": []int{3, 8, 60},
		"actions": [][]string{
			{"ld_disable_web", "DISABLE_CLIENT", "web", "4", "72"},
			{"ld_quarantine_alice", "QUARANTINE_SUBJECT", "alice", "3", "94"},
			{"ld_lineage_rootA", "REVOKE_LINEAGE", "rootA", "5", "91"},
			{"ld_limit_api", "LIMIT_AUDIENCE", "api", "3", "88"},
			{"ld_retire_k1", "RETIRE_KEY", "k1", "2", "77"},
			{"ld_lineage_rootS", "REVOKE_LINEAGE", "rootS", "3", "79"},
			{"ld_revoke_childA1", "REVOKE_TOKEN", "childA1", "1", "98"},
		},
		"conflicts": [][]string{
			{"ld_disable_web", "ld_limit_api"},
			{"ld_retire_k1", "ld_lineage_rootS"},
		},
		"prerequisites": [][]string{
			{"ld_lineage_rootA", "ld_quarantine_alice"},
			{"ld_retire_k1", "ld_disable_web"},
		},
	}
	return buildCase(600, issuers, keys, clients, resources, events, 1, nil, [2]int{2, 650}, remediation)
}

func retractionLineageCase() string {
	issuers := [][]string{{"corp", "5"}}
	keys := [][]string{{"k1", "corp", "RS256", "0", "5000", "active"}}
	clients := [][]string{{"web", "corp", "active", "2", "500", "yes", "yes", "authorization_code,exchange", "api"}}
	resources := [][]string{{"api", "1", "read,write"}}
	events := [][]string{
		{"rt1", "100", "a", "1", "web", "ann", "MINT", "root", "k1", "RS256", "authorization_code", "api", "read", "300", "yes", "yes", "n1"},
		{"rt2", "110", "a", "2", "web", "ann", "EXCHANGE", "child", "root", "k1", "RS256", "api", "read", "200", "yes", "n2"},
		{"rt3", "111", "a", "3", "web", "ann", "EXCHANGE", "ghost", "child", "k1", "RS256", "api", "read", "100", "yes", "n3"},
		{"rt3", "112", "z", "1", "web", "ann", "EXCHANGE", "dupeghost", "child", "k1", "RS256", "api", "read", "100", "yes", "n4"},
		{"rt4", "120", "a", "4", "web", "ann", "EXCHANGE", "too_long", "root", "k1", "RS256", "api", "read", "450", "yes", "n5"},
	}
	remediation := map[string]any{
		"limits": []int{2, 4, 60},
		"actions": [][]string{
			{"rt_lineage_root", "REVOKE_LINEAGE", "root", "3", "90"},
			{"rt_revoke_child", "REVOKE_TOKEN", "child", "1", "95"},
			{"rt_limit_api", "LIMIT_AUDIENCE", "api", "2", "85"},
		},
		"conflicts":     [][]string{{"rt_lineage_root", "rt_limit_api"}},
		"prerequisites": [][]string{{"rt_revoke_child", "rt_limit_api"}},
	}
	return buildCase(250, issuers, keys, clients, resources, events, 2, []string{"rt3"}, [2]int{2, 260}, remediation)
}

func v3BonusPenaltyCase() string {
	issuers := [][]string{{"corp", "0"}}
	keys := [][]string{
		{"k1", "corp", "RS256", "0", "5000", "active"},
		{"k2", "corp", "ES256", "0", "5000", "active"},
	}
	clients := [][]string{
		{"web", "corp", "active", "2", "900", "yes", "yes", "authorization_code,exchange", "api,admin"},
		{"svc", "corp", "active", "1", "1200", "no", "no", "client_credentials,exchange", "api"},
	}
	resources := [][]string{
		{"api", "1", "read,write"},
		{"admin", "2", "read,admin"},
	}
	events := [][]string{
		{"vp1", "100", "a", "1", "web", "alice", "MINT", "rootA", "k1", "RS256", "authorization_code", "api", "read,write", "700", "yes", "yes", "na"},
		{"vp2", "120", "a", "2", "web", "alice", "EXCHANGE", "childA1", "rootA", "k2", "ES256", "admin", "read", "260", "yes", "nb"},
		{"vp3", "140", "a", "3", "web", "alice", "EXCHANGE", "childA2", "childA1", "k2", "ES256", "api", "read", "220", "yes", "nc"},
		{"vp4", "160", "a", "4", "web", "bob", "MINT", "rootB", "k1", "RS256", "authorization_code", "api", "read", "680", "yes", "yes", "nd"},
		{"vp5", "180", "a", "5", "svc", "daemon", "MINT", "svcRoot", "k1", "RS256", "client_credentials", "api", "read,write", "760", "no", "no", "-"},
		{"vp6", "200", "a", "6", "svc", "daemon", "EXCHANGE", "svcChild", "svcRoot", "k1", "RS256", "api", "read", "260", "no", "-"},
	}
	remediation := map[string]any{
		"limits": []int{4, 11, 70},
		"actions": [][]string{
			{"vp_disable_web", "DISABLE_CLIENT", "web", "5", "78"},
			{"vp_quarantine_alice", "QUARANTINE_SUBJECT", "alice", "3", "93"},
			{"vp_lineage_rootA", "REVOKE_LINEAGE", "rootA", "4", "92"},
			{"vp_revoke_rootB", "REVOKE_TOKEN", "rootB", "2", "95"},
			{"vp_limit_api", "LIMIT_AUDIENCE", "api", "4", "85"},
			{"vp_retire_k1", "RETIRE_KEY", "k1", "4", "82"},
			{"vp_disable_svc", "DISABLE_CLIENT", "svc", "3", "84"},
			{"vp_lineage_svc", "REVOKE_LINEAGE", "svcRoot", "3", "88"},
			{"vp_missing", "REVOKE_TOKEN", "ghost", "1", "99"},
			{"vp_unknown", "LOCK_SESSION", "alice", "1", "99"},
		},
		"conflicts": [][]string{
			{"vp_disable_web", "vp_limit_api"},
			{"vp_retire_k1", "vp_lineage_rootA"},
		},
		"prerequisites": [][]string{
			{"vp_lineage_rootA", "vp_quarantine_alice"},
			{"vp_lineage_svc", "vp_disable_svc"},
		},
		"type_limits": [][]string{
			{"DISABLE_CLIENT", "1"},
			{"REVOKE_LINEAGE", "1"},
			{"LIMIT_AUDIENCE", "1"},
		},
		"plan_tuning": []int{35, 80},
		"bonuses": [][]string{
			{"vp_lineage_rootA", "vp_revoke_rootB", "65"},
			{"vp_disable_svc", "vp_lineage_svc", "25"},
			{"vp_limit_api", "vp_retire_k1", "-90"},
		},
	}
	return buildCase(600, issuers, keys, clients, resources, events, 3, nil, [2]int{2, 700}, remediation)
}

func v3TypeLimitClosureCase() string {
	issuers := [][]string{{"corp", "0"}}
	keys := [][]string{{"k1", "corp", "RS256", "0", "5000", "active"}}
	clients := [][]string{{"web", "corp", "active", "2", "900", "yes", "yes", "authorization_code,exchange", "api"}}
	resources := [][]string{{"api", "1", "read,write"}}
	events := [][]string{
		{"tc1", "100", "a", "1", "web", "alice", "MINT", "root1", "k1", "RS256", "authorization_code", "api", "read,write", "700", "yes", "yes", "n1"},
		{"tc2", "110", "a", "2", "web", "alice", "EXCHANGE", "child1", "root1", "k1", "RS256", "api", "read", "250", "yes", "n2"},
		{"tc3", "120", "a", "3", "web", "carol", "MINT", "root2", "k1", "RS256", "authorization_code", "api", "read,write", "680", "yes", "yes", "n3"},
		{"tc4", "130", "a", "4", "web", "carol", "EXCHANGE", "child2", "root2", "k1", "RS256", "api", "read", "240", "yes", "n4"},
	}
	remediation := map[string]any{
		"limits": []int{4, 9, 75},
		"actions": [][]string{
			{"tc_disable_web", "DISABLE_CLIENT", "web", "5", "77"},
			{"tc_quarantine_alice", "QUARANTINE_SUBJECT", "alice", "2", "92"},
			{"tc_quarantine_carol", "QUARANTINE_SUBJECT", "carol", "2", "91"},
			{"tc_lineage_root1", "REVOKE_LINEAGE", "root1", "3", "94"},
			{"tc_lineage_root2", "REVOKE_LINEAGE", "root2", "3", "93"},
			{"tc_revoke_root2", "REVOKE_TOKEN", "root2", "1", "96"},
			{"tc_limit_api", "LIMIT_AUDIENCE", "api", "3", "82"},
		},
		"conflicts": [][]string{
			{"tc_disable_web", "tc_limit_api"},
		},
		"prerequisites": [][]string{
			{"tc_lineage_root1", "tc_quarantine_alice"},
			{"tc_lineage_root2", "tc_quarantine_carol"},
		},
		"type_limits": [][]string{
			{"QUARANTINE_SUBJECT", "1"},
			{"REVOKE_LINEAGE", "1"},
		},
		"plan_tuning": []int{15, 55},
		"bonuses": [][]string{
			{"tc_quarantine_carol", "tc_revoke_root2", "24"},
			{"tc_lineage_root1", "tc_lineage_root2", "-120"},
		},
	}
	return buildCase(550, issuers, keys, clients, resources, events, 3, nil, [2]int{2, 720}, remediation)
}
