// Package worldmap loads a playtest world description from disk and gives
// callers a deterministic, ID-ascending view of the rooms, exits, actions,
// and items it contains. Files on disk store exits/actions/items in
// descending ID order (an authoring convention); this package is the single
// place that re-orders them ascending so every other package sees a stable
// view regardless of how the fixture was authored.
package worldmap

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

// Room is a single location an oracle session can occupy.
type Room struct {
	ID    string `json:"id"`
	Title string `json:"title"`
}

// Exit connects two rooms behind an optional set of required items.
type Exit struct {
	ID            string   `json:"id"`
	From          string   `json:"from"`
	To            string   `json:"to"`
	Verb          string   `json:"verb"`
	RequiredItems []string `json:"required_items"`
}

// Item is a takeable object seeded in a room.
type Item struct {
	ID     string `json:"id"`
	RoomID string `json:"room_id"`
}

// Action is a room-local verb/target interaction (not a move, not a take).
type Action struct {
	ID            string   `json:"id"`
	RoomID        string   `json:"room_id"`
	Verb          string   `json:"verb"`
	Target        string   `json:"target"`
	RequiredItems []string `json:"required_items"`
}

// World is the full playtest geography for one world_id.
type World struct {
	WorldID   string   `json:"world_id"`
	StartRoom string   `json:"start_room"`
	Rooms     []Room   `json:"rooms"`
	Exits     []Exit   `json:"exits"`
	Items     []Item   `json:"items"`
	Actions   []Action `json:"actions"`
}

// BundledRoot is where world.json fixtures shipped in the image live.
const BundledRoot = "/app/data/worlds"

// HiddenRoot is where verifier-only world fixtures are mounted.
const HiddenRoot = "/opt/verifier-fixtures/worlds"

// Load reads and parses a world.json file at the given path.
func Load(path string) (*World, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("worldmap: read %s: %w", path, err)
	}
	var w World
	if err := json.Unmarshal(raw, &w); err != nil {
		return nil, fmt.Errorf("worldmap: parse %s: %w", path, err)
	}
	return &w, nil
}

// LoadByID locates a world.json for world_id, checking the bundled root
// first and the hidden verifier root second, and loads it.
func LoadByID(worldID string) (*World, error) {
	candidates := []string{
		filepath.Join(BundledRoot, worldID, "world.json"),
		filepath.Join(HiddenRoot, worldID, "world.json"),
	}
	for _, path := range candidates {
		if _, err := os.Stat(path); err == nil {
			return Load(path)
		}
	}
	return nil, fmt.Errorf("worldmap: no world.json found for world_id=%s", worldID)
}

// HasRoom reports whether roomID exists in the world.
func (w *World) HasRoom(roomID string) bool {
	for _, r := range w.Rooms {
		if r.ID == roomID {
			return true
		}
	}
	return false
}

// ExitsInRoomAscending returns exits leaving roomID sorted by exit ID
// ascending, regardless of on-disk order.
func (w *World) ExitsInRoomAscending(roomID string) []Exit {
	var out []Exit
	for _, e := range w.Exits {
		if e.From == roomID {
			out = append(out, e)
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out
}

// ActionsInRoomAscending returns actions available in roomID sorted by
// action ID ascending, regardless of on-disk order.
func (w *World) ActionsInRoomAscending(roomID string) []Action {
	var out []Action
	for _, a := range w.Actions {
		if a.RoomID == roomID {
			out = append(out, a)
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out
}

// ItemsInRoomAscending returns items seeded in roomID sorted by item ID
// ascending, regardless of on-disk order.
func (w *World) ItemsInRoomAscending(roomID string) []Item {
	var out []Item
	for _, it := range w.Items {
		if it.RoomID == roomID {
			out = append(out, it)
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out
}
