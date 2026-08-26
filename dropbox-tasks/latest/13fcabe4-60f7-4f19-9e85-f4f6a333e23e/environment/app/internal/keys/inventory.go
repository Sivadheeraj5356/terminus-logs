package keys

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/miekg/dns"
)

type Role string

const (
	RoleKSK Role = "KSK"
	RoleZSK Role = "ZSK"
)

type Status string

const (
	StatusIntroduced Status = "introduced"
	StatusPublished  Status = "published"
	StatusActive     Status = "active"
	StatusRetiring   Status = "retiring"
	StatusRetired    Status = "retired"
	StatusRevoked    Status = "revoked"
)

type Entry struct {
	ID           string `json:"id"`
	Role         Role   `json:"role"`
	Status       Status `json:"status"`
	Algorithm    uint8  `json:"algorithm"`
	Flags        uint16 `json:"flags"`
	PublicKey    string `json:"public_key_b64"`
	PrivatePath  string `json:"private_key_path"`
	KeyTag       uint16 `json:"key_tag"`
	LineageHint  string `json:"lineage_id,omitempty"`
}

type Inventory struct {
	Origin  string  `json:"origin"`
	Keys    []Entry `json:"keys"`
	keysDir string
}

func LoadInventory(path, keysDir string) (*Inventory, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var inv Inventory
	if err := json.Unmarshal(data, &inv); err != nil {
		return nil, err
	}
	inv.keysDir = keysDir
	sort.Slice(inv.Keys, func(i, j int) bool {
		return inv.Keys[i].ID < inv.Keys[j].ID
	})
	for i := range inv.Keys {
		e := &inv.Keys[i]
		if e.KeyTag == 0 {
			rr, err := dns.NewRR(fmt.Sprintf(". 0 DNSKEY %d %d %d %s", e.Flags, 3, e.Algorithm, e.PublicKey))
			if err != nil {
				return nil, err
			}
			e.KeyTag = KeyTag(rr.(*dns.DNSKEY))
		}
		if !filepath.IsAbs(e.PrivatePath) {
			e.PrivatePath = filepath.Join(keysDir, e.PrivatePath)
		}
	}
	return &inv, nil
}

func (inv *Inventory) ByTag(tag uint16) []Entry {
	var out []Entry
	for _, k := range inv.Keys {
		if k.KeyTag == tag {
			out = append(out, k)
		}
	}
	return out
}

func (inv *Inventory) PrivateFiles() []string {
	var files []string
	for _, k := range inv.Keys {
		if k.Status == StatusActive || k.Status == StatusPublished || k.Status == StatusRetiring {
			files = append(files, k.PrivatePath)
		}
	}
	sort.Strings(files)
	return files
}

func ParseDNSKEY(e Entry) (*dns.DNSKEY, error) {
	rr, err := dns.NewRR(fmt.Sprintf(". 0 DNSKEY %d 3 %d %s", e.Flags, e.Algorithm, e.PublicKey))
	if err != nil {
		return nil, err
	}
	return rr.(*dns.DNSKEY), nil
}

func EntryFromDNSKEY(role Role, status Status, key *dns.DNSKEY, privatePath string) Entry {
	return Entry{
		ID:          fmt.Sprintf("key-%d", KeyTag(key)),
		Role:        role,
		Status:      status,
		Algorithm:   key.Algorithm,
		Flags:       key.Flags,
		PublicKey:   key.PublicKey,
		PrivatePath: privatePath,
		KeyTag:      KeyTag(key),
	}
}

func NormalizePublicKey(b64 string) string {
	return strings.TrimSpace(b64)
}
