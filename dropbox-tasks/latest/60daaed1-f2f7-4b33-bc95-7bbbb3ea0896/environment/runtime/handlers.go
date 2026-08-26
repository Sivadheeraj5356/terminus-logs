package main

import "net/http"

type Handlers struct {
	replay *ReplayStore
}

func NewHandlers(replay *ReplayStore) *Handlers {
	return &Handlers{replay: replay}
}

func (h *Handlers) PublicPing(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"service": "local-api",
		"status":  "ok",
	})
}

func (h *Handlers) PublicDocs(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"docs": []string{"/v1/public/ping", "/v1/public/docs", "/v1/public/state", "/v1/admin/profile", "/v1/admin/audit"},
	})
}

func (h *Handlers) PublicState(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"state": h.replay.Stats()})
}

func (h *Handlers) AdminProfile(w http.ResponseWriter, _ *http.Request, who tokenRecord) {
	writeJSON(w, http.StatusOK, map[string]any{
		"user": who.User,
		"role": who.Role,
	})
}

func (h *Handlers) AdminAudit(w http.ResponseWriter, _ *http.Request, who tokenRecord) {
	writeJSON(w, http.StatusOK, map[string]any{
		"actor":  who.User,
		"events": []string{"login", "read_config", "rotate_key"},
	})
}
