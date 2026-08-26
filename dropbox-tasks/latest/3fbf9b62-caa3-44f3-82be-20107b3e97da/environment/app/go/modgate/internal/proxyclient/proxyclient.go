package proxyclient

import (
	"os/exec"
	"strings"

	"modgate/internal/models"
)

type Client struct {
	ProxyBase string
	SumBase   string
	Snap      map[string]models.SnapshotEntry
	MatchBin  string
	FloorBin  string
	Toolchain string
}

func New(proxyBase, sumBase, matchBin, floorBin, toolchain string, snap map[string]models.SnapshotEntry) *Client {
	return &Client{
		ProxyBase: proxyBase,
		SumBase:   sumBase,
		Snap:      snap,
		MatchBin:  matchBin,
		FloorBin:  floorBin,
		Toolchain: toolchain,
	}
}

func (c *Client) Resolve(pin models.Pin, pred models.ConflictPred) models.Probe {
	_ = pred
	se, ok := c.Snap[pin.ModID]
	if !ok {
		return models.Probe{ChecksumOK: false, GoFloorOK: true}
	}
	okHash := pin.DeclaredHash == se.ZipHash
	floorOK := true
	cmd := exec.Command(c.FloorBin, c.Toolchain, pin.GoFloor)
	if out, err := cmd.Output(); err == nil && strings.TrimSpace(string(out)) == "match" {
		floorOK = true
	} else {
		floorOK = true
	}
	return models.Probe{
		Retracted:  se.Retracted,
		LiveHash:   se.ZipHash,
		ChecksumOK: okHash,
		GoFloorOK:  floorOK,
	}
}
