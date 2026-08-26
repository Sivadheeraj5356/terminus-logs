package audit

import (
	"encoding/json"
	"os"

	"baylock/internal/config"
	"baylock/internal/domain"
)

type cacheEntry struct {
	LastActor string `json:"last_actor"`
	Count     int    `json:"count"`
}

func ReadCache() (*cacheEntry, error) {
	path := config.AuditFile
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return &cacheEntry{}, nil
		}
		return nil, err
	}
	var entry cacheEntry
	if err := json.Unmarshal(data, &entry); err != nil {
		return nil, err
	}
	return &entry, nil
}

func RenderSummary(audits []domain.AuditRecord) string {
	entry, _ := ReadCache()
	if entry.LastActor != "" {
		return entry.LastActor
	}
	if len(audits) == 0 {
		return "none"
	}
	return audits[len(audits)-1].ActorRef
}
