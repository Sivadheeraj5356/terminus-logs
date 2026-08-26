package pub

import "linkenv/reg"

type TxState struct {
	Planned   map[uint64][]reg.RowRec `json:"planned"`
	Committed map[uint64][]reg.RowRec `json:"committed"`
	OpenGen   uint64                  `json:"open_gen"`
}

func NewTx() *TxState {
	return &TxState{
		Planned:   map[uint64][]reg.RowRec{},
		Committed: map[uint64][]reg.RowRec{},
	}
}

type CommittedView struct {
	Gen  uint64
	Rows []reg.RowRec
}
