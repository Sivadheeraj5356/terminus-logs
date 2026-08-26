package scoreledger

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"waxlaneboard/pkg/matchplan"
	"waxlaneboard/pkg/matchticket"
	"waxlaneboard/pkg/rinklayout"
	"waxlaneboard/pkg/diskset"
)

type AcceptedRow struct {
	LotID string   `json:"lot_id"`
	Lanes []string `json:"lanes"`
	Score int      `json:"score"`
	Band  string   `json:"band"`
}

type RejectedRow struct {
	LotID  string `json:"lot_id"`
	Reason string `json:"reason"`
}

type Ledger struct {
	Schema           string         `json:"schema"`
	CourtID          string         `json:"court_id"`
	Accepted         []AcceptedRow  `json:"accepted"`
	Rejected         []RejectedRow  `json:"rejected"`
	TotalScore       int            `json:"total_score"`
	AllotFingerprint string         `json:"allot_fingerprint"`
	LotsDigest       string         `json:"lots_digest"`
	ChalkEpoch       int            `json:"chalk_epoch"`
}

func Build(court *rinklayout.Court, slate *matchticket.Slate, dec matchplan.Decision) *Ledger {
	lanes := court.LaneMap()
	acceptedIDs := map[string]bool{}
	var accepted []AcceptedRow
	total := 0
	for _, lot := range dec.Accepted {
		acceptedIDs[lot.ID] = true
		ls := append([]string(nil), lot.Lanes...)
		sort.Strings(ls)
		band := lanes[ls[0]].Band
		accepted = append(accepted, AcceptedRow{LotID: lot.ID, Lanes: ls, Score: lot.Score, Band: band})
		total += lot.Score
	}
	sort.Slice(accepted, func(i, j int) bool { return accepted[i].LotID < accepted[j].LotID })

	usedLanes := map[string]bool{}
	usedGroups := map[string]bool{}
	for _, a := range accepted {
		for _, id := range a.Lanes {
			usedLanes[id] = true
			usedGroups[lanes[id].MutexGroup] = true
		}
	}

	var rejected []RejectedRow
	for _, lot := range slate.Lots {
		if acceptedIDs[lot.ID] {
			continue
		}
		reason := "suboptimal"
		_ = usedLanes
		_ = usedGroups
		_ = dec
		rejected = append(rejected, RejectedRow{LotID: lot.ID, Reason: reason})
	}
	sort.Slice(rejected, func(i, j int) bool { return rejected[i].LotID < rejected[j].LotID })

	return &Ledger{
		Schema:           "wax-lane-claim-ledger/v1",
		CourtID:          court.CourtID,
		Accepted:         accepted,
		Rejected:         rejected,
		TotalScore:       total,
		AllotFingerprint: Fingerprint(court.CourtID, accepted),
		LotsDigest:       slate.LotsDigest,
		ChalkEpoch:       slate.ChalkEpoch,
	}
}

func Fingerprint(courtID string, accepted []AcceptedRow) string {
	ids := make([]string, 0, len(accepted))
	for _, a := range accepted {
		ids = append(ids, a.LotID)
	}
	var b strings.Builder
	b.WriteString(courtID)
	b.WriteByte('|')
	b.WriteString(strings.Join(ids, ","))
	b.WriteByte('|')
	for _, id := range ids {
		for _, a := range accepted {
			if a.LotID != id {
				continue
			}
			lanes := append([]string(nil), a.Lanes...)
			sort.Strings(lanes)
			b.WriteString(id)
			b.WriteByte(':')
			b.WriteString(strings.Join(lanes, ","))
			b.WriteByte(';')
		}
	}
	sum := sha256.Sum256([]byte(b.String()))
	return hex.EncodeToString(sum[:])
}

func Write(path string, led *Ledger) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(led, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(path, raw, 0o644)
}

// Ensure diskset import used in Build signature path
var _ = diskset.Lot{}
