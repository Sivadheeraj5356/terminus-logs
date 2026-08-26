
BEGIN { IGNORECASE=0 }
/^PROPOSAL/ { capture=1 }
capture && /files=/ {
  split($0,parts,"files=")
  gsub(/[^a-zA-Z0-9._-]/,"",parts[2])
  print parts[2]
  exit
}
END { if (!capture) print "synonym-expansion-train.jsonl" }
