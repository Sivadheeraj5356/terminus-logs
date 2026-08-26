// Package httpapi wires the labyrinth oracle's HTTP surface: health,
// session creation, the probe/assemble snapshot pipeline, and the attempt
// endpoint used to move a session through its world.
package httpapi

import (
	"encoding/json"
	"net/http"
	"os"

	"labyrinthoracle/internal/chronicle"
	"labyrinthoracle/internal/hintassemble"
	"labyrinthoracle/internal/filters"
	"labyrinthoracle/internal/probe"
	"labyrinthoracle/internal/rules"
	"labyrinthoracle/internal/session"
	"labyrinthoracle/internal/worldmap"
)

// NewRouter builds the labyrinth oracle's HTTP handler.
func NewRouter(store *session.Store) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", handleHealth)
	mux.HandleFunc("POST /sessions", handleCreateSession(store))
	mux.HandleFunc("GET /sessions/{id}/oracle", handleOracle(store))
	mux.HandleFunc("POST /sessions/{id}/probe", handleProbe(store))
	mux.HandleFunc("POST /sessions/{id}/assemble", handleAssemble(store))
	mux.HandleFunc("POST /sessions/{id}/attempt", handleAttempt(store))
	return mux
}

func writeJSON(w http.ResponseWriter, status int, body interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]string{"error": message})
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

type createSessionRequest struct {
	WorldID   string   `json:"world_id"`
	RoomID    string   `json:"room_id"`
	Inventory []string `json:"inventory"`
}

func handleCreateSession(store *session.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req createSessionRequest
		if r.Body != nil {
			_ = json.NewDecoder(r.Body).Decode(&req)
		}
		worldID := req.WorldID
		if worldID == "" {
			worldID = "labyrinth"
		}
		world, err := worldmap.LoadByID(worldID)
		if err != nil {
			writeError(w, http.StatusBadRequest, "unknown world_id")
			return
		}
		roomID := req.RoomID
		if roomID == "" {
			roomID = world.StartRoom
		}
		if !world.HasRoom(roomID) {
			writeError(w, http.StatusBadRequest, "unknown room_id for world")
			return
		}
		sess := store.Create(worldID, roomID, req.Inventory)
		view := sess.View()
		writeJSON(w, http.StatusCreated, sessionView(view))
	}
}

func sessionView(view session.Snapshot) map[string]interface{} {
	inv := view.Inventory
	cons := view.Consumed
	failed := view.Failed
	if inv == nil {
		inv = []string{}
	}
	if cons == nil {
		cons = []string{}
	}
	if failed == nil {
		failed = []session.FailedAttempt{}
	}
	return map[string]interface{}{
		"session_id": view.ID,
		"world_id":   view.WorldID,
		"room":       view.Room,
		"inventory":  inv,
		"consumed":   cons,
		"failed":     failed,
	}
}

func lookupSession(store *session.Store, r *http.Request) (*session.Session, bool) {
	id := r.PathValue("id")
	return store.Get(id)
}

func handleOracle(store *session.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		sess, ok := lookupSession(store, r)
		if !ok {
			writeError(w, http.StatusNotFound, "unknown session")
			return
		}
		view := sess.View()
		world, err := worldmap.LoadByID(view.WorldID)
		if err != nil {
			writeError(w, http.StatusInternalServerError, "world load failed")
			return
		}
		chroniclePath := chronicle.Resolve(view.WorldID)
		if _, err := probe.WriteSnapshot(sess, world, chroniclePath); err != nil {
			writeError(w, http.StatusInternalServerError, "probe failed")
			return
		}
		result, err := hintassemble.Assemble(sess)
		if err != nil {
			writeError(w, http.StatusInternalServerError, "assemble failed")
			return
		}
		body := map[string]interface{}{
			"session_id": view.ID,
			"room":       view.Room,
			"hints":      result.Hints,
		}
		if result.Refused {
			body["refused"] = true
			body["reason"] = result.Reason
		} else if result.RouteDigest != "" {
			body["route_digest"] = result.RouteDigest
		}
		writeJSON(w, http.StatusOK, body)
	}
}

