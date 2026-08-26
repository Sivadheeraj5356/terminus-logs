package load

import (
	"encoding/json"
	"os"
	"path/filepath"

	"passenger-rebooking-engine/internal/model"
)

type Bundle struct {
	Passengers   []model.Passenger
	Cancellations []model.CancellationEvent
	Flights      []model.FlightInventory
	Alliances    model.AllianceDoc
	Policy       model.Policy
}

func dataRoot() string {
	override := os.Getenv("TB3_DATA_DIR")
	if len(override) > 0 && override[0] == '/' {
		return override
	}
	return "/app/data"
}

func stateRoot() string {
	override := os.Getenv("TB3_STATE_DIR")
	if len(override) > 0 && override[0] == '/' {
		return override
	}
	return "/app/state"
}

func outputRoot() string {
	override := os.Getenv("TB3_OUTPUT_DIR")
	if len(override) > 0 && override[0] == '/' {
		return override
	}
	return "/app/output"
}

func readJSON(path string, dest any) error {
	raw, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(raw, dest)
}

func Load() (*Bundle, error) {
	root := dataRoot()
	var passengers struct {
		Passengers []model.Passenger `json:"passengers"`
	}
	var cancellations struct {
		Cancellations []model.CancellationEvent `json:"cancellations"`
	}
	var inventory struct {
		Flights []model.FlightInventory `json:"flights"`
	}
	var alliances model.AllianceDoc
	var policy model.Policy

	if err := readJSON(filepath.Join(root, "passengers.json"), &passengers); err != nil {
		return nil, err
	}
	if err := readJSON(filepath.Join(root, "flight-cancellations.json"), &cancellations); err != nil {
		return nil, err
	}
	if err := readJSON(filepath.Join(root, "seat-inventory.json"), &inventory); err != nil {
		return nil, err
	}
	if err := readJSON(filepath.Join(root, "alliance-agreements.json"), &alliances); err != nil {
		return nil, err
	}
	if err := readJSON(filepath.Join(root, "airline-policies.json"), &policy); err != nil {
		return nil, err
	}

	return &Bundle{
		Passengers:    passengers.Passengers,
		Cancellations: cancellations.Cancellations,
		Flights:       inventory.Flights,
		Alliances:     alliances,
		Policy:        policy,
	}, nil
}

func SnapshotPath() string {
	return filepath.Join(stateRoot(), "rebooking-snapshot.json")
}

func LedgerPath() string {
	return filepath.Join(stateRoot(), "rebooking-ledger.json")
}

func PlanPath() string {
	return filepath.Join(outputRoot(), "rebooking-plan.json")
}

func SummaryPath() string {
	return filepath.Join(outputRoot(), "passenger-summary.json")
}
