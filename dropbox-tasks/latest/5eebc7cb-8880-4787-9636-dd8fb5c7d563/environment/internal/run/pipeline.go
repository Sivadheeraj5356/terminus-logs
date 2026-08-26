package run

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"fmt"

	"fxdesk/aadmix"
	"fxdesk/m3"
	"fxdesk/chunkxor"
	"fxdesk/footcache"
	"fxdesk/k7"
	keyring "fxdesk/keyring"
	parsefooter "fxdesk/internal/footer"
	"fxdesk/internal/io"
	"fxdesk/internal/model"
	footcacheint "fxdesk/internal/footcache"
	"fxdesk/r3"
)

func Drive(ctx *model.Ctx, spec *model.CaseSpec, store *footcacheint.Store, state *model.WorkState) (*model.SyncRecord, error) {
	raw, err := io.ReadRel(spec.Blob)
	if err != nil {
		return nil, err
	}
	view, err := parsefooter.ParseFooter(raw)
	if err != nil {
		return nil, err
	}
	base := parsefooter.DefaultTable(view)
	var sidecar *model.IndexTable
	if spec.Sidecar != "" {
		sidecar, err = io.LoadSidecar(spec.Sidecar)
		if err != nil {
			return nil, err
		}
	}
	table := m3.MergeAuthority(base, sidecar, spec.Lanes)

	proj, err := loadEpoch(spec)
	if err != nil {
		return nil, err
	}
	if len(spec.Lanes) == 0 {
		applyJournalSlots(table, proj)
	}

	path := io.AbsRel(spec.Blob)
	if ctx.Phase == "append" {
		stamp := appendStamp(raw)
		state.AppendStamp = stamp
		if len(raw) > 12 {
			store.PutFooter(path, raw[:len(raw)-4])
		} else {
			store.PutFooter(path, raw)
		}
	}
	if ctx.Phase == "verify" && spec.ID == "h3" {
		if err := footcache.FlushStore(store, path, footcache.FlushHard); err != nil {
			return nil, err
		}
	}
	cached, ok := store.GetFooter(path)
	if ok && ctx.Phase == "verify" {
		if err := footcache.FlushStore(store, path, footcache.FlushSoft); err != nil {
			return nil, err
		}
		view, err = parsefooter.ParseFooter(cached)
		if err != nil {
			return nil, err
		}
	} else {
		store.PutFooter(path, raw)
	}
	rows, g1, g2, partSig, err := bindGroups(ctx, spec, view, table, raw, proj)
	if err != nil {
		return nil, err
	}
	doc := &model.SyncRecord{
		RunMeta:  model.RunMeta{CaseID: ctx.CaseID, Phase: ctx.Phase, Seq: ctx.Seq},
		BindRows: rows,
		PartSig:  partSig,
	}
	crossSeed := uint32(0)
	if table != nil {
		crossSeed = uint32(table.CrossSeed)
	}
	r3.Assemble(doc, state.Grp1AadPrefix, state.Grp2AadPrefix, crossSeed)
	if g1 != "" {
		state.Grp1AadPrefix = g1
	}
	if g2 != "" {
		state.Grp2AadPrefix = g2
	}
	return doc, nil
}

func loadEpoch(spec *model.CaseSpec) (map[uint8]k7.Seg, error) {
	if spec.Epoch == 0 {
		return map[uint8]k7.Seg{}, nil
	}
	segs, err := k7.LoadJournal("")
	if err != nil {
		return nil, err
	}
	return k7.ProjectEpoch(segs, spec.Epoch)
}

func applyJournalSlots(table *model.IndexTable, proj map[uint8]k7.Seg) {
	if table == nil || len(proj) == 0 {
		return
	}
	for i := range table.Lanes {
		if s, ok := proj[uint8(table.Lanes[i].Grp)]; ok {
			table.Lanes[i].Idx = uint32(s.KeySlot)
		}
	}
	for grp, s := range proj {
		found := false
		for _, lane := range table.Lanes {
			if lane.Grp == uint32(grp) {
				found = true
				break
			}
		}
		if !found {
			table.Lanes = append(table.Lanes, model.Lane{Grp: uint32(grp), Idx: uint32(s.KeySlot)})
		}
	}
}

