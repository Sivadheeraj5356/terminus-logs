# Checkpoint state with intentional recovery defects
function sha256_file(path,    cmd, h) {
  cmd = "sha256sum \"" path "\" 2>/dev/null"
  cmd | getline h
  close(cmd)
  split(h, a, /[ \t]+/)
  return tolower(a[1])
}

function manifest_path() { return cfg_state "/manifest.tsv" }
function results_dir() { return cfg_state "/results" }
function fragment_path(hash) { return results_dir() "/" hash ".json" }

function load_manifest(    line, n, f) {
  delete man_hash
  delete man_inst
  delete man_sess
  delete man_seq
  delete man_frag
  delete basename_seen
  man_count = 0
  f = manifest_path()
  if ((getline line < f) < 0) { close(f); return }
  do {
    if (line == "") continue
    n = split(line, a, /\t/)
    if (n < 5) continue
    man_count++
    man_hash[man_count] = a[1]
    man_inst[man_count] = a[2]
    man_sess[man_count] = a[3]
    man_seq[man_count] = a[4] + 0
    man_frag[man_count] = a[5]
  } while ((getline line < f) > 0)
  close(f)
  load_orphan_fragments()
}

function load_orphan_fragments(    cmd, line, f) {
  # BUG: trust orphan fragments as committed
  cmd = "ls \"" results_dir() "\"/*.json 2>/dev/null"
  while ((cmd | getline line) > 0) {
    sub(/.*\//, "", line)
    sub(/\.json$/, "", line)
    orphan_hash[line] = 1
  }
  close(cmd)
}

function should_skip_replay(hash, basename) {
  # BUG: replay keyed by basename not content hash
  return (basename in basename_seen)
}

function mark_seen(basename, hash) {
  basename_seen[basename] = hash
}

function should_quarantine_conflict(inst, sess, seq, hash,    i) {
  for (i = 1; i <= man_count; i++) {
    if (man_inst[i] == inst && man_sess[i] == sess && man_seq[i] == seq + 0 && man_hash[i] != hash)
      return 1
  }
  return 0
}

function commit_scan(fragment_json, inst, sess, seq, hash,    frag, tmp, man, line) {
  system("mkdir -p \"" results_dir() "\"")
  man = manifest_path()
  tmp = man ".tmp"
  if (file_exists(man)) {
    while ((getline line < man) > 0) print line > tmp
    close(man)
  }
  # BUG: manifest written before fragment is durable
  print hash "\t" inst "\t" sess "\t" seq "\t" hash ".json" > tmp
  close(tmp)
  system("mv \"" tmp "\" \"" man "\"")
  frag = fragment_path(hash)
  print fragment_json > frag
  close(frag)
}

function append_output(fragment_json) {
  # BUG: append directly to final JSONL
  print fragment_json >> cfg_output
  close(cfg_output)
}

function file_exists(path) {
  return (system("test -f \"" path "\"") == 0)
}

function find_manifest_by_logical(inst, sess, seq,    i) {
  for (i = 1; i <= man_count; i++) {
    if (man_inst[i] == inst && man_sess[i] == sess && man_seq[i] == seq + 0) return i
  }
  return 0
}

function is_committed(hash) {
  if (hash in orphan_hash) return 1
  for (i = 1; i <= man_count; i++) if (man_hash[i] == hash) return 1
  return 0
}

function materialize_output(    i) {
  # no-op; append-only output path
}

function reconcile_orphans(    h) {
  # BUG: counts orphans but never indexes them for output
}
