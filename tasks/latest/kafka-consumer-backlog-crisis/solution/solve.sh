#!/bin/bash
if [ -z "${BASH_VERSION:-}" ]; then
  exec /bin/bash "$0" "$@"
fi
set -euo pipefail

test -d /app/environment

cat > /app/environment/runtime/collect/collect.go << 'GOEOF'
package collect

import "streamkit/internal/model"

func RecordWeight(rec model.Record) int {
	return 1024 + len(rec.Value)*256
}

func mergeUnits(available, maxRecords, minBytes int, recs []model.Record) []model.Record {
	_ = minBytes
	if available <= 0 || len(recs) == 0 {
		return nil
	}
	if maxRecords <= 0 || maxRecords > len(recs) {
		maxRecords = len(recs)
	}
	return recs[:maxRecords]
}

func Collect(recs []model.Record, available, maxRecords, minBytes int, useByteCredit bool) []model.Record {
	_ = useByteCredit
	return mergeUnits(available, maxRecords, minBytes, recs)
}
GOEOF

cat > /app/environment/pkg/pull/lanes.go << 'GOEOF'
package pull

type Gate struct {
	Stride int
}

func NewGate(stride int) *Gate {
	if stride < 1 {
		stride = 1
	}
	return &Gate{Stride: stride}
}

func (g *Gate) Active(lanes []int, tick int) []int {
	if len(lanes) == 0 {
		return nil
	}
	stride := g.Stride
	if stride < 1 {
		stride = 1
	}
	start := tick % len(lanes)
	out := []int{}
	for i := 0; i < len(lanes); i += stride {
		out = append(out, lanes[(start+i)%len(lanes)])
	}
	return out
}

func ActiveLanes(lanes []int, tick int) []int {
	return NewGate(1).Active(lanes, tick)
}
GOEOF

cat > /app/environment/ingest/layout/slots.go << 'GOEOF'
package layout

func AssignLanes(laneCount, slotCount int) [][]int {
	out := [][]int{}
	for i := 0; i < slotCount; i++ {
		out = append(out, []int{})
	}
	if slotCount <= 0 {
		return out
	}
	base := laneCount / slotCount
	extra := laneCount % slotCount
	cursor := 0
	for slot := 0; slot < slotCount; slot++ {
		width := base
		if slot < extra {
			width++
		}
		for i := 0; i < width; i++ {
			out[slot] = append(out[slot], cursor)
			cursor++
		}
	}
	return out
}

func Loads(assignments [][]int) []int {
	loads := []int{}
	for _, lanes := range assignments {
		loads = append(loads, len(lanes))
	}
	return loads
}

func Spread(assignments [][]int) int {
	loads := Loads(assignments)
	if len(loads) == 0 {
		return 0
	}
	min, max := loads[0], loads[0]
	for _, v := range loads[1:] {
		if v < min {
			min = v
		}
		if v > max {
			max = v
		}
	}
	return max - min
}
GOEOF

cat > /app/environment/internal/config/profile.go << 'GOEOF'
package config

type RuntimeProfile struct {
	LaneStride         int
	FetchUseByteCredit bool
	MarkScaleByPull    bool
	PlacementHeavyLast bool
}

func RuntimeFromCluster(c ClusterProfile) RuntimeProfile {
	rp := RuntimeProfile{
		LaneStride:         1,
		FetchUseByteCredit: false,
		MarkScaleByPull:    false,
		PlacementHeavyLast: false,
	}
	if c.LaneScan == "full" {
		rp.LaneStride = 1
	}
	if c.FetchCreditMode == "floor" {
		rp.FetchUseByteCredit = false
	}
	if c.MarkStyle == "interval" {
		rp.MarkScaleByPull = false
	}
	if c.GroupProtocol == "cooperative-sticky" {
		rp.PlacementHeavyLast = false
	}
	return rp
}
GOEOF

cat > /app/environment/internal/member/roster.go << 'GOEOF'
package member

func RebalanceTail(assign [][]int) [][]int {
	return assign
}
GOEOF

cat > /app/environment/internal/offset/journal.go << 'GOEOF'
package offset

type Journal struct {
	pending int
}

func NewJournal() *Journal {
	return &Journal{}
}

func (j *Journal) Add(n int) {
	if n > 0 {
		j.pending += n
	}
}

func (j *Journal) TryFlush(interval, lastPull int) bool {
	_ = lastPull
	if j.pending <= 0 {
		return false
	}
	if interval <= 0 {
		j.pending = 0
		return true
	}
	if j.pending < interval {
		return false
	}
	j.pending = 0
	return true
}
GOEOF

cd /app/environment
go run ./cmd/stream-bench \
  --workloads /app/environment/data/workloads.json \
  --cluster /app/environment/configs/cluster.json \
  --report /app/ingest_recovery_report.json

test -s /app/ingest_recovery_report.json
