package config

import (
	"strconv"
	"strings"
)

func decodeToml(text string, site *Settings) error {
	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") || !strings.Contains(line, "=") {
			continue
		}
		key, val := splitKeyVal(line)
		val = strings.Trim(val, "\"")
		switch key {
		case "orchard_id":
			site.OrchardID = val
		case "base_temp_c":
			f, err := strconv.ParseFloat(val, 64)
			if err != nil {
				return err
			}
			site.BaseTempC = f
		case "ingest_unit":
			site.IngestUnit = strings.ToUpper(val)
		case "bucket_anchor_epoch":
			n, err := strconv.ParseInt(val, 10, 64)
			if err != nil {
				return err
			}
			site.BucketAnchorEpoch = n
		}
	}
	return nil
}

func splitKeyVal(line string) (string, string) {
	parts := strings.SplitN(line, "=", 2)
	return strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1])
}
