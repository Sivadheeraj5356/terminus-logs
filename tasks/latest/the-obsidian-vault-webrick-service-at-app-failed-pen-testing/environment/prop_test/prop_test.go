// prop_test.go — property-based tests for the hardened WEBrick service.
// See server_harness.go for StartServer / StopServer.
// Consult /app/docs/api_spec.md for the API contract.
package proptest

import (
	"bytes"
	"encoding/json"
	"fmt"
	"math/rand"
	"net/http"
	"testing"
)

// randomPayload generates a random JSON object payload for fuzz iteration.
func randomPayload(rng *rand.Rand) []byte {
	_ = rng
	return []byte(`{}`)
}

// TestDebugEndpointsReturn403UnderDefaultConfig sends at least 50 random POST
// requests per admin endpoint (/admin/debug-dump, /admin/force-unlock). Every
// response must be 403 or 404.
func TestDebugEndpointsReturn403UnderDefaultConfig(t *testing.T) {
	t.Skip("not implemented")
}

// TestGameEndpointAcceptsValidCommand sends a well-formed POST /command with
// a game verb and asserts the response is 2xx.
func TestGameEndpointAcceptsValidCommand(t *testing.T) {
	t.Skip("not implemented")
}

// TestPuzzleAttemptIsThreadSafe launches concurrent goroutines all sending an
// attempt to the same puzzle and verifies serialization (3 evaluated,
// no_attempts >= 95, evaluated + no_attempts <= 100).
func TestPuzzleAttemptIsThreadSafe(t *testing.T) {
	t.Skip("not implemented")
}

// TestModeratorEndpointsRequireHMAC verifies that moderator verbs are rejected
// without a correct X-Moderator-Signature header.
func TestModeratorEndpointsRequireHMAC(t *testing.T) {
	t.Skip("not implemented")
}

// TestAdminEndpointRejectsReplay verifies that reusing the same admin nonce
// returns 403 on the second request.
func TestAdminEndpointRejectsReplay(t *testing.T) {
	t.Skip("not implemented")
}

// postJSON is a convenience helper that sends a POST request with a JSON body.
func postJSON(baseURL, path string, body []byte) (*http.Response, error) {
	url := baseURL + path
	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	return http.DefaultClient.Do(req)
}

// mustMarshal encodes v to JSON and panics on error (test-only helper).
func mustMarshal(v any) []byte {
	b, err := json.Marshal(v)
	if err != nil {
		panic(err)
	}
	return b
}