func handleProbe(store *session.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		sess, ok := lookupSession(store, r)
		if !ok {
			writeError(w, http.StatusNotFound, "unknown session")
			return
		}
		view := sess.View()
		world, err := worldmap.LoadByID(view.WorldID)
		if err != nil {
			writeError(w, http.StatusInternalServerError, "world load failed")
			return
		}
		chroniclePath := chronicle.Resolve(view.WorldID)
		snap, err := probe.WriteSnapshot(sess, world, chroniclePath)
		if err != nil {
			writeError(w, http.StatusInternalServerError, "probe failed")
			return
		}
		writeJSON(w, http.StatusOK, map[string]interface{}{
			"session_id":      snap.SessionID,
			"gather_seq":      snap.GatherSeq,
			"candidate_count": len(snap.Candidates),
			"staged_at":       probe.ScratchPath(snap.SessionID),
		})
	}
}

func handleAssemble(store *session.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		sess, ok := lookupSession(store, r)
		if !ok {
			writeError(w, http.StatusNotFound, "unknown session")
			return
		}
		result, err := hintassemble.Assemble(sess)
		if err != nil {
			writeError(w, http.StatusInternalServerError, "assemble failed")
			return
		}
		writeJSON(w, http.StatusOK, result)
	}
}

type attemptRequest struct {
	Verb   string `json:"verb"`
	Target string `json:"target"`
}

func handleAttempt(store *session.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		sess, ok := lookupSession(store, r)
		if !ok {
			writeError(w, http.StatusNotFound, "unknown session")
			return
		}
		var req attemptRequest
		if r.Body != nil {
			_ = json.NewDecoder(r.Body).Decode(&req)
		}
		view := sess.View()
		world, err := worldmap.LoadByID(view.WorldID)
		if err != nil {
			writeError(w, http.StatusInternalServerError, "world load failed")
			return
		}
		chroniclePath := chronicle.Resolve(view.WorldID)
		chronicleText, err := readChronicle(chroniclePath)
		if err != nil {
			writeError(w, http.StatusInternalServerError, "chronicle load failed")
			return
		}
		forbidden := rules.Load(chronicleText)

		ok2, reason := applyAttempt(sess, world, forbidden, req.Verb, req.Target)
		if !ok2 {
			sess.RecordFailure(req.Verb, req.Target)
		}
		out := sess.View()
		writeJSON(w, http.StatusOK, map[string]interface{}{
			"session_id": out.ID,
			"room":       out.Room,
			"inventory":  out.Inventory,
			"consumed":   out.Consumed,
			"failed":     out.Failed,
			"ok":         ok2,
			"reason":     reason,
		})
	}
}

func applyAttempt(sess *session.Session, world *worldmap.World, forbidden []rules.ForbiddenRule, verb, target string) (bool, string) {
	view := sess.View()

	if verb == "take" {
		for _, it := range world.ItemsInRoomAscending(view.Room) {
			if it.ID == target {
				if rules.ForbiddenIn(forbidden, view.Room, verb, target) {
					return false, "forbidden"
				}
				if !filters.NotIn(target, view.Inventory) {
					return false, "already-held"
				}
				sess.AddItem(target)
				return true, ""
			}
		}
		return false, "no-such-item"
	}

	for _, e := range world.ExitsInRoomAscending(view.Room) {
		if e.Verb == verb && e.To == target {
			if rules.ForbiddenIn(forbidden, view.Room, verb, target) {
				return false, "forbidden"
			}
			if !filters.InventoryOK(e.RequiredItems, view.Inventory) {
				return false, "missing-items"
			}
			sess.MoveTo(target)
			return true, ""
		}
	}

	for _, a := range world.ActionsInRoomAscending(view.Room) {
		if a.Verb == verb && a.Target == target {
			if rules.ForbiddenIn(forbidden, view.Room, verb, target) {
				return false, "forbidden"
			}
			if !filters.InventoryOK(a.RequiredItems, view.Inventory) {
				return false, "missing-items"
			}
			if !filters.NotIn(target, view.Consumed) {
				return false, "already-consumed"
			}
			sess.Consume(target)
			return true, ""
		}
	}

	return false, "unknown-attempt"
}

func readChronicle(path string) (string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return string(raw), nil
}
