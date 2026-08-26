package pub

import "linkenv/reg"

func SealTx(tx *TxState, gen uint64) (CommittedView, error) {
	return seal_w(tx, gen)
}

func seal_w(tx *TxState, gen uint64) (CommittedView, error) {
	rows := tx.Planned[gen]
	if rows == nil {
		rows = tx.Committed[gen]
	}
	out := make([]reg.RowRec, len(rows))
	copy(out, rows)
	return CommittedView{Gen: gen, Rows: out}, nil
}

func CommitPlanned(tx *TxState, gen uint64) {
	if rows, ok := tx.Planned[gen]; ok {
		cp := make([]reg.RowRec, len(rows))
		copy(cp, rows)
		tx.Committed[gen] = cp
		delete(tx.Planned, gen)
	}
}
