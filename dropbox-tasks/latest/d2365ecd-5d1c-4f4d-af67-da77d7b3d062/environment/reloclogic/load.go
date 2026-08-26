package reloclogic

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// Mapping is one relocation rule.
type Mapping struct {
	Seq        int    `json:"seq"`
	FromPrefix string `json:"from_prefix"`
	ToPrefix   string `json:"to_prefix"`
	Priority   int    `json:"priority"`
}

// SymbolDecl is a class-like symbol inside a unit.
type SymbolDecl struct {
	FQN     string `json:"fqn"`
	PkgPath string `json:"pkg_path"`
}

// RefDecl is a string reference that must be rewritten.
type RefDecl struct {
	ID      string `json:"id"`
	Literal string `json:"literal"`
	Kind    string `json:"kind"`
}

// ResourceDecl is a resource entry with a relocatable content ref.
type ResourceDecl struct {
	Path       string `json:"path"`
	ContentRef string `json:"content_ref"`
}

// Unit is one archive or nested archive fragment.
type Unit struct {
	Path     string         `json:"path"`
	Root     string         `json:"root"`
	Symbols  []SymbolDecl   `json:"symbols"`
	Refs     []RefDecl      `json:"refs"`
	Resources []ResourceDecl `json:"resources"`
	Nested   []Unit         `json:"nested"`
}

// Step is a transformation step for digest simulation.
type Step struct {
	Seq      int    `json:"seq"`
	Op       string `json:"op"`
	Fail     bool   `json:"fail"`
	Rollback bool   `json:"rollback"`
}

// Schedule is one replay mapping subset.
type Schedule struct {
	ScheduleID      string `json:"schedule_id"`
	MappingSeqOrder []int  `json:"mapping_seq_order"`
}

// ReplayBlock optional replay section.
type ReplayBlock struct {
	Schedules []Schedule `json:"schedules"`
}

// ObservedSymbol is a post-transform symbol observation.
type ObservedSymbol struct {
	Original string `json:"original"`
	FQN      string `json:"fqn"`
	PkgPath  string `json:"pkg_path"`
}

// ObservedRef is a post-transform reference observation.
type ObservedRef struct {
	ID      string `json:"id"`
	Literal string `json:"literal"`
}

// ObservedResource is a post-transform resource observation.
type ObservedResource struct {
	Path       string `json:"path"`
	ContentRef string `json:"content_ref"`
}

// ObservedNested is nested observations keyed by unit path.
type ObservedNested struct {
	UnitPath string           `json:"unit_path"`
	Symbols  []ObservedSymbol `json:"symbols"`
	Refs     []ObservedRef    `json:"refs"`
}

// ObservedBlock is the observed transformed state.
type ObservedBlock struct {
	Symbols       []ObservedSymbol   `json:"symbols"`
	Refs          []ObservedRef      `json:"refs"`
	Resources     []ObservedResource `json:"resources"`
	Identity      struct {
		Group    string `json:"group"`
		Artifact string `json:"artifact"`
		Version  string `json:"version"`
	} `json:"identity"`
	Metadata struct {
		RelocatorEpoch int `json:"relocator_epoch"`
	} `json:"metadata"`
	Digest         string           `json:"digest"`
	NestedApplied  bool             `json:"nested_applied"`
	Nested         []ObservedNested `json:"nested"`
}

// BatchFile is the on-disk batch payload.
type BatchFile struct {
	BatchID          string `json:"batch_id"`
	PreserveIdentity bool   `json:"preserve_identity"`
	Identity         struct {
		Group    string `json:"group"`
		Artifact string `json:"artifact"`
		Version  string `json:"version"`
	} `json:"identity"`
	Mappings []Mapping       `json:"mappings"`
	Units    []Unit          `json:"units"`
	Steps    []Step          `json:"steps"`
	Observed ObservedBlock   `json:"observed"`
	Replay   *ReplayBlock    `json:"replay,omitempty"`
}

// LoadPolicy reads the shipped YAML using fixed defaults matching rules.yaml.
func LoadPolicy(path string) (Policy, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Policy{}, err
	}
	text := string(raw)
	checks := []string{
		"chain_relocations: false",
		"cascade_nested: true",
		"forbid_cross_root_merge: true",
		"required_relocator_epoch: 7",
		"prefix_stable_on_findings: true",
		"full_unstable_on_findings: true",
		"detect_shadowed_mappings: true",
		"cascade_gap_suppresses_nested: true",
		"digest_bind_active_maps: true",
		"collision_top_level_only: true",
		"check_resource_rewrites: true",
		"digest_bind_resources: true",
		"preserve_identity_version: true",
		"digest_bind_effective_maps: true",
		"replay_skips_digest: true",
		"detect_dangling_observations: true",
		"digest_map_bind_order_seq: true",
		"relocator_epoch_must_equal: true",
		"orphan_requires_payload: true",
		"digest_exclude_cycle_maps: true",
		"replay_ignore_unknown_seqs: true",
		"detect_dangling_nested: true",
	}
	for _, c := range checks {
		if !strings.Contains(text, c) {
			return Policy{}, fmt.Errorf("policy missing %s", c)
		}
	}
	p := Policy{}
	p.Ordering.PrimaryKey = "priority"
	p.Ordering.SecondaryKey = "from_prefix"
	p.ChainRelocations = false
	p.CascadeNested = true
	p.ForbidCrossRootMerge = true
	p.RequiredRelocatorEpoch = 7
	p.PrefixStableOnFindings = true
	p.FullUnstableOnFindings = true
	p.DetectShadowedMappings = true
	p.CascadeGapSuppressesNested = true
	p.DigestBindActiveMaps = true
	p.CollisionTopLevelOnly = true
	p.CheckResourceRewrites = true
	p.DigestBindResources = true
	p.PreserveIdentityVersion = true
	p.DigestBindEffectiveMaps = true
	p.ReplaySkipsDigest = true
	p.DetectDanglingObservations = true
	p.DigestMapBindOrderSeq = true
	p.RequireExactRelocatorEpoch = true
	p.OrphanRequiresPayload = true
	p.DigestExcludeCycleMaps = true
	p.ReplayIgnoreUnknownSeqs = true
	p.DetectDanglingNested = true
	return p, nil
}

// LoadBatches loads batch_01.json through batch_20.json from dir.
func LoadBatches(dir string) ([]BatchFile, error) {
	out := make([]BatchFile, 0, 20)
	for i := 1; i <= 20; i++ {
		name := fmt.Sprintf("batch_%02d.json", i)
		path := filepath.Join(dir, name)
		b, err := os.ReadFile(path)
		if err != nil {
			return nil, err
		}
		var bf BatchFile
		if err := json.Unmarshal(b, &bf); err != nil {
			return nil, fmt.Errorf("%s: %w", name, err)
		}
		want := fmt.Sprintf("batch_%02d", i)
		if bf.BatchID != want {
			return nil, fmt.Errorf("%s: batch_id %q != %q", name, bf.BatchID, want)
		}
		out = append(out, bf)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].BatchID < out[j].BatchID })
	return out, nil
}
