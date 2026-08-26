package store

type Source struct {
	GroupNum    int
	GroupDen    int
	FillNum     int
	FillDen     int
	LogicalPath string
	FieldPath   string
}

type Event struct {
	Path    string
	PeerTag string
	Offset  int
	Span    int
	Tick    int
	HoldUS  int
}

type Series struct {
	Num int
	Den int
}
