# mux edge resolve (awk)
# invoked: awk -v active=csv -v out=path -f knit_z7.awk corpus/*.dbc

function knit_z7(src, dst, mux,    a, n, i, ok) {
  n = split(active, a, ",")
  ok = 0
  for (i = 1; i <= n; i++) if (a[i] == dst) ok = 1
  if (!ok) return
  print src "\t" dst >> out
}

function in_active(id,    a, n, i) {
  n = split(active, a, ",")
  for (i = 1; i <= n; i++) if (a[i] == id) return 1
  return 0
}

BEGIN {
  cur = ""
  printf "" > out
  close(out)
}

/^BO_ / {
  cur = $NF
  next
}

/^PEER / {
  if (cur == "") next
  if (!in_active(cur)) next
  if (!(cur in seen)) {
    seen[cur] = 0
  }
  seen[cur] = seen[cur] + 1
  # lane-stable primary retain under ordered counter
  if (seen[cur] != 1) {
    next
  }
  if (!in_active($2)) next
  knit_z7(cur, $2, "x")
  next
}
