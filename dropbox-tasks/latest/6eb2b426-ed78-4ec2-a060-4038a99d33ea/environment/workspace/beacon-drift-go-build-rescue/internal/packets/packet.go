package packets

import (
    "embed"
    "encoding/json"
    "fmt"
    "math"
    "os"
    "sort"
    "strings"
)

//go:embed config/beacon_profiles.json
var profileFS embed.FS

type Profile struct {
    ID             string  `json:"id"`
    MaxDriftMeters float64 `json:"max_drift_meters"`
    MinBattery     int     `json:"min_battery_percent"`
    AllowedZones   []string `json:"allowed_zones"`
}

type Packet struct {
    BeaconID      string  `json:"beacon_id"`
    Sequence      int     `json:"sequence"`
    Zone          string  `json:"zone"`
    DriftMeters   float64 `json:"drift_meters"`
    BatteryPct    int     `json:"battery_percent"`
    RecordedAtUTC string  `json:"recorded_at_utc"`
}

type Result struct {
    BeaconID string   `json:"beacon_id"`
    Profile  string   `json:"profile"`
    Accepted bool     `json:"accepted"`
    Reasons  []string `json:"reasons"`
    Severity string   `json:"severity"`
}

func LoadProfiles() (map[string]Profile, error) {
    raw, err := profileFS.ReadFile("config/beacon_profiles.json")
    if err != nil {
        return nil, fmt.Errorf("cannot load bundled profiles: %w", err)
    }
    var profiles []Profile
    if err := json.Unmarshal(raw, &profiles); err != nil {
        return nil, err
    }
    out := map[string]Profile{}
    for _, p := range profiles {
        out[p.ID] = p
    }
    return out, nil
}

func ValidatePacket(profileID, packetPath string) (Result, error) {
    profiles, err := LoadProfiles()
    if err != nil {
        return Result{}, err
    }
    profile, ok := profiles[profileID]
    if !ok {
        return Result{}, fmt.Errorf("unknown profile %s", profileID)
    }

    raw, err := os.ReadFile(packetPath)
    if err != nil {
        return Result{}, err
    }
    var packet Packet
    if err := json.Unmarshal(raw, &packet); err != nil {
        return Result{}, err
    }

    reasons := []string{}
    if strings.TrimSpace(packet.BeaconID) == "" {
        reasons = append(reasons, "missing_beacon_id")
    }
    if packet.Sequence <= 0 {
        reasons = append(reasons, "invalid_sequence")
    }
    if !contains(profile.AllowedZones, packet.Zone) {
        reasons = append(reasons, "zone_not_allowed")
    }
    if math.Abs(packet.DriftMeters) > profile.MaxDriftMeters {
        reasons = append(reasons, "drift_limit_exceeded")
    }
    if packet.BatteryPct < profile.MinBattery {
        reasons = append(reasons, "battery_below_policy")
    }
    sort.Strings(reasons)

    severity := "clear"
    if len(reasons) > 0 {
        severity = "hold"
    }
    return Result{BeaconID: packet.BeaconID, Profile: profile.ID, Accepted: len(reasons) == 0, Reasons: reasons, Severity: severity}, nil
}

func contains(items []string, value string) bool {
    for _, item := range items {
        if item == value {
            return true
        }
    }
    return false
}
