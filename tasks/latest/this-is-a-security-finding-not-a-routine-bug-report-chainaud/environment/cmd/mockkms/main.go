// mockkms is a stand-in for the checkpoint-signing key service. It serves a
// fixed table of key material over HTTP, answers 410 Gone for keys that have
// been rotated out, and rate-limits the first few requests for any given key
// with 429 so a caller must implement real retry/backoff to get anywhere.
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"
	"time"
)

type keyRecord struct {
	Material        []byte
	Revoked         bool
	AlwaysThrottled bool // never resolves past 429; simulates a genuinely degraded KMS, not just a flaky one
}

func derive(keyID string) []byte {
	h := sha256.Sum256([]byte("CHAINAUDIT-MOCKKMS-KEY-MATERIAL-v1:" + keyID))
	return h[:]
}

var keyTable = map[string]keyRecord{
	"key-2022-11":            {Material: derive("key-2022-11"), Revoked: true},
	"key-2023-05":            {Material: derive("key-2023-05"), Revoked: true},
	"key-2024-02":            {Material: derive("key-2024-02"), Revoked: false},
	"key-2024-11":            {Material: derive("key-2024-11"), Revoked: false},
	"key-2024-12-degraded":   {Material: derive("key-2024-12-degraded"), AlwaysThrottled: true},
}

const flakyAttempts = 2

var (
	mu        sync.Mutex
	seenCount = map[string]int{}
)

func main() {
	addr := os.Getenv("MOCKKMS_ADDR")
	if addr == "" {
		addr = "127.0.0.1:8500"
	}
	logPath := os.Getenv("MOCKKMS_LOG")
	if logPath == "" {
		logPath = "/app/data/kms_access.log"
	}

	logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		log.Fatalf("mockkms: cannot open access log %s: %v", logPath, err)
	}
	defer logFile.Close()
	var logMu sync.Mutex

	http.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	http.HandleFunc("/v1/keys/", func(w http.ResponseWriter, r *http.Request) {
		keyID := r.URL.Path[len("/v1/keys/"):]

		mu.Lock()
		seenCount[keyID]++
		attempt := seenCount[keyID]
		mu.Unlock()

		rec, known := keyTable[keyID]

		var status int
		switch {
		case !known:
			status = http.StatusNotFound
		case rec.AlwaysThrottled:
			status = http.StatusTooManyRequests
		case attempt <= flakyAttempts:
			status = http.StatusTooManyRequests
		case rec.Revoked:
			status = http.StatusGone
		default:
			status = http.StatusOK
		}

		logMu.Lock()
		entry, _ := json.Marshal(map[string]interface{}{
			"ts":      time.Now().UnixMilli(),
			"key_id":  keyID,
			"status":  status,
			"attempt": attempt,
		})
		logFile.Write(append(entry, '\n'))
		logMu.Unlock()

		switch status {
		case http.StatusNotFound:
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusNotFound)
			fmt.Fprintf(w, `{"error":"not_found","key_id":%q}`, keyID)
		case http.StatusTooManyRequests:
			w.Header().Set("Retry-After", "0")
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusTooManyRequests)
			fmt.Fprintf(w, `{"error":"rate_limited","key_id":%q}`, keyID)
		case http.StatusGone:
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusGone)
			fmt.Fprintf(w, `{"error":"revoked","key_id":%q}`, keyID)
		case http.StatusOK:
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]string{
				"key_id":           keyID,
				"key_material_hex": hex.EncodeToString(rec.Material),
			})
		}
	})

	log.Printf("mockkms listening on %s (log: %s)", addr, logPath)
	log.Fatal(http.ListenAndServe(addr, nil))
}