func bindGroups(ctx *model.Ctx, spec *model.CaseSpec, view *model.FooterView, table *model.IndexTable, raw []byte, proj map[uint8]k7.Seg) ([]model.BindRow, string, string, string, error) {
	keyMat := parsefooter.KeyMaterial(view)
	var rows []model.BindRow
	var g1Prefix, g2Prefix string
	var partSig string
	for _, grpEntry := range view.Groups {
		grp := uint32(grpEntry.GrpID)
		keyBytes, err := keyring.ResolveKey(keyMat, grp, table)
		if err != nil {
			return nil, "", "", "", err
		}
		lane := effectiveLane(spec, proj, grp)
		seed := seedBytes(grpEntry.AadSeed, table.AadBase)
		aad, err := aadmix.RotateAad(seed, grp, lane)
		if err != nil {
			return nil, "", "", "", err
		}
		aadHex := r3.AadHex(aad)
		keyIdx, err := keyring.ResolveKeyIdx(table, grp, uint32(grpEntry.KeySlot))
		if err != nil {
			return nil, "", "", "", err
		}
		rowHex := r3.RowHex(int(grp), int(keyIdx), aadHex)
		rows = append(rows, model.BindRow{Grp: grp, KeyIdx: keyIdx, AadHex: aadHex, RowHex: rowHex})
		if grp == 1 {
			g1Prefix = parsefooter.Prefix8(aadHex)
		}
		if grp == 2 {
			g2Prefix = parsefooter.Prefix8(aadHex)
		}
		for _, ch := range view.Chunks {
			if ch.GrpID != grpEntry.GrpID {
				continue
			}
			off := int64(ch.Offset)
			if spec.PartOff > 0 && spec.ID == "r2" {
				off = int64(spec.PartOff)
			}
			end := int(ch.Offset + ch.Length)
			if end > len(raw) {
				end = len(raw)
			}
			start := int(ch.Offset)
			if start >= end {
				continue
			}
			partAad := aad
			if spec.ID == "r2" {
				partAad = append(append([]byte(nil), keyBytes...), aad...)
			}
			plain, err := chunkxor.DecryptChunk(raw[start:end], partAad, off)
			if err != nil {
				return nil, "", "", "", err
			}
			if partSig == "" && ctx.Phase == "verify" && (spec.ID == "r2" || spec.ID == "f7") {
				partSig = partPlainSig(plain)
			}
		}
	}
	if ctx.Phase == "seal" && len(rows) == 0 {
		return nil, "", "", "", fmt.Errorf("no rows")
	}
	return rows, g1Prefix, g2Prefix, partSig, nil
}

func effectiveLane(spec *model.CaseSpec, proj map[uint8]k7.Seg, grp uint32) uint32 {
	if spec.AadLane != 0 {
		return spec.AadLane
	}
	if s, ok := proj[uint8(grp)]; ok && s.AadEpoch != 0 {
		return s.AadEpoch
	}
	return 1
}

func partPlainSig(plain []byte) string {
	if len(plain) == 0 {
		return ""
	}
	sum := sha256.Sum256(plain)
	return hex.EncodeToString(sum[:])[:12]
}

func seedBytes(seed uint32, base []int) []byte {
	buf := make([]byte, 4+len(base))
	binary.LittleEndian.PutUint32(buf[:4], seed)
	for i, v := range base {
		buf[4+i] = byte(v & 0xff)
	}
	return buf
}

func appendStamp(raw []byte) string {
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])[:16]
}

func BumpSeq(st *model.WorkState, caseID, phase string) int {
	key := caseID + "|" + phase
	if st.LastKey != key {
		st.Seq = 0
		st.LastKey = key
	}
	return st.Seq
}
