package publication

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"path/filepath"
	"sort"

	"zonepub/internal/config"
	"zonepub/internal/dnszone"
	"zonepub/internal/fsutil"
	"zonepub/internal/journal"
	"zonepub/internal/keys"
	"zonepub/internal/manifest"
	"zonepub/internal/nsec3"
	"zonepub/internal/rollover"
	"zonepub/internal/serial"
)

type Plan struct {
	EpochID        string
	Origin         string
	Epoch          int64
	InputDigest    string
	PlanDigest     string
	Serial         uint32
	NSEC3          nsec3.Params
	SignatureStart int64
	SignatureEnd   int64
	Keys           []manifest.KeyMeta
	SigningKeys    []string
	Changed        bool
}

type Publisher struct {
	cfg       *config.Config
	workspace string
	outputDir string
}

func NewPublisher(cfg *config.Config, workspace, outputDir string) *Publisher {
	return &Publisher{cfg: cfg, workspace: workspace, outputDir: outputDir}
}

func (p *Publisher) Publish() (int, error) {
	records, err := journal.ReadAll(p.cfg.JournalPath())
	if err != nil {
		return 3, err
	}
	decision, _ := journal.Classify(journal.RecoveryContext{
		Workspace: p.workspace,
		OutputDir: p.outputDir,
		Records:   records,
	})
	inv, err := keys.LoadInventory(p.cfg.InventoryPath(), p.cfg.KeysPath())
	if err != nil {
		return 3, fmt.Errorf("inventory: %w", err)
	}
	zone, err := dnszone.ParseFile(p.cfg.Origin, p.cfg.UnsignedPath())
	if err != nil {
		return 3, fmt.Errorf("zone: %w", err)
	}
	inputDigest, err := fsutil.DigestFile(p.cfg.UnsignedPath())
	if err != nil {
		return 3, err
	}
	var previous *manifest.Document
	if fsutil.Exists(p.cfg.PreviousManifest()) {
		previous, _ = manifest.ReadDocument(p.cfg.PreviousManifest())
	}
	var snap *manifest.SnapshotV1
	snapPath := filepath.Join(p.workspace, "operator-snapshot-v1.json")
	if fsutil.Exists(snapPath) {
		snap, _ = rollover.LoadSnapshot(snapPath)
	}
	var journalKeys []manifest.JournalKeyState
	for _, r := range records {
		if r.Phase == journal.PhaseAccepted {
			journalKeys = r.Keys
		}
	}
	model := rollover.Reconcile(rollover.Inputs{
		Inventory: inv,
		Journal:   journalKeys,
		Previous:  previous,
		Snapshot:  snap,
	})
	plan, err := p.buildPlan(zone, inputDigest, model, inv, previous, records, decision)
	if err != nil {
		return 3, err
	}
	stagingDir := filepath.Join(p.cfg.StagingRoot(), "pending-epoch")
	if err := Stage(p.cfg, plan, zone, stagingDir, inv); err != nil {
		return 4, fmt.Errorf("stage: %w", err)
	}
	if err := Commit(p.cfg, plan, stagingDir, p.outputDir, records); err != nil {
		return 6, fmt.Errorf("commit: %w", err)
	}
	return 0, nil
}

func (p *Publisher) buildPlan(zone *dnszone.Zone, inputDigest string, model *rollover.Model, inv *keys.Inventory, previous *manifest.Document, records []journal.Record, decision journal.RecoveryDecision) (*Plan, error) {
	candidateSerial, err := dnszone.SOASerial(zone)
	if err != nil {
		return nil, err
	}
	prevSerial := uint32(1)
	changed := true
	if previous != nil {
		prevSerial = previous.Serial
		if previous.InputDigest == inputDigest && previous.Epoch == p.cfg.Epoch {
			changed = false
		}
	}
	allocSerial := serial.Allocate(candidateSerial, prevSerial, changed)
	epochID := decision.ResumeEpoch
	if epochID == "" {
		epochID = hashID(inputDigest, p.cfg.Epoch)
	}
	commit, _ := journal.LoadCommitRecord(filepath.Join(p.cfg.StagingRoot(), "pending-epoch"))
	nsec := nsec3.Select(p.cfg, epochID, previous, commit)
	start := p.cfg.Epoch
	end := p.cfg.Epoch + p.cfg.SignatureLifetime
	var keyMetas []manifest.KeyMeta
	var signFiles []string
	for _, e := range inv.Keys {
		dk, err := keys.ParseDNSKEY(e)
		if err != nil {
			continue
		}
		lid := keys.DurableID(dk)
		st, ok := model.Get(lid)
		status := e.Status
		if ok {
			status = st.Status
		}
		if rollover.Terminal(status) {
			continue
		}
		if status == keys.StatusActive || status == keys.StatusPublished || status == keys.StatusRetiring {
			keyMetas = append(keyMetas, manifest.KeyMeta{
				LineageID: lid,
				Role:      string(e.Role),
				Status:    string(status),
				KeyTag:    e.KeyTag,
				Algorithm: e.Algorithm,
				PublicKey: e.PublicKey,
			})
			signFiles = append(signFiles, e.PrivatePath)
		}
	}
	sort.Strings(signFiles)
	plan := &Plan{
		EpochID:        epochID,
		Origin:         p.cfg.Origin,
		Epoch:          p.cfg.Epoch,
		InputDigest:    inputDigest,
		Serial:         allocSerial,
		NSEC3:          nsec,
		SignatureStart: start,
		SignatureEnd:   end,
		Keys:           keyMetas,
		SigningKeys:    signFiles,
		Changed:        changed,
	}
	plan.PlanDigest = digestPlan(plan)
	return plan, nil
}

func digestPlan(plan *Plan) string {
	b, _ := json.Marshal(plan)
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func hashID(input string, epoch int64) string {
	h := sha256.Sum256([]byte(fmt.Sprintf("%s|%d", input, epoch)))
	return hex.EncodeToString(h[:8])
}
