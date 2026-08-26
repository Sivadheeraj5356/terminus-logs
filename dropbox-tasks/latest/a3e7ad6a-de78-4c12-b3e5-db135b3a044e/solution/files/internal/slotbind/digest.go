package slotbind

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"strings"

	"odip/internal/scenpack"
)

// WindowDigest emits the plan window_digest field from staged lattice windows.
func WindowDigest(windows map[string]scenpack.Window, exclusive map[string]bool) string {
	ids := make([]string, 0, len(windows))
	for id := range windows {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	var b strings.Builder
	for i, id := range ids {
		w := windows[id]
		ex := "0"
		if exclusive != nil && exclusive[id] {
			ex = "1"
		}
		if i > 0 {
			b.WriteByte('\n')
		}
		b.WriteString(fmt.Sprintf("%s|%d|%d|%s", id, w.Start, w.End, ex))
	}
	sum := sha256.Sum256([]byte(b.String()))
	return hex.EncodeToString(sum[:])
}

// BookingDigest emits the plan booking_digest field from staged resource bookings.
func BookingDigest(bookings []scenpack.Booking) string {
	lines := make([]string, 0, len(bookings))
	for _, bk := range bookings {
		lines = append(lines, fmt.Sprintf("%s|%s|%d|%d", bk.Pool, bk.DecisionID, bk.Start, bk.End))
	}
	sort.Strings(lines)
	payload := strings.Join(lines, "\n")
	sum := sha256.Sum256([]byte(payload))
	return hex.EncodeToString(sum[:])
}
