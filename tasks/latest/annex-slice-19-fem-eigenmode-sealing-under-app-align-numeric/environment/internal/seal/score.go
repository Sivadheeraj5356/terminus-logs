package seal

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func fuseLocales(dataDir string) (LocaleBundle, error) {
	clockRaw, err := os.ReadFile(filepath.Join(dataDir, "tb_state", "clock.json"))
	if err != nil {
		return LocaleBundle{}, err
	}
	var clockObj map[string]any
	if err := json.Unmarshal(clockRaw, &clockObj); err != nil {
		return LocaleBundle{}, err
	}
	epochF, err := mustNum(clockObj, "epoch")
	if err != nil {
		return LocaleBundle{}, err
	}
	epoch := uint64(epochF)

	liveDir := filepath.Join(dataDir, "bands_live")
	shadowDir := filepath.Join(dataDir, "bands_shadow")
	liveIdxRaw, err := os.ReadFile(filepath.Join(liveDir, "index.json"))
	if err != nil {
		return LocaleBundle{}, err
	}
	var liveIdx map[string]any
	if err := json.Unmarshal(liveIdxRaw, &liveIdx); err != nil {
		return LocaleBundle{}, err
	}
	requireF, err := mustNum(liveIdx, "require_epoch")
	if err != nil {
		return LocaleBundle{}, err
	}
	requireEpoch := uint64(requireF)

	peelDir := shadowDir
	peelSource := "shadow"
	if epoch >= requireEpoch {
		peelDir = liveDir
		peelSource = "live"
	}

	refs, err := loadFloatMap(filepath.Join(dataDir, "num_auth", "ref_weights.json"))
	if err != nil {
		return LocaleBundle{}, err
	}

	bundle := LocaleBundle{
		Locales:    map[string]LocalePick{},
		Mismatched: []string{},
		PeelSource: peelSource,
		Epoch:      epoch,
	}
	entries, err := os.ReadDir(peelDir)
	if err != nil {
		return LocaleBundle{}, err
	}
	for _, ent := range entries {
		if ent.IsDir() {
			continue
		}
		name := ent.Name()
		if name == "index.json" || !strings.HasPrefix(name, "L") || !strings.HasSuffix(name, ".json") {
			continue
		}
		raw, err := os.ReadFile(filepath.Join(peelDir, name))
		if err != nil {
			return LocaleBundle{}, err
		}
		var slab map[string]any
		if err := json.Unmarshal(raw, &slab); err != nil {
			return LocaleBundle{}, err
		}
		locale, err := mustStr(slab, "locale_id")
		if err != nil {
			return LocaleBundle{}, err
		}
		sw, err := mustNum(slab, "weight")
		if err != nil {
			return LocaleBundle{}, err
		}
		sg, err := mustNum(slab, "generation")
		if err != nil {
			return LocaleBundle{}, err
		}
		bundle.Locales[locale] = LocalePick{
			Weight:     sw,
			Generation: uint64(sg),
			Source:     peelSource,
		}
		if v, ok := refs[locale]; ok && math.Abs(v-sw) > 1e-12 {
			bundle.Mismatched = append(bundle.Mismatched, locale)
		} else if !ok {
			bundle.Mismatched = append(bundle.Mismatched, locale)
		}
	}
	for locale := range refs {
		if _, ok := bundle.Locales[locale]; !ok {
			bundle.Mismatched = append(bundle.Mismatched, locale)
		}
	}
	sort.Strings(bundle.Mismatched)
	// unique
	uniq := []string{}
	seen := map[string]bool{}
	for _, m := range bundle.Mismatched {
		if !seen[m] {
			uniq = append(uniq, m)
			seen[m] = true
		}
	}
	bundle.Mismatched = uniq
	bundle.Agreement = len(bundle.Mismatched) == 0
	return bundle, nil
}

func loadBounds(path string) (map[string]FamilyBound, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	out := map[string]FamilyBound{}
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func loadCells(fixturesDir string) ([]ModeCell, error) {
	entries, err := os.ReadDir(fixturesDir)
	if err != nil {
		return nil, err
	}
	var cells []ModeCell
	names := []string{}
	for _, ent := range entries {
		if strings.HasSuffix(ent.Name(), ".modes.json") {
			names = append(names, ent.Name())
		}
	}
	sort.Strings(names)
	for _, name := range names {
		raw, err := os.ReadFile(filepath.Join(fixturesDir, name))
		if err != nil {
			return nil, err
		}
		var rows []map[string]any
		if err := json.Unmarshal(raw, &rows); err != nil {
			return nil, err
		}
		for _, row := range rows {
			c := ModeCell{}
			c.PanelID, _ = mustStr(row, "panel_id")
			c.Family, _ = mustStr(row, "family")
			c.Mode, _ = mustStr(row, "mode")
			c.Locale, _ = mustStr(row, "locale")
			c.OmegaObs, _ = mustNum(row, "omega_obs")
			c.OmegaRef, _ = mustNum(row, "omega_ref")
			c.Excit, _ = mustNum(row, "excit")
			cells = append(cells, c)
		}
	}
	return cells, nil
}

func scoreArm(cells []ModeCell, stiff, damp, cpl, weights map[string]float64, bounds map[string]FamilyBound) ScoreArm {
	arm := ScoreArm{Panels: map[string]PanelScore{}}
	panelRes := map[string][]float64{}
	panelFam := map[string]string{}
	for _, c := range cells {
		r := residual(c, stiff, damp, cpl, weights)
		panelRes[c.PanelID] = append(panelRes[c.PanelID], r)
		panelFam[c.PanelID] = c.Family
	}
	for pid, rs := range panelRes {
		fam := panelFam[pid]
		b := bounds[fam]
		viol := 0
		maxAbs := 0.0
		for _, r := range rs {
			if r < b.Lo || r > b.Hi {
				viol++
			}
			if math.Abs(r) > maxAbs {
				maxAbs = math.Abs(r)
			}
		}
		arm.Panels[pid] = PanelScore{
			BoundViolations: viol,
			Tightness:        maxAbs,
			MaxTightness:     b.MaxTightness,
			Family:           fam,
		}
		arm.TotalViolations += viol
		if maxAbs > arm.MaxTightness {
			arm.MaxTightness = maxAbs
		}
	}
	arm.Digest = digestOf(cells, stiff, damp, cpl, weights)
	return arm
}
