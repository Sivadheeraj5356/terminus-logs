package stamp

import (
	"sort"

	"ra.local/field/internal/domain"
)

func Order(doc *domain.Attestation) {
	sort.Slice(doc.Sources, func(i, j int) bool { return doc.Sources[i].Path < doc.Sources[j].Path })
	sort.Slice(doc.Observations, func(i, j int) bool { return doc.Observations[i].ID < doc.Observations[j].ID })
	sort.Slice(doc.Runs, func(i, j int) bool { return doc.Runs[i].Run < doc.Runs[j].Run })
	sort.Strings(doc.Model.TrainingRuns)
	sort.Slice(doc.Model.Centers, func(i, j int) bool {
		return doc.Model.Centers[i].Peptide < doc.Model.Centers[j].Peptide
	})
	sort.Slice(doc.Replays, func(i, j int) bool {
		return doc.Replays[i].HoldoutRun < doc.Replays[j].HoldoutRun
	})
	for index := range doc.Replays {
		sort.Strings(doc.Replays[index].TrainingRuns)
		sort.Strings(doc.Replays[index].Model.TrainingRuns)
		sort.Slice(doc.Replays[index].Model.Centers, func(i, j int) bool {
			return doc.Replays[index].Model.Centers[i].Peptide <
				doc.Replays[index].Model.Centers[j].Peptide
		})
		sort.Slice(doc.Replays[index].Residuals, func(i, j int) bool {
			return doc.Replays[index].Residuals[i].ObservationID <
				doc.Replays[index].Residuals[j].ObservationID
		})
	}
	sort.Slice(doc.Lineage.SelectedViews, func(i, j int) bool {
		return doc.Lineage.SelectedViews[i].HoldoutRun <
			doc.Lineage.SelectedViews[j].HoldoutRun
	})
	for index := range doc.Lineage.SelectedViews {
		sort.Strings(doc.Lineage.SelectedViews[index].TrainingRuns)
		sort.Strings(doc.Lineage.SelectedViews[index].ObservationIDs)
	}
	sort.Slice(doc.Lineage.CacheEntries, func(i, j int) bool {
		left, right := doc.Lineage.CacheEntries[i], doc.Lineage.CacheEntries[j]
		if left.Scope != right.Scope {
			return left.Scope < right.Scope
		}
		return left.Peptide < right.Peptide
	})
}
