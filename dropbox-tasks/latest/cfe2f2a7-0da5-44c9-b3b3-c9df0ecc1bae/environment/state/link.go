package state

type Link struct {
	Open          bool  `json:"open"`
	Quarantined   bool  `json:"quarantined"`
	HopCount      int   `json:"hop_count"`
	SumMs         int   `json:"sum_ms"`
	MaxMs         int   `json:"max_ms"`
	AlarmBreaches int   `json:"alarm_breaches"`
	SLAMs         int   `json:"sla_ms"`
	Buckets       []int `json:"buckets"`
	LastEpoch     int   `json:"last_epoch"`
	LastSeq       int   `json:"last_seq"`
	Referenced    bool  `json:"-"`
}

func NewLink() *Link {
	return &Link{Buckets: []int{0, 0, 0, 0, 0, 0}}
}
