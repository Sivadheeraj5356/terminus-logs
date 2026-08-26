package proxyclient

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os/exec"
	"strings"
	"time"

	"modgate/internal/models"
	"modgate/internal/sumscan"
)

type Client struct {
	ProxyBase string
	SumBase   string
	Snap      map[string]models.SnapshotEntry
	MatchBin  string
	FloorBin  string
	Toolchain string
	HTTP      *http.Client
}

func New(proxyBase, sumBase, matchBin, floorBin, toolchain string, snap map[string]models.SnapshotEntry) *Client {
	return &Client{
		ProxyBase: strings.TrimRight(proxyBase, "/") + "/",
		SumBase:   strings.TrimRight(sumBase, "/") + "/",
		Snap:      snap,
		MatchBin:  matchBin,
		FloorBin:  floorBin,
		Toolchain: toolchain,
		HTTP:      &http.Client{Timeout: 45 * time.Second},
	}
}

func (c *Client) Resolve(pin models.Pin, pred models.ConflictPred) models.Probe {
	se := c.Snap[pin.ModID]
	retracted := se.Retracted
	liveHash := se.ZipHash
	if pred.RefreshRetract {
		retracted = c.liveRetracted(pin.ModulePath, pin.Version)
	}
	if pred.RefreshSum {
		liveHash = c.liveZipHash(pin.ModulePath, pin.Version)
	}
	okHash := liveHash != "" && pin.DeclaredHash == liveHash
	floorOK := c.floorMatch(pin.GoFloor)
	return models.Probe{
		Retracted:  retracted,
		LiveHash:   liveHash,
		ChecksumOK: okHash,
		GoFloorOK:  floorOK,
	}
}

func (c *Client) floorMatch(floor string) bool {
	cmd := exec.Command(c.FloorBin, c.Toolchain, floor)
	out, err := cmd.Output()
	if err != nil {
		return false
	}
	return strings.TrimSpace(string(out)) == "match"
}

func (c *Client) liveRetracted(modulePath, version string) bool {
	latest, err := c.fetchLatest(modulePath)
	if err != nil || latest == "" {
		return false
	}
	modText, err := c.fetchMod(modulePath, latest)
	if err != nil {
		return false
	}
	for _, spec := range parseRetractSpecs(modText) {
		if c.retractMatch(version, spec) {
			return true
		}
	}
	return false
}

func (c *Client) retractMatch(version, spec string) bool {
	cmd := exec.Command(c.MatchBin, version, spec)
	out, err := cmd.Output()
	if err != nil {
		return false
	}
	return strings.TrimSpace(string(out)) == "match"
}

func (c *Client) fetchLatest(modulePath string) (string, error) {
	u := c.ProxyBase + encodeModule(modulePath) + "/@latest"
	body, err := c.get(u)
	if err != nil {
		return "", err
	}
	var payload struct {
		Version string `json:"Version"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return "", err
	}
	return payload.Version, nil
}

func (c *Client) fetchMod(modulePath, version string) (string, error) {
	u := c.ProxyBase + encodeModule(modulePath) + "/@v/" + version + ".mod"
	body, err := c.get(u)
	if err != nil {
		return "", err
	}
	return string(body), nil
}

func (c *Client) liveZipHash(modulePath, version string) string {
	u := c.SumBase + "lookup/" + encodeModule(modulePath) + "@" + version
	body, err := c.get(u)
	if err != nil {
		return ""
	}
	return sumscan.ZipHash(string(body), modulePath, version)
}

func (c *Client) get(u string) ([]byte, error) {
	req, err := http.NewRequest(http.MethodGet, u, nil)
	if err != nil {
		return nil, err
	}
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("status %d", resp.StatusCode)
	}
	return io.ReadAll(resp.Body)
}

func encodeModule(modulePath string) string {
	var b strings.Builder
	for _, r := range modulePath {
		if r >= 'A' && r <= 'Z' {
			b.WriteByte('!')
			b.WriteRune(r - 'A' + 'a')
		} else {
			b.WriteRune(r)
		}
	}
	return b.String()
}

func parseRetractSpecs(modText string) []string {
	var specs []string
	lines := strings.Split(modText, "\n")
	inBlock := false
	for _, raw := range lines {
		line := strings.TrimSpace(raw)
		if idx := strings.Index(line, "//"); idx >= 0 {
			line = strings.TrimSpace(line[:idx])
		}
		if line == "" {
			continue
		}
		if strings.HasPrefix(line, "retract") {
			rest := strings.TrimSpace(strings.TrimPrefix(line, "retract"))
			if rest == "(" || rest == "" {
				inBlock = true
				continue
			}
			if strings.HasPrefix(rest, "(") && strings.HasSuffix(rest, ")") {
				inner := strings.TrimSpace(rest[1 : len(rest)-1])
				if inner != "" {
					specs = append(specs, inner)
				}
				continue
			}
			specs = append(specs, rest)
			continue
		}
		if inBlock {
			if line == ")" {
				inBlock = false
				continue
			}
			specs = append(specs, line)
		}
	}
	return specs
}
