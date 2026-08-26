package packets_test

import (
    "path/filepath"
    "testing"

    "example.com/coastal/beacon-drift/internal/packets"
)

func TestValidFixtureAccepted(t *testing.T) {
    result, err := packets.ValidatePacket("north-pier", filepath.Join("..", "..", "fixtures", "packet_valid.json"))
    if err != nil {
        t.Fatalf("unexpected error: %v", err)
    }
    if !result.Accepted || result.Severity != "clear" || len(result.Reasons) != 0 {
        t.Fatalf("expected clear accepted result, got %#v", result)
    }
}

func TestInvalidFixtureRejected(t *testing.T) {
    result, err := packets.ValidatePacket("north-pier", filepath.Join("..", "..", "fixtures", "packet_invalid.json"))
    if err != nil {
        t.Fatalf("unexpected error: %v", err)
    }
    if result.Accepted || result.Severity != "hold" {
        t.Fatalf("expected held result, got %#v", result)
    }
    if len(result.Reasons) < 2 {
        t.Fatalf("expected multiple policy reasons, got %#v", result.Reasons)
    }
}
