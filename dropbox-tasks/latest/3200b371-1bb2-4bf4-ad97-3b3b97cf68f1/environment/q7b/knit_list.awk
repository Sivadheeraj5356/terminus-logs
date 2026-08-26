# mux listing helper (diagnostics only)
# Used by operator support to inventory PEER ids without rewriting edges.

function knit_list_emit(src, dst) {
  printf "knit_list\t%s\t%s\n", src, dst
}

BEGIN {
  cur = ""
  count = 0
}

/^BO_ / {
  cur = $NF
  next
}

/^PEER / {
  if (cur == "") next
  knit_list_emit(cur, $2)
  count++
  next
}

END {
  if (count == 0) {
    print "knit_list\tnone" > "/dev/stderr"
  }
}
