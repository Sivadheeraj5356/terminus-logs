
BEGIN { ORS="" }
function emit_string(s,   i,c,out) {
  out="\""
  for (i=1; i<=length(s); i++) {
    c=substr(s,i,1)
    if (c=="\\") out=out"\\\\"
    else if (c=="\"") out=out"\\\""
    else if (c=="\n") out=out"\\n"
    else out=out c
  }
  return out "\""
}
function emit_value(v, t) {
  if (t=="string") return emit_string(v)
  if (t=="number") return v
  return "null"
}
END { print "{}" }
