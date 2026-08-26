package reloclogic

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
)

// WriteReport writes the report with normative key order and a trailing newline.
func WriteReport(path string, rpt Report) error {
	var buf bytes.Buffer
	buf.WriteString("{\n")
	buf.WriteString(`  "summary": `)
	sum, err := marshalSummary(rpt.Summary)
	if err != nil {
		return err
	}
	buf.Write(sum)
	buf.WriteString(",\n")
	buf.WriteString(`  "batches": [`)
	for i, m := range rpt.Batches {
		if i > 0 {
			buf.WriteByte(',')
		}
		buf.WriteByte('\n')
		mb, err := marshalBatch(m)
		if err != nil {
			return err
		}
		buf.WriteString("    ")
		buf.Write(mb)
	}
	if len(rpt.Batches) > 0 {
		buf.WriteByte('\n')
		buf.WriteString("  ")
	}
	buf.WriteString("]\n}\n")
	return os.WriteFile(path, buf.Bytes(), 0o644)
}

func marshalSummary(s Summary) ([]byte, error) {
	return marshalOrdered([]any{
		"batches_analyzed", s.BatchesAnalyzed,
		"failed_batches", s.FailedBatches,
		"clean_batches", s.CleanBatches,
		"total_findings", s.TotalFindings,
		"replay_runs", s.ReplayRuns,
		"replay_passed", s.ReplayPassed,
	})
}

func marshalBatch(m BatchResult) ([]byte, error) {
	findings := m.Findings
	if findings == nil {
		findings = []Finding{}
	}
	fb, err := marshalFindings(findings)
	if err != nil {
		return nil, err
	}
	rb, err := marshalOrdered([]any{
		"schedules_run", m.Replay.SchedulesRun,
		"schedules_passed", m.Replay.SchedulesPassed,
		"stable", m.Replay.Stable,
	})
	if err != nil {
		return nil, err
	}
	var buf bytes.Buffer
	buf.WriteByte('{')
	writeKV(&buf, "batch_id", m.BatchID, true)
	writeKV(&buf, "relocation_ok", m.RelocationOK, false)
	buf.WriteString(`,"findings":`)
	buf.Write(fb)
	writeKV(&buf, "mapping_ok", m.MappingOK, false)
	writeKV(&buf, "rewrite_ok", m.RewriteOK, false)
	writeKV(&buf, "isolation_ok", m.IsolationOK, false)
	writeKV(&buf, "identity_ok", m.IdentityOK, false)
	writeKV(&buf, "rollback_ok", m.RollbackOK, false)
	buf.WriteString(`,"replay":`)
	buf.Write(rb)
	buf.WriteByte('}')
	return buf.Bytes(), nil
}

func marshalFindings(findings []Finding) ([]byte, error) {
	if len(findings) == 0 {
		return []byte("[]"), nil
	}
	var buf bytes.Buffer
	buf.WriteByte('[')
	for i, f := range findings {
		if i > 0 {
			buf.WriteByte(',')
		}
		b, err := marshalOrdered([]any{
			"kind", f.Kind,
			"subject", f.Subject,
			"expected", f.Expected,
			"observed", f.Observed,
			"rule_id", f.RuleID,
		})
		if err != nil {
			return nil, err
		}
		buf.Write(b)
	}
	buf.WriteByte(']')
	return buf.Bytes(), nil
}

func writeKV(buf *bytes.Buffer, key string, val any, first bool) {
	if !first {
		buf.WriteByte(',')
	}
	kb, _ := json.Marshal(key)
	vb, _ := json.Marshal(val)
	buf.Write(kb)
	buf.WriteByte(':')
	buf.Write(vb)
}

func marshalOrdered(kv []any) ([]byte, error) {
	if len(kv)%2 != 0 {
		return nil, fmt.Errorf("ordered kv length")
	}
	var buf bytes.Buffer
	buf.WriteByte('{')
	for i := 0; i < len(kv); i += 2 {
		if i > 0 {
			buf.WriteByte(',')
		}
		kb, err := json.Marshal(kv[i])
		if err != nil {
			return nil, err
		}
		vb, err := json.Marshal(kv[i+1])
		if err != nil {
			return nil, err
		}
		buf.Write(kb)
		buf.WriteByte(':')
		buf.Write(vb)
	}
	buf.WriteByte('}')
	return buf.Bytes(), nil
}
