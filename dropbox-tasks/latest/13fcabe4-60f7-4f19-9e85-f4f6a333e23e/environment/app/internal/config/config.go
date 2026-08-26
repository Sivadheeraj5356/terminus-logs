package config

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/BurntSushi/toml"
)

type NSEC3Policy struct {
	Algorithm  uint8  `toml:"algorithm"`
	Flags      uint8  `toml:"flags"`
	Iterations uint16 `toml:"iterations"`
	SaltSeed   string `toml:"salt_seed"`
}

type Config struct {
	Origin            string      `toml:"origin"`
	UnsignedZone      string      `toml:"unsigned_zone"`
	Inventory         string      `toml:"inventory"`
	Journal           string      `toml:"journal"`
	PreviousDir       string      `toml:"previous_dir"`
	KeysDir           string      `toml:"keys_dir"`
	SignedOutputName  string      `toml:"signed_output_name"`
	ManifestName      string      `toml:"manifest_name"`
	SignatureLifetime int64       `toml:"signature_lifetime"`
	Epoch             int64       `toml:"epoch"`
	NSEC3             NSEC3Policy `toml:"nsec3"`
	Workspace         string      `toml:"-"`
}

func LoadWorkspace(workspace string) (*Config, error) {
	path := filepath.Join(workspace, "publish.toml")
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var cfg Config
	if _, err := toml.Decode(string(data), &cfg); err != nil {
		return nil, err
	}
	cfg.Workspace = workspace
	if cfg.UnsignedZone == "" {
		cfg.UnsignedZone = "unsigned.zone"
	}
	if cfg.Inventory == "" {
		cfg.Inventory = "inventory.json"
	}
	if cfg.Journal == "" {
		cfg.Journal = "release-log.jsonl"
	}
	if cfg.PreviousDir == "" {
		cfg.PreviousDir = "previous"
	}
	if cfg.KeysDir == "" {
		cfg.KeysDir = "keys"
	}
	if cfg.SignedOutputName == "" {
		cfg.SignedOutputName = cfg.Origin + ".signed"
	}
	if cfg.ManifestName == "" {
		cfg.ManifestName = "publication-manifest.json"
	}
	if cfg.SignatureLifetime == 0 {
		cfg.SignatureLifetime = 86400 * 30
	}
	if cfg.NSEC3.Algorithm == 0 {
		cfg.NSEC3.Algorithm = 2
	}
	if cfg.NSEC3.Iterations == 0 {
		cfg.NSEC3.Iterations = 0
	}
	if cfg.Origin == "" {
		return nil, fmt.Errorf("origin required")
	}
	return &cfg, nil
}

func (c *Config) Abs(rel string) string {
	if filepath.IsAbs(rel) {
		return rel
	}
	return filepath.Join(c.Workspace, rel)
}

func (c *Config) UnsignedPath() string  { return c.Abs(c.UnsignedZone) }
func (c *Config) InventoryPath() string { return c.Abs(c.Inventory) }
func (c *Config) JournalPath() string   { return c.Abs(c.Journal) }
func (c *Config) KeysPath() string      { return c.Abs(c.KeysDir) }
func (c *Config) PreviousSigned() string {
	return filepath.Join(c.Abs(c.PreviousDir), c.SignedOutputName)
}
func (c *Config) PreviousManifest() string {
	return filepath.Join(c.Abs(c.PreviousDir), c.ManifestName)
}
func (c *Config) StagingRoot() string { return filepath.Join(c.Workspace, "staging") }
