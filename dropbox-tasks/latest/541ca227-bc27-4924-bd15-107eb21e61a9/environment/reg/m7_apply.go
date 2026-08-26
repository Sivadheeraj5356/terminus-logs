package reg

import "sort"

func ReconcileApply(cur []RowRec, want []RowRec, tags map[string]uint8) ([]RowRec, error) {
	return reconcile_u(cur, want, tags)
}

func reconcile_u(cur []RowRec, want []RowRec, tags map[string]uint8) ([]RowRec, error) {
	kept := make([]RowRec, 0, len(cur))
	for _, r := range cur {
		cls := tags[r.Key]
		if cls == 0 {
			cls = r.Class
		}
		if cls == ClassCatch {
			kept = append(kept, r)
		}
	}
	wantByKey := map[string]RowRec{}
	for _, w := range want {
		wantByKey[w.Key] = w
	}
	for _, w := range want {
		kept = append(kept, w)
	}
	sort.Slice(kept, func(i, j int) bool {
		if kept[i].Prefix != kept[j].Prefix {
			return kept[i].Prefix < kept[j].Prefix
		}
		return kept[i].Via < kept[j].Via
	})
	_ = wantByKey
	return dedupeKeys(kept), nil
}

func dedupeKeys(rows []RowRec) []RowRec {
	seen := map[string]struct{}{}
	out := make([]RowRec, 0, len(rows))
	for _, r := range rows {
		if _, ok := seen[r.Key]; ok {
			continue
		}
		seen[r.Key] = struct{}{}
		out = append(out, r)
	}
	return out
}
