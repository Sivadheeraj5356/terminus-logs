package model

type Leg struct {
	LegSeq       int    `json:"leg_seq"`
	FlightID     string `json:"flight_id"`
	Carrier      string `json:"carrier"`
	Origin       string `json:"origin"`
	Destination  string `json:"destination"`
	DepartureUTC string `json:"departure_utc"`
	ArrivalUTC   string `json:"arrival_utc"`
	FareClass    string `json:"fare_class"`
}

type Passenger struct {
	PassengerID  string `json:"passenger_id"`
	Name         string `json:"name"`
	LoyaltyTier  string `json:"loyalty_tier"`
	FareClass    string `json:"fare_class"`
	Itinerary    []Leg  `json:"itinerary"`
}

type ReplacementOption struct {
	FlightID  string `json:"flight_id"`
	Carrier   string `json:"carrier"`
	FareClass string `json:"fare_class"`
}

type CancellationEvent struct {
	EventID         string              `json:"event_id"`
	FlightID        string              `json:"flight_id"`
	Revision        int                 `json:"revision"`
	RecordedUTC     string              `json:"recorded_utc"`
	ReplacementPool []ReplacementOption `json:"replacement_pool"`
}

type FlightInventory struct {
	FlightID     string         `json:"flight_id"`
	Carrier      string         `json:"carrier"`
	Origin       string         `json:"origin"`
	Destination  string         `json:"destination"`
	DepartureUTC string         `json:"departure_utc"`
	ArrivalUTC   string         `json:"arrival_utc"`
	Inventory    map[string]int `json:"inventory"`
}

type AllianceCarrier struct {
	Partners []string `json:"partners"`
}

type AllianceDoc struct {
	Carriers map[string]AllianceCarrier `json:"carriers"`
}

type PriorityWeight struct {
	Loyalty    map[string]int `json:"loyalty"`
	FareClass  map[string]int `json:"fare_class"`
}

type Policy struct {
	ConnectionProtectionMinutes int            `json:"connection_protection_minutes"`
	PriorityWeight              PriorityWeight `json:"priority_weight"`
	FareClassRank               map[string]int `json:"fare_class_rank"`
	UpgradeOnCancel             bool           `json:"upgrade_on_cancel"`
	MaxFareUpgradeSteps         int            `json:"max_fare_upgrade_steps"`
	PriorityPickMode            string         `json:"priority_pick_mode"`
}

type RebookedLeg struct {
	LegSeq          int    `json:"leg_seq"`
	OriginalFlight  string `json:"original_flight"`
	ReplacementFlight string `json:"replacement_flight"`
	Carrier         string `json:"carrier"`
	FareClass       string `json:"fare_class"`
	DepartureUTC    string `json:"departure_utc"`
	ArrivalUTC      string `json:"arrival_utc"`
}

type PassengerRecord struct {
	PassengerID   string        `json:"passenger_id"`
	Status        string        `json:"status"`
	PriorityScore int           `json:"priority_score"`
	RebookedLegs  []RebookedLeg `json:"rebooked_legs"`
}

type RebookingSnapshot struct {
	SnapshotVersion            int                       `json:"snapshot_version"`
	SnapshotFingerprint        string                    `json:"snapshot_fingerprint"`
	DisruptionDate             string                    `json:"disruption_date"`
	CollapsedCancellationCount int                       `json:"collapsed_cancellation_count"`
	AutoRebookedPassengerIDs   []string                  `json:"auto_rebooked_passenger_ids"`
	PassengerRecords           []PassengerRecord         `json:"passenger_records"`
	RemainingSeats             map[string]map[string]int `json:"remaining_seats"`
	CancelledFlights           []string                  `json:"cancelled_flights"`
}

type RebookingLedger struct {
	LedgerVersion      int                       `json:"ledger_version"`
	InputDigest        string                    `json:"input_digest"`
	StageSequence      int                       `json:"stage_sequence"`
	PriorityPickMode   string                    `json:"priority_pick_mode"`
	RemainingSeatMap   map[string]map[string]int `json:"remaining_seat_map"`
}

type PlanEntry struct {
	PassengerID     string        `json:"passenger_id"`
	Status          string        `json:"status"`
	PriorityScore   int           `json:"priority_score"`
	RebookedLegs    []RebookedLeg `json:"rebooked_legs"`
	RebookRank      int           `json:"rebook_rank"`
}

type RebookingPlan struct {
	PlanVersion        int         `json:"plan_version"`
	PlanFingerprint    string      `json:"plan_fingerprint"`
	LedgerStageSequence int        `json:"ledger_stage_sequence"`
	Entries            []PlanEntry `json:"entries"`
}

type PassengerSummary struct {
	SummaryVersion      int      `json:"summary_version"`
	DisruptionDate      string   `json:"disruption_date"`
	TotalPassengers     int      `json:"total_passengers"`
	RebookedCount       int      `json:"rebooked_count"`
	StandbyCount        int      `json:"standby_count"`
	UnaffectedCount     int      `json:"unaffected_count"`
	PriorityPickMode    string   `json:"priority_pick_mode"`
	CancelledFlightList []string `json:"cancelled_flight_list"`
}
