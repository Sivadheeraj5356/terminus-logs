package main

import (
	"archive/tar"
	"bufio"
	"compress/gzip"
	"crypto/hmac"
	"crypto/sha256"
	"crypto/sha512"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path"
	"path/filepath"
	"sort"
	"strings"
	"syscall"
	"time"
)

const (
	minChunk = 3072
	maxChunk = 12288
	mask     = 0x1FFF
	zero64   = "0000000000000000000000000000000000000000000000000000000000000000"
)

func sha256Sum(b []byte) []byte {
	h := sha256.Sum256(b)
	return h[:]
}

func sha256Hex(b []byte) string { return hex.EncodeToString(sha256Sum(b)) }

func sha512_256Hex(b []byte) string {
	h := sha512.Sum512_256(b)
	return hex.EncodeToString(h[:])
}

func u32be(n uint32) []byte {
	return []byte{byte(n >> 24), byte(n >> 16), byte(n >> 8), byte(n)}
}

func must(err error) {
	if err != nil {
		panic(err)
	}
}

func writeJSON(path string, v any) {
	b, err := json.MarshalIndent(v, "", "  ")
	must(err)
	b = append(b, '\n')
	must(os.WriteFile(path, b, 0o644))
}

func compactJSON(v any) string {
	b, err := json.Marshal(v)
	must(err)
	return string(b)
}

type endpoints struct {
	URL    string `json:"policy_material_url"`
	SHA256 string `json:"policy_material_sha256"`
}

type manifestFile struct {
	Version int `json:"version"`
	Jobs    []struct {
		ID     string `json:"id"`
		Src    string `json:"src"`
		Config string `json:"config"`
	} `json:"jobs"`
}

type backupConfig struct {
	Exclude   []string `json:"exclude"`
	GzipLevel int      `json:"gzip_level"`
}

type policy struct {
	URL        string
	SHA256     string
	ByteLength int
	Domain     string
	GearSeed   []byte
	StoreSalt  []byte
	MacKey     []byte
	Gear       [256]uint32
}

type policyReceipt struct {
	URL               string `json:"url"`
	SHA256            string `json:"sha256"`
	ByteLength        int    `json:"byte_length"`
	AttestationDomain string `json:"attestation_domain"`
	GearSeedHex       string `json:"gear_seed_hex"`
	StoreSaltHex      string `json:"store_salt_hex"`
	MacKeyHex         string `json:"mac_key_hex"`
}

type reportRow struct {
	JobID        string `json:"job_id"`
	Status       string `json:"status"`
	FileCount    any    `json:"file_count"`
	ByteCount    any    `json:"byte_count"`
	ChunkCount   any    `json:"chunk_count"`
	UniqueChunks any    `json:"unique_chunks"`
	MerkleRoot   any    `json:"merkle_root"`
}

type fileRec struct {
	Path        string   `json:"path"`
	Kind        string   `json:"kind"`
	Size        int64    `json:"size"`
	FileID      any      `json:"file_id"`
	ChunkIDs    []string `json:"chunk_ids"`
	LinkTarget  any      `json:"link_target"`
	PrimaryPath any      `json:"primary_path"`
}

type holeRec struct {
	Offset int `json:"offset"`
	Length int `json:"length"`
}

type restoreRec struct {
	Path        string    `json:"path"`
	Kind        string    `json:"kind"`
	FileID      any       `json:"file_id"`
	ChunkIDs    []string  `json:"chunk_ids"`
	Holes       []holeRec `json:"holes"`
	PrimaryPath any       `json:"primary_path"`
}

type chunkRec struct {
	ChunkID   string `json:"chunk_id"`
	StoreName string `json:"store_name"`
	Size      int    `json:"size"`
	RefCount  int    `json:"ref_count"`
}

