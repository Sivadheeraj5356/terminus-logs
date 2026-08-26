package main

// Agent represents a support agent.
type Agent struct {
	AgentID string
	Name    string
	Tier    string
}

// Ticket represents a support ticket.
type Ticket struct {
	TicketID        string
	Title           string
	Priority        string
	Status          string
	AssignedAgentID string
	OpenedAt        string
}

// Resolution represents a resolved ticket record.
type Resolution struct {
	ResolutionID      int64
	TicketID          string
	AgentID           string
	ResolutionMinutes int64
	SLAMet            bool
	ResolvedAt        string
}
