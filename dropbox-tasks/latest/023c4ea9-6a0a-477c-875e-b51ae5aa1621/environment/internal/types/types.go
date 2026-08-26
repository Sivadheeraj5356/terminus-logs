package types

type UserRow struct {
    ID string `json:"id"`
}

type MembershipRow struct {
    From   string `json:"from"`
    To     string `json:"to"`
    Active bool   `json:"active"`
}

type AssumeRow struct {
    From string `json:"from"`
    To   string `json:"to"`
}

type ConstraintRow struct {
    Order    int    `json:"order"`
    SrcLevel int    `json:"src_level"`
    DstLevel int    `json:"dst_level"`
    Action   string `json:"action"`
}

type UsageRow struct {
    From string `json:"from"`
    To   string `json:"to"`
    Hits int    `json:"hits"`
}

type IdentityRow struct {
    ID    string `json:"id"`
    Entry bool   `json:"entry"`
    Crown bool   `json:"crown"`
    Level int    `json:"level"`
}

type BindingRow struct {
    Subject string `json:"subject"`
    Role    string `json:"role"`
}

type AggregateRow struct {
    Role   string `json:"role"`
    Parent string `json:"parent"`
}

type FederationRow struct {
    From string `json:"from"`
    To   string `json:"to"`
}

type EdgeRow struct {
    From    string `json:"from"`
    To      string `json:"to"`
    Channel string `json:"channel"`
    Weight  int    `json:"weight"`
}

type ChainRow struct {
    Entry    string   `json:"entry"`
    Target   string   `json:"target"`
    HopCount int      `json:"hop_count"`
    Severity string   `json:"severity"`
    Path     []string `json:"path"`
}

type EscalationReport struct {
    Profile          string     `json:"profile"`
    IdentityCount    int        `json:"identity_count"`
    Edges            []EdgeRow  `json:"edges"`
    Chains           []ChainRow `json:"chains"`
    ReportDigestHex string     `json:"report_digest_hex"`
}
