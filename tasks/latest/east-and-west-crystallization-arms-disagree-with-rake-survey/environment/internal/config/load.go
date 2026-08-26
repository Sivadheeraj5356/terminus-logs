package config

import (
	"database/sql"
	"encoding/json"
	"os"
	"path/filepath"

	_ "modernc.org/sqlite"

	"lab.local/salt_pond/pkg/pond"
	"lab.local/salt_pond/pkg/tape"
)

// Bundle is everything needed for one replay.
type Bundle struct {
	Plan     pond.Plan
	Arms     []pond.Arm
	Tape     []tape.Row
	Surveys  map[string]map[int][2]float64
}

func ActiveDir(root string) (string, error) {
	return filepath.Join(root, "data", "active"), nil
}

func LoadBundle(dir string) (Bundle, error) {
	raw, err := os.ReadFile(filepath.Join(dir, "pond_plan.json"))
	if err != nil {
		return Bundle{}, err
	}
	var plan pond.Plan
	if err := json.Unmarshal(raw, &plan); err != nil {
		return Bundle{}, err
	}
	tapeRows, err := loadTape(filepath.Join(dir, "wind_tape.jsonl"))
	if err != nil {
		return Bundle{}, err
	}
	arms, surveys, err := loadLane(filepath.Join(dir, "lane.db"))
	if err != nil {
		return Bundle{}, err
	}
	return Bundle{Plan: plan, Arms: arms, Tape: tapeRows, Surveys: surveys}, nil
}

func loadTape(path string) ([]tape.Row, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var out []tape.Row
	start := 0
	for i := 0; i <= len(data); i++ {
		if i == len(data) || data[i] == '\n' {
			line := string(data[start:i])
			start = i + 1
			if line == "" {
				continue
			}
			var row tape.Row
			if err := json.Unmarshal([]byte(line), &row); err != nil {
				continue
			}
			out = append(out, row)
		}
	}
	return out, nil
}

func loadLane(path string) ([]pond.Arm, map[string]map[int][2]float64, error) {
	db, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, nil, err
	}
	defer db.Close()
	// Field reports emit arms in packing sequence; arm_label is display-only.
	rows, err := db.Query("SELECT arm_id, arm_label, base_front, sealed FROM arm_lane ORDER BY arm_label")
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()
	var arms []pond.Arm
	for rows.Next() {
		var id, label, sealed int
		var base float64
		if err := rows.Scan(&id, &label, &base, &sealed); err != nil {
			return nil, nil, err
		}
		arms = append(arms, pond.Arm{
			ArmKey:    keyFor(id),
			ArmID:     id,
			ArmLabel:  label,
			BaseFront: base,
			Sealed:    sealed != 0,
		})
	}
	srows, err := db.Query("SELECT day, arm_key, rake_m, lidar_m FROM survey_reading ORDER BY day, arm_key")
	if err != nil {
		return nil, nil, err
	}
	defer srows.Close()
	surveys := map[string]map[int][2]float64{}
	for srows.Next() {
		var day int
		var key string
		var rake, lidar float64
		if err := srows.Scan(&day, &key, &rake, &lidar); err != nil {
			return nil, nil, err
		}
		if surveys[key] == nil {
			surveys[key] = map[int][2]float64{}
		}
		surveys[key][day] = [2]float64{rake, lidar}
	}
	return arms, surveys, srows.Err()
}

func keyFor(id int) string {
	return "L" + itoa(id)
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var buf [8]byte
	i := len(buf)
	for n > 0 {
		i--
		buf[i] = byte('0' + n%10)
		n /= 10
	}
	return string(buf[i:])
}
