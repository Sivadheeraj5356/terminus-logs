#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/output

jq -n --slurpfile stale /app/metadata/stale-stations.json '
  $stale[0] as $stations
  | {
      readings_count: 0,
      station_count: ($stations | length),
      missing_station_count: 0,
      stations: ($stations | to_entries | map({
        station_id: .key,
        metadata_status: "bundled",
        name: .value.name,
        time_zone: .value.time_zone,
        reading_count: 0,
        average_temp_c: null,
        quality_flags: [],
        requires_review: false
      }))
    }
' > /app/output/weather-evidence.json

cp /app/metadata/stale-stations.json /app/output/noaa-stations.json
