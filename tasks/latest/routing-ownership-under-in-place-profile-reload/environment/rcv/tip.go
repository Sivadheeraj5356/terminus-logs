package rcv

import (
	"linkenv/pub"
	"linkenv/reg"
	"linkenv/wal"
)

type Tip struct {
	Gen      uint64
	Rows     []reg.RowRec
	Sealed   bool
	FromOpen bool
}

func LoadSealedTip(root string, tx *pub.TxState) Tip {
	fr, ok := wal.RecoverSealed(root)
	if !ok {
		return Tip{}
	}
	tip := Tip{Gen: fr.Gen, Rows: fr.Rows, Sealed: fr.Sealed}
	if !fr.Sealed && tx != nil && tx.OpenGen > 0 {
		if rows, ok := tx.Planned[tx.OpenGen]; ok {
			tip.Gen = tx.OpenGen
			tip.Rows = rows
			tip.FromOpen = true
		}
	}
	return tip
}

func TagMap(rows []reg.RowRec) map[string]uint8 {
	m := map[string]uint8{}
	for _, r := range rows {
		m[r.Key] = r.Class
	}
	return m
}
