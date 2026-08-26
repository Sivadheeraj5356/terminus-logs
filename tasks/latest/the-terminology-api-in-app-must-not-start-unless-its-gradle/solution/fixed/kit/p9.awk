BEGIN {
  route = ""
  revision = ""
  delete files
  delete forbidden
  fc = 0
  forb = 0
}
/<!--[[:space:]]*FINAL_RATIFIED:/ {
  line = $0
  sub(/^.*FINAL_RATIFIED:/, "", line)
  sub(/-->.*/, "", line)
  n = split(line, parts, /[[:space:]]+/)
  local_route = ""
  local_revision = ""
  local_files = ""
  local_forbidden = ""
  for (i = 1; i <= n; i++) {
    split(parts[i], kv, "=")
  if (length(kv) < 2) continue
    key = kv[1]
    val = kv[2]
    if (key == "route") local_route = val
    else if (key == "revision") local_revision = val
    else if (key == "files") local_files = val
    else if (key == "forbidden") local_forbidden = val
  }
  if (local_route == "") next
  if (local_route == ENVIRON["TARGET_ROUTE"]) {
    route = local_route
    if (local_revision != "") revision = local_revision
    if (local_files != "") {
      m = split(local_files, arr, /,/)
      for (j = 1; j <= m; j++) if (arr[j] != "") files[++fc] = arr[j]
    }
    if (local_forbidden != "") {
      m = split(local_forbidden, arr, /,/)
      for (j = 1; j <= m; j++) if (arr[j] != "") forbidden[++forb] = arr[j]
    }
  }
}
END {
  print "route=" route
  print "revision=" revision
  for (i = 1; i <= fc; i++) print "file=" files[i]
  for (i = 1; i <= forb; i++) print "forbidden=" forbidden[i]
}
