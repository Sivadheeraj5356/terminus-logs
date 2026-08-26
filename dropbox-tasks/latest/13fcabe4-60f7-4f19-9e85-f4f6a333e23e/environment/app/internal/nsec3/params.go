package nsec3

import (
	"crypto/sha256"
	"encoding/hex"
	"math/rand"
	"time"

	"zonepub/internal/config"
	"zonepub/internal/manifest"
)

type Params struct {
	Algorithm  uint8
	Flags      uint8
	Iterations uint16
	Salt       string
}

func FromPolicy(cfg *config.Config, planID string) Params {
	seed := cfg.NSEC3.SaltSeed + "|" + planID
	h := sha256.Sum256([]byte(seed))
	salt := hex.EncodeToString(h[:8])
	return Params{
		Algorithm:  cfg.NSEC3.Algorithm,
		Flags:      cfg.NSEC3.Flags,
		Iterations: cfg.NSEC3.Iterations,
		Salt:       salt,
	}
}

func newSalt() string {
	rng := rand.New(rand.NewSource(time.Now().UnixNano()))
	buf := make([]byte, 8)
	rng.Read(buf)
	return hex.EncodeToString(buf)
}

// Select chooses NSEC3 parameters for publication or recovery.
func Select(cfg *config.Config, planID string, recovered *manifest.Document, commit *manifest.CommitRecord) Params {
	if commit != nil && commit.NSEC3.Salt != "" {
		return Params{
			Algorithm:  commit.NSEC3.Algorithm,
			Flags:      commit.NSEC3.Flags,
			Iterations: commit.NSEC3.Iterations,
			Salt:       commit.NSEC3.Salt,
		}
	}
	if recovered != nil && recovered.NSEC3.Salt != "" {
		return Params{
			Algorithm:  recovered.NSEC3.Algorithm,
			Flags:      recovered.NSEC3.Flags,
			Iterations: recovered.NSEC3.Iterations,
			Salt:       recovered.NSEC3.Salt,
		}
	}
	if commit != nil {
		p := FromPolicy(cfg, planID)
		p.Salt = newSalt()
		return p
	}
	return FromPolicy(cfg, planID)
}

func (p Params) SaltFlag() string {
	if p.Salt == "-" || p.Salt == "" {
		return "-"
	}
	return p.Salt
}

func (p Params) SignzoneArg() string {
	return ""
}
