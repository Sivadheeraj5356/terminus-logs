package consumer

import (
	"streamkit/internal/config"
	"streamkit/internal/model"
	"streamkit/runtime/collect"
)

func FetchBatch(raw []model.Record, available, maxRecords, minBytes int, profile config.RuntimeProfile) []model.Record {
	return collect.Collect(raw, available, maxRecords, minBytes, profile.FetchUseByteCredit)
}
