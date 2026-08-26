// Package kms is a client for the checkpoint-signing key service. Keys
// rotate over time; old ones are not deleted, they are revoked, and the
// service answers a revoked key with 410 Gone rather than treating it as an
// ordinary failure. The service also rate-limits: callers must retry 429
// responses with backoff rather than fail immediately or hammer it in a tight
// loop.
package kms

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math/rand"
	"net/http"
	"time"
)

type KeyStatus int

const (
	KeyActive KeyStatus = iota
	KeyRevoked
)

type Key struct {
	KeyID    string
	Material []byte
	Status   KeyStatus
}

type Client struct {
	BaseURL     string
	HTTPClient  *http.Client
	MaxAttempts int
	BaseDelay   time.Duration
}

func NewClient(baseURL string) *Client {
	return &Client{
		BaseURL:     baseURL,
		HTTPClient:  &http.Client{Timeout: 5 * time.Second},
		MaxAttempts: 6,
		BaseDelay:   50 * time.Millisecond,
	}
}

// FetchKey retrieves key material for keyID, retrying 429 responses with
// exponential backoff and jitter. A 410 is not an error: it means the key was
// intentionally rotated out, and the caller gets a KeyRevoked result back
// instead of an error so it can tell that apart from a real failure.
func (c *Client) FetchKey(ctx context.Context, keyID string) (*Key, error) {
	url := c.BaseURL + "/v1/keys/" + keyID
	var lastErr error

	for attempt := 0; attempt < c.MaxAttempts; attempt++ {
		if attempt > 0 {
			delay := c.BaseDelay * time.Duration(int64(1)<<uint(attempt-1))
			jitter := time.Duration(rand.Int63n(int64(delay)/2 + 1))
			select {
			case <-time.After(delay + jitter):
			case <-ctx.Done():
				return nil, ctx.Err()
			}
		}

		key, retry, err := c.attempt(ctx, url, keyID)
		if err == nil {
			return key, nil
		}
		if !retry {
			return nil, err
		}
		lastErr = err
	}
	return nil, fmt.Errorf("kms: exhausted retries fetching key %s: %w", keyID, lastErr)
}

// attempt makes one HTTP call. The bool return says whether the caller should
// retry: true for a transient condition (429, network error), false for a
// definitive result (200, 410) or a non-retryable failure.
func (c *Client) attempt(ctx context.Context, url, keyID string) (*Key, bool, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, false, err
	}
	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, true, err
	}
	defer resp.Body.Close()

	switch resp.StatusCode {
	case http.StatusOK:
		var body struct {
			KeyID          string `json:"key_id"`
			KeyMaterialHex string `json:"key_material_hex"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
			return nil, false, err
		}
		material, err := hex.DecodeString(body.KeyMaterialHex)
		if err != nil {
			return nil, false, err
		}
		return &Key{KeyID: body.KeyID, Material: material, Status: KeyActive}, false, nil
	case http.StatusGone:
		return &Key{KeyID: keyID, Status: KeyRevoked}, false, nil
	case http.StatusTooManyRequests:
		return nil, true, fmt.Errorf("kms: rate limited fetching key %s", keyID)
	default:
		return nil, false, fmt.Errorf("kms: unexpected status %d fetching key %s", resp.StatusCode, keyID)
	}
}
