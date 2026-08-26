package main

// LegacyLedgerRoot is an alternate root export layout.
type LegacyLedgerRoot struct {
	Period   string `json:"period"`
	Currency string `json:"currency"`
}

// LegacyLineItem is an alternate line item layout.
type LegacyLineItem struct {
	Service            string `json:"service"`
	Units              int64  `json:"total_units"`
	CommitmentDiscount int64  `json:"commitment_discount_microcents"`
}
