package main

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"os"
	"sync"

	"github.com/gin-gonic/gin"
)

type Roster struct {
	ProfileID   string   `json:"profile_id"`
	Epoch       int      `json:"epoch"`
	SigningAlg  string   `json:"signing_alg"`
	AllowedAlgs []string `json:"allowed_algs"`
}

var (
	mu     sync.Mutex
	keys   = map[string]bool{}
	roster Roster
)

func loadRoster() {
	path := "/app/fixtures/profiles/roster.json"
	if v := os.Getenv("REELSEAL_ROSTER"); v != "" {
		path = v
	}
	b, err := os.ReadFile(path)
	if err != nil {
		roster = Roster{ProfileID: "reel-std", Epoch: 7, SigningAlg: "Ed25519", AllowedAlgs: []string{"Ed25519"}}
		return
	}
	_ = json.Unmarshal(b, &roster)
}

func main() {
	loadRoster()
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"ok": true, "engine": "reelseal-runtime/v1"})
	})
	r.POST("/v1/profiles/resolve", resolve)
	r.POST("/v1/keys/issue", issue)
	r.POST("/v1/attest/release", attest)
	addr := ":8742"
	if v := os.Getenv("REELSEAL_API_ADDR"); v != "" {
		addr = v
	}
	_ = r.Run(addr)
}

func resolve(c *gin.Context) {
	var req struct {
		ProfileID     string `json:"profile_id"`
		ExpectedEpoch int    `json:"expected_epoch"`
	}
	if err := c.BindJSON(&req); err != nil {
		c.JSON(400, gin.H{"error": "bad json"})
		return
	}
	if req.ProfileID != "" && req.ProfileID != roster.ProfileID {
		c.JSON(404, gin.H{"error": "unknown profile"})
		return
	}
	if req.ExpectedEpoch != roster.Epoch {
		c.JSON(http.StatusConflict, gin.H{"error": "epoch_skew", "epoch": roster.Epoch})
		return
	}
	c.JSON(200, gin.H{
		"profile_id":   roster.ProfileID,
		"epoch":        roster.Epoch,
		"signing_alg":  roster.SigningAlg,
		"allowed_algs": roster.AllowedAlgs,
	})
}

func issue(c *gin.Context) {
	var req struct {
		ProfileID   string `json:"profile_id"`
		MediaDigest string `json:"media_digest"`
		Purpose     string `json:"purpose"`
	}
	if err := c.BindJSON(&req); err != nil {
		c.JSON(400, gin.H{"error": "bad json"})
		return
	}
	if req.MediaDigest == "" || req.Purpose != "hls-aes128" {
		c.JSON(400, gin.H{"error": "bad issue request"})
		return
	}
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	kid := "rk-" + hex.EncodeToString(b)
	mu.Lock()
	keys[kid] = true
	mu.Unlock()
	c.JSON(200, gin.H{
		"key_id":        kid,
		"key_urn":       "urn:reelseal:key:" + kid,
		"profile_epoch": roster.Epoch,
	})
}

func attest(c *gin.Context) {
	var req struct {
		KeyID          string `json:"key_id"`
		MediaDigest    string `json:"media_digest"`
		PlaylistDigest string `json:"playlist_digest"`
		PolicyDigest   string `json:"policy_digest"`
		ManifestDigest string `json:"manifest_digest"`
		ReleaseTag     string `json:"release_tag"`
	}
	if err := c.BindJSON(&req); err != nil {
		c.JSON(400, gin.H{"error": "bad json"})
		return
	}
	if req.KeyID == "" || req.MediaDigest == "" || req.PlaylistDigest == "" || req.PolicyDigest == "" || req.ManifestDigest == "" {
		c.JSON(400, gin.H{"error": "missing digest fields"})
		return
	}
	mu.Lock()
	ok := keys[req.KeyID]
	mu.Unlock()
	if !ok {
		c.JSON(400, gin.H{"error": "unknown key_id"})
		return
	}
	id := make([]byte, 6)
	_, _ = rand.Read(id)
	c.JSON(200, gin.H{"attest_id": "att-" + hex.EncodeToString(id), "bound": true, "engine": "reelseal-runtime/v1"})
}