type attestationRec struct {
	JobID          string `json:"job_id"`
	MerkleRoot     string `json:"merkle_root"`
	Domain         string `json:"domain"`
	ManifestSHA256 string `json:"manifest_sha256"`
	StoreBinding   string `json:"store_binding"`
	SignatureHex   string `json:"signature_hex"`
}

type ledgerEntry struct {
	JobID        string `json:"job_id"`
	MerkleRoot   string `json:"merkle_root"`
	StoreBinding string `json:"store_binding"`
	PrevHash     string `json:"prev_hash"`
	EntryHash    string `json:"entry_hash"`
}

type jobManifest struct {
	JobID string    `json:"job_id"`
	Files []fileRec `json:"files"`
}

type chunkCatalog struct {
	Chunks []chunkRec `json:"chunks"`
}

type dedupReport struct {
	JobID        string `json:"job_id"`
	TotalFiles   int    `json:"total_files"`
	PrimaryFiles int    `json:"primary_files"`
	AliasFiles   int    `json:"alias_files"`
	TotalBytes   int    `json:"total_bytes"`
	StoredBytes  int    `json:"stored_bytes"`
}

type restorationMap struct {
	JobID   string       `json:"job_id"`
	Entries []restoreRec `json:"entries"`
}

type summaryRec struct {
	JobID        string `json:"job_id"`
	FileCount    int    `json:"file_count"`
	ByteCount    int    `json:"byte_count"`
	ChunkCount   int    `json:"chunk_count"`
	UniqueChunks int    `json:"unique_chunks"`
	MerkleRoot   string `json:"merkle_root"`
	GzipLevel    int    `json:"gzip_level"`
}

func derivePolicy(url string, body []byte) policy {
	bodyHash := sha256Sum(body)
	gearSeed := sha256Sum(append([]byte("gear\x00"), body...))
	macKey := sha256Sum(append([]byte("hmac\x00"), body...))
	storeSalt := sha256Sum(append([]byte("store\x00"), body...))
	var gear [256]uint32
	for i := 0; i < 256; i++ {
		d := sha256Sum(append(append([]byte{}, gearSeed...), u32be(uint32(i))...))
		gear[i] = uint32(d[0])<<24 | uint32(d[1])<<16 | uint32(d[2])<<8 | uint32(d[3])
	}
	return policy{
		URL: url, SHA256: hex.EncodeToString(bodyHash), ByteLength: len(body),
		Domain: hex.EncodeToString(bodyHash)[:32], GearSeed: gearSeed, StoreSalt: storeSalt, MacKey: macKey, Gear: gear,
	}
}

func cdcChunk(data []byte, gear [256]uint32) [][]byte {
	if len(data) == 0 {
		return nil
	}
	var chunks [][]byte
	start, fp, length := 0, uint32(0), 0
	for i, b := range data {
		fp = (fp << 1) + gear[b]
		length++
		cut := length >= maxChunk || (length >= minChunk && (fp&mask) == 0)
		if cut {
			chunks = append(chunks, data[start:i+1])
			start = i + 1
			fp, length = 0, 0
		}
	}
	if start < len(data) {
		chunks = append(chunks, data[start:])
	}
	return chunks
}

func findHoles(data []byte) []holeRec {
	holes := []holeRec{}
	for i := 0; i < len(data); {
		if data[i] != 0 {
			i++
			continue
		}
		j := i
		for j < len(data) && data[j] == 0 {
			j++
		}
		if j-i >= 2048 {
			holes = append(holes, holeRec{Offset: i, Length: j - i})
		}
		i = j
	}
	return holes
}

