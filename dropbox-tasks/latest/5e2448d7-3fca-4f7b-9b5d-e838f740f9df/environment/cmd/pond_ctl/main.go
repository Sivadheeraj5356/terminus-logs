// Report JSON for /app/output/front_report.json:
//
// schema_version — string
// pond_id — string
// mast_epoch — uint32
// arms — array of {arm_key, front_m, advance_cmd, survey_m, telemetry_ok}
// daily_fronts — array of {day, vertices:[{arm_key, front_m}]}
// calm_latch_events — int
// survey_mismatch — int
// front_sum — int
// digest_hex — string
//
// Root object contains only these keys.
package main

import (
	"log"
	"os"

	"lab.local/salt_pond/internal/driver"
)

func main() {
	if os.Getenv("TB_POND_FIXTURE") != "1" {
		log.Fatal("TB_POND_FIXTURE unset or not 1")
	}
	rep, err := driver.RunActive("/app")
	if err != nil {
		log.Fatal(err)
	}
	if err := driver.EmitReport("/app/output/front_report.json", rep); err != nil {
		log.Fatal(err)
	}
}
