package main

const boardSize = 5

type Move struct {
	Color string
	Coord string
}

type Game struct {
	Props map[string]string
	Moves []Move
	Raw   string
	Path  string
}

type RoundRow struct {
	GameID      string
	Round       int
	Board       int
	Black       string
	White       string
	Record      string
	Result      string
	Reason      string
	BlackPoints int
	WhitePoints int
}

type Card struct {
	GameID        string
	Round         int
	Board         int
	Black         string
	White         string
	Result        string
	Reason        string
	OverturnedPly int
	ForfeitWinner string
}

type JournalEntry struct {
	GameID string
	Seq    int
	Active bool
	Event  string
	Note   string
}

type CameraRow struct {
	Ply    int
	Color  string
	Coord  string
	Status string
}

type ReplayResult struct {
	Result        string
	BlackScore    int
	WhiteScore    int
	LegalPlyCount int
	Reason        string
	BlackPoints   int
	WhitePoints   int
}

type AdjOut struct {
	GameID        string `json:"game_id"`
	Round         int    `json:"round"`
	Board         int    `json:"board"`
	Black         string `json:"black"`
	White         string `json:"white"`
	Result        string `json:"result"`
	Reason        string `json:"reason"`
	BlackPoints   int    `json:"black_points"`
	WhitePoints   int    `json:"white_points"`
	BlackScore    int    `json:"black_score"`
	WhiteScore    int    `json:"white_score"`
	LegalPlyCount int    `json:"legal_ply_count"`
	RecordSHA256  string `json:"record_sha256"`
}

type Standing struct {
	Player      string
	Wins        int
	Losses      int
	SOS         int
	SODOS       int
	StoneMargin int
}

type RepairEntry struct {
	GameID        string `json:"game_id"`
	JournalSeq    int    `json:"journal_seq"`
	JournalEvent  string `json:"journal_event"`
	CameraSHA256  string `json:"camera_sha256"`
	RecordSHA256  string `json:"record_sha256"`
	Result        string `json:"result"`
	Reason        string `json:"reason"`
	LegalPlyCount int    `json:"legal_ply_count"`
}

type Manifest struct {
	Ruleset           string   `json:"ruleset"`
	BoardSize         int      `json:"board_size"`
	RecordCount       int      `json:"record_count"`
	SourceRoundsSHA   string   `json:"source_rounds_sha256"`
	RepairStateSHA256 string   `json:"repair_state_sha256,omitempty"`
	Records           []AdjOut `json:"records"`
}