func merkleRoot(ids []string) string {
	uniq := append([]string{}, ids...)
	sort.Strings(uniq)
	w := 0
	for i := 0; i < len(uniq); i++ {
		if i == 0 || uniq[i] != uniq[i-1] {
			uniq[w] = uniq[i]
			w++
		}
	}
	uniq = uniq[:w]
	if len(uniq) == 0 {
		return zero64
	}
	level := make([][]byte, len(uniq))
	for i, id := range uniq {
		level[i] = sha256Sum(append([]byte{0xA5}, []byte(id)...))
	}
	for len(level) > 1 {
		var nxt [][]byte
		for i := 0; i < len(level); i += 2 {
			if i+1 == len(level) {
				nxt = append(nxt, level[i])
			} else {
				buf := append([]byte{0x5A}, level[i]...)
				buf = append(buf, level[i+1]...)
				nxt = append(nxt, sha256Sum(buf))
			}
		}
		level = nxt
	}
	return hex.EncodeToString(level[0])
}

func excluded(rel string, patterns []string) bool {
	base := path.Base(rel)
	for _, pat := range patterns {
		ok1, _ := path.Match(pat, rel)
		ok2, _ := path.Match(pat, base)
		if ok1 || ok2 {
			return true
		}
	}
	return false
}

type entry struct {
	path, kind, target, primary string
	size                        int64
	mode                        os.FileMode
	dev, ino                    uint64
	body                        []byte
	fileID                      string
	chunkIDs, storeNames        []string
	holes                       []holeRec
}

func scanJob(src string, patterns []string) ([]entry, error) {
	var raw []entry
	err := filepath.Walk(src, func(full string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if full == src {
			return nil
		}
		rel, err := filepath.Rel(src, full)
		if err != nil {
			return err
		}
		rel = filepath.ToSlash(rel)
		if excluded(rel, patterns) {
			if info.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}
		st, err := os.Lstat(full)
		if err != nil {
			return err
		}
		sys := st.Sys().(*syscall.Stat_t)
		e := entry{path: rel, size: st.Size(), mode: st.Mode(), dev: uint64(sys.Dev), ino: uint64(sys.Ino)}
		if st.Mode()&os.ModeSymlink != 0 {
			e.kind = "symlink"
			e.target, err = os.Readlink(full)
			if err != nil {
				return err
			}
		} else if st.Mode().IsRegular() {
			e.kind = "regular"
		} else if st.IsDir() {
			return nil
		} else {
			return nil
		}
		raw = append(raw, e)
		return nil
	})
	if err != nil {
		return nil, err
	}
	groups := map[string][]int{}
	for i, e := range raw {
		if e.kind == "regular" {
			key := fmt.Sprintf("%d:%d", e.dev, e.ino)
			groups[key] = append(groups[key], i)
		}
	}
	for _, idxs := range groups {
		best := idxs[0]
		bestDepth := strings.Count(raw[best].path, "/")
		for _, i := range idxs[1:] {
			d := strings.Count(raw[i].path, "/")
			if d < bestDepth || (d == bestDepth && raw[i].path < raw[best].path) {
				best, bestDepth = i, d
			}
		}
		for _, i := range idxs {
			if i == best {
				raw[i].kind = "regular"
				raw[i].primary = ""
			} else {
				raw[i].kind = "hardlink"
				raw[i].primary = raw[best].path
			}
		}
	}
	sort.Slice(raw, func(i, j int) bool { return raw[i].path < raw[j].path })
	return raw, nil
}

