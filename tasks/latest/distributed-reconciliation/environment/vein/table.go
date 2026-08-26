package vein

type Row struct {
	PartitionID int    `json:"partition_id"`
	WriterJob   string `json:"writer_job"`
	PublishTick int    `json:"publish_tick"`
	VisibleTick int    `json:"visible_tick"`
}

type Table struct {
	rows       []Row
	strictDeps bool
}

func NewTable(count int, strictDeps bool) *Table {
	rows := make([]Row, count)
	for i := range rows {
		rows[i] = Row{PartitionID: i, PublishTick: -1, VisibleTick: -1}
	}
	return &Table{rows: rows, strictDeps: strictDeps}
}

func (t *Table) StrictDeps() bool {
	return t.strictDeps
}

func (t *Table) Ledger() []Row {
	out := make([]Row, len(t.rows))
	copy(out, t.rows)
	return out
}

func (t *Table) Restore(rows []Row) {
	if len(rows) != len(t.rows) {
		return
	}
	copy(t.rows, rows)
}
