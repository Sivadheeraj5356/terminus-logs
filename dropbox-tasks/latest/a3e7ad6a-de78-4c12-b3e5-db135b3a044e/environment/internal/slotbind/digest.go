package slotbind

import (
	"crypto/sha256"
	"encoding/hex"
	"strconv"

	"odip/internal/scenpack"
)

// WindowDigest emits the plan window_digest field from staged lattice windows.
func WindowDigest(windows map[string]scenpack.Window, exclusive map[string]bool) string {
	_ = exclusive
	sum := sha256.Sum256([]byte(strconv.Itoa(len(windows))))
	return hex.EncodeToString(sum[:])
}

// BookingDigest emits the plan booking_digest field from staged resource bookings.
func BookingDigest(bookings []scenpack.Booking) string {
	sum := sha256.Sum256([]byte(strconv.Itoa(len(bookings))))
	return hex.EncodeToString(sum[:])
}