func main() {
	epBytes, err := os.ReadFile("/app/data/endpoints.json")
	must(err)
	var ep endpoints
	must(json.Unmarshal(epBytes, &ep))
	resp, err := http.Get(ep.URL)
	must(err)
	body, err := io.ReadAll(resp.Body)
	resp.Body.Close()
	must(err)
	if sha256Hex(body) != ep.SHA256 {
		panic("policy hash mismatch")
	}
	pol := derivePolicy(ep.URL, body)
	must(os.MkdirAll("/app/output/chunk_store", 0o755))
	writeJSON("/app/output/policy_receipt.json", policyReceipt{
		URL: pol.URL, SHA256: pol.SHA256, ByteLength: pol.ByteLength,
		AttestationDomain: pol.Domain, GearSeedHex: hex.EncodeToString(pol.GearSeed),
		StoreSaltHex: hex.EncodeToString(pol.StoreSalt), MacKeyHex: hex.EncodeToString(pol.MacKey),
	})

	type jobWork struct {
		ID, Src, Config string
	}
	var jobs []jobWork
	manBytes, err := os.ReadFile("/app/data/manifest.json")
	must(err)
	var man manifestFile
	must(json.Unmarshal(manBytes, &man))
	for _, job := range man.Jobs {
		jobs = append(jobs, jobWork{
			ID: job.ID, Src: filepath.Join("/app/data", job.Src),
			Config: filepath.Join("/app/data", job.Config),
		})
	}
	extraPath := "/app/resources/remote_catalog/extra_jobs.json"
	if _, err := os.Stat(extraPath); err == nil {
		extraBytes, err := os.ReadFile(extraPath)
		must(err)
		var extras []struct {
			ID     string `json:"id"`
			Src    string `json:"src"`
			Config string `json:"config"`
		}
		must(json.Unmarshal(extraBytes, &extras))
		for _, job := range extras {
			jobs = append(jobs, jobWork{
				ID: job.ID, Src: filepath.Join("/app/resources/remote_catalog", job.Src),
				Config: filepath.Join("/app/resources/remote_catalog", job.Config),
			})
		}
	}

	writtenStores := map[string]bool{}
	globalChunks := map[string]*chunkRec{}
	var reportLines []string
	var ledger []ledgerEntry
	prevHash := zero64

	for _, job := range jobs {
		cfgBytes, err := os.ReadFile(job.Config)
		must(err)
		var cfg backupConfig
		must(json.Unmarshal(cfgBytes, &cfg))
		src := job.Src
		entries, err := scanJob(src, cfg.Exclude)
		must(err)
		deny := false
		for _, e := range entries {
			if strings.Contains(e.path, "__deny__") {
				deny = true
				break
			}
		}
		nullRow := func(status string) {
			reportLines = append(reportLines, compactJSON(reportRow{
				JobID: job.ID, Status: status, FileCount: nil, ByteCount: nil,
				ChunkCount: nil, UniqueChunks: nil, MerkleRoot: nil,
			}))
		}
		if deny {
			nullRow("quarantined")
			continue
		}
		if len(entries) == 0 {
			nullRow("failed")
			continue
		}

		primaries := map[string]*entry{}
		for i := range entries {
			e := &entries[i]
			if e.kind == "regular" {
				e.body, err = os.ReadFile(filepath.Join(src, e.path))
				must(err)
				e.fileID = sha512_256Hex(e.body)
				e.holes = findHoles(e.body)
				chunks := cdcChunk(e.body, pol.Gear)
				e.chunkIDs = []string{}
				e.storeNames = []string{}
				for _, ch := range chunks {
					cid := sha512_256Hex(ch)
					sname := sha256Hex(append(append([]byte{}, pol.StoreSalt...), ch...))
					e.chunkIDs = append(e.chunkIDs, cid)
					e.storeNames = append(e.storeNames, sname)
				}
				primaries[e.path] = e
			}
		}
		for i := range entries {
			e := &entries[i]
			if e.kind == "hardlink" {
				p := primaries[e.primary]
				e.fileID = p.fileID
				e.chunkIDs = append([]string{}, p.chunkIDs...)
				e.storeNames = append([]string{}, p.storeNames...)
				e.holes = []holeRec{}
			}
		}

		catalog := map[string]*chunkRec{}
		var manifestFiles []fileRec
		var restore []restoreRec
		storedBytes := 0
		totalBytes := 0
		primaryFiles, aliasFiles, allSlots := 0, 0, 0

		for i := range entries {
			e := &entries[i]
			if e.kind == "symlink" {
				manifestFiles = append(manifestFiles, fileRec{
					Path: e.path, Kind: "symlink", Size: 0, FileID: nil,
					ChunkIDs: []string{}, LinkTarget: e.target, PrimaryPath: nil,
				})
				restore = append(restore, restoreRec{
					Path: e.path, Kind: "symlink", FileID: nil, ChunkIDs: []string{},
					Holes: []holeRec{}, PrimaryPath: nil,
				})
				continue
			}
			if e.kind == "regular" {
				primaryFiles++
			} else {
				aliasFiles++
			}
			totalBytes += int(e.size)
			for j, cid := range e.chunkIDs {
				sname := e.storeNames[j]
				if _, ok := catalog[cid]; !ok {
					catalog[cid] = &chunkRec{ChunkID: cid, StoreName: sname, Size: 0, RefCount: 0}
				}
				catalog[cid].RefCount++
				allSlots++
				if _, ok := globalChunks[cid]; !ok {
					globalChunks[cid] = &chunkRec{ChunkID: cid, StoreName: sname, Size: 0, RefCount: 0}
				}
				globalChunks[cid].RefCount++
			}
			if e.kind == "regular" {
				chunks := cdcChunk(e.body, pol.Gear)
				for j, ch := range chunks {
					cid := e.chunkIDs[j]
					sname := e.storeNames[j]
					catalog[cid].Size = len(ch)
					globalChunks[cid].Size = len(ch)
					if !writtenStores[sname] {
						dir := filepath.Join("/app/output/chunk_store", sname[:2])
						must(os.MkdirAll(dir, 0o755))
						must(os.WriteFile(filepath.Join(dir, sname), ch, 0o644))
						writtenStores[sname] = true
						storedBytes += len(ch)
					}
				}
			}
			var primaryPath any
			if e.kind == "hardlink" {
				primaryPath = e.primary
			}
			cids := e.chunkIDs
			if cids == nil {
				cids = []string{}
			}
			manifestFiles = append(manifestFiles, fileRec{
				Path: e.path, Kind: e.kind, Size: e.size, FileID: e.fileID,
				ChunkIDs: cids, LinkTarget: nil, PrimaryPath: primaryPath,
			})
			holes := e.holes
			if holes == nil {
				holes = []holeRec{}
			}
			restore = append(restore, restoreRec{
				Path: e.path, Kind: e.kind, FileID: e.fileID, ChunkIDs: cids,
				Holes: holes, PrimaryPath: primaryPath,
			})
		}

		var ids []string
		for id := range catalog {
			ids = append(ids, id)
		}
		root := merkleRoot(ids)
		var storeNames []string
		seen := map[string]bool{}
		for _, id := range ids {
			sn := catalog[id].StoreName
			if !seen[sn] {
				seen[sn] = true
				storeNames = append(storeNames, sn)
			}
		}
		sort.Strings(storeNames)
		storeBinding := sha256Hex([]byte(strings.Join(storeNames, "\n")))

		jobOut := filepath.Join("/app/output/jobs", job.ID)
		must(os.MkdirAll(jobOut, 0o755))
		writeJSON(filepath.Join(jobOut, "manifest.json"), jobManifest{JobID: job.ID, Files: manifestFiles})
		manBytesOut, err := os.ReadFile(filepath.Join(jobOut, "manifest.json"))
		must(err)
		manSHA := sha256Hex(manBytesOut)

		sort.Strings(ids)
		catList := make([]chunkRec, 0, len(ids))
		for _, id := range ids {
			catList = append(catList, *catalog[id])
		}
		writeJSON(filepath.Join(jobOut, "chunk_catalog.json"), chunkCatalog{Chunks: catList})
		writeJSON(filepath.Join(jobOut, "dedup_report.json"), dedupReport{
			JobID: job.ID, TotalFiles: len(entries), PrimaryFiles: primaryFiles,
			AliasFiles: aliasFiles, TotalBytes: totalBytes, StoredBytes: storedBytes,
		})
		writeJSON(filepath.Join(jobOut, "restoration_map.json"), restorationMap{JobID: job.ID, Entries: restore})
		writeJSON(filepath.Join(jobOut, "summary.json"), summaryRec{
			JobID: job.ID, FileCount: len(entries), ByteCount: totalBytes,
			ChunkCount: allSlots, UniqueChunks: len(catalog), MerkleRoot: root, GzipLevel: cfg.GzipLevel,
		})

		must(writeArchive(filepath.Join(jobOut, "archive.tar.gz"), entries, cfg.GzipLevel))

		msg := strings.Join([]string{pol.Domain, job.ID, root, manSHA, storeBinding}, "\n")
		mac := hmac.New(sha256.New, pol.MacKey)
		mac.Write([]byte(msg))
		sig := hex.EncodeToString(mac.Sum(nil))
		writeJSON(filepath.Join(jobOut, "attestation.json"), attestationRec{
			JobID: job.ID, MerkleRoot: root, Domain: pol.Domain,
			ManifestSHA256: manSHA, StoreBinding: storeBinding, SignatureHex: sig,
		})

		entryHash := sha256Hex([]byte(prevHash + job.ID + root + storeBinding))
		ledger = append(ledger, ledgerEntry{
			JobID: job.ID, MerkleRoot: root, StoreBinding: storeBinding,
			PrevHash: prevHash, EntryHash: entryHash,
		})
		prevHash = entryHash

		reportLines = append(reportLines, compactJSON(reportRow{
			JobID: job.ID, Status: "ok", FileCount: len(entries), ByteCount: totalBytes,
			ChunkCount: allSlots, UniqueChunks: len(catalog), MerkleRoot: root,
		}))
	}

	gids := make([]string, 0, len(globalChunks))
	for id := range globalChunks {
		gids = append(gids, id)
	}
	sort.Strings(gids)
	gList := make([]chunkRec, 0, len(gids))
	for _, id := range gids {
		gList = append(gList, *globalChunks[id])
	}
	if ledger == nil {
		ledger = []ledgerEntry{}
	}
	writeJSON("/app/output/global_chunk_registry.json", chunkCatalog{Chunks: gList})
	writeJSON("/app/output/ledger.json", struct {
		Entries []ledgerEntry `json:"entries"`
	}{Entries: ledger})
	rf, err := os.Create("/app/output/report.jsonl")
	must(err)
	w := bufio.NewWriter(rf)
	for _, line := range reportLines {
		fmt.Fprintln(w, line)
	}
	must(w.Flush())
	must(rf.Close())
}

