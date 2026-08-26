package p7_chain

import (
	"os"
	"path/filepath"

	"balance_lab/p8_seal"
	"balance_lab/p9_types"
	"balance_lab/p7_load"
)

func digestParts(envRoot string, scen p9_types.Scenario) ([]string, error) {
	chronoBody, err := os.ReadFile(filepath.Join(envRoot, scen.Chronology))
	if err != nil {
		return nil, err
	}
	matchBody, err := os.ReadFile(filepath.Join(envRoot, scen.Matches))
	if err != nil {
		return nil, err
	}
	noteBody, err := os.ReadFile(filepath.Join(envRoot, scen.Notes))
	if err != nil {
		return nil, err
	}
	polBody, err := os.ReadFile(filepath.Join(envRoot, "policy", "balance_policy.json"))
	if err != nil {
		return nil, err
	}
	return []string{
		scen.Chronology + ":" + string(chronoBody),
		scen.Matches + ":" + string(matchBody),
		scen.Notes + ":" + string(notesBody(noteBody)),
		"policy/balance_policy.json:" + string(polBody),
	}, nil
}

func notesBody(b []byte) []byte {
	return b
}

func BuildArchive(envRoot string, scen p9_types.Scenario) (p9_types.Archive, error) {
	chronoPath := filepath.Join(envRoot, scen.Chronology)
	rows, err := p7_load.ReadChronology(chronoPath)
	if err != nil {
		return p9_types.Archive{}, err
	}
	matches, err := p7_load.ReadMatches(filepath.Join(envRoot, scen.Matches))
	if err != nil {
		return p9_types.Archive{}, err
	}
	notes, err := p7_load.ReadNotes(filepath.Join(envRoot, scen.Notes))
	if err != nil {
		return p9_types.Archive{}, err
	}
	pol, err := p7_load.ReadPolicy(filepath.Join(envRoot, "policy", "balance_policy.json"))
	if err != nil {
		return p9_types.Archive{}, err
	}
	eras := BuildEras(rows, matches, scen.Roster, pol.EraGapSeq, pol.WilsonZ)
	var last p9_types.EraSpan
	if len(eras) > 0 {
		last = p9_types.EraSpan{
			ID:         eras[len(eras)-1].ID,
			StartPatch: eras[len(eras)-1].StartPatch,
			EndPatch:   eras[len(eras)-1].EndPatch,
		}
	}
	parts, err := digestParts(envRoot, scen)
	if err != nil {
		return p9_types.Archive{}, err
	}
	return p9_types.Archive{
		SchemaVersion:   2,
		Scenario:        scen.Name,
		Eras:            eras,
		TurningPoints:   BuildTurningPoints(rows, matches, scen.Roster, pol.JSTurnThreshold),
		Recommendations: BuildRecommendations(last, rows, matches, notes, scen.Roster, pol.WilsonZ),
		ArchiveDigest:   p8_seal.ArchiveDigest(parts),
	}, nil
}
