package reg

type RowRec struct {
	Key    string `json:"key"`
	Prefix string `json:"prefix"`
	Via    string `json:"via"`
	Class  uint8  `json:"class"`
}

const (
	ClassDyn    uint8 = 1
	ClassInject uint8 = 2
	ClassCatch  uint8 = 3
)