func writeArchive(outPath string, entries []entry, level int) error {
	f, err := os.Create(outPath)
	if err != nil {
		return err
	}
	defer f.Close()
	gz, err := gzip.NewWriterLevel(f, level)
	if err != nil {
		return err
	}
	tw := tar.NewWriter(gz)
	for _, e := range entries {
		hdr := &tar.Header{
			Name:    e.path,
			Mode:    int64(e.mode.Perm()),
			Uid:     0,
			Gid:     0,
			Uname:   "",
			Gname:   "",
			ModTime: time.Unix(0, 0).UTC(),
			Format:  tar.FormatUSTAR,
		}
		switch e.kind {
		case "symlink":
			hdr.Typeflag = tar.TypeSymlink
			hdr.Linkname = e.target
			hdr.Size = 0
			if err := tw.WriteHeader(hdr); err != nil {
				return err
			}
		case "hardlink":
			hdr.Typeflag = tar.TypeLink
			hdr.Linkname = e.primary
			hdr.Size = 0
			if err := tw.WriteHeader(hdr); err != nil {
				return err
			}
		default:
			hdr.Typeflag = tar.TypeReg
			hdr.Size = int64(len(e.body))
			if err := tw.WriteHeader(hdr); err != nil {
				return err
			}
			if _, err := tw.Write(e.body); err != nil {
				return err
			}
		}
	}
	if err := tw.Close(); err != nil {
		return err
	}
	return gz.Close()
}
