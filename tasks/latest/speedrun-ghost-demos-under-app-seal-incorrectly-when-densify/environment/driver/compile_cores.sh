#!/bin/bash
set -euo pipefail
ROOT=/app
WORK="$ROOT/work"
CLASSES="$WORK/classes"
mkdir -p "$CLASSES" "$WORK"

find "$CLASSES" -type f -name '*.class' -delete 2>/dev/null || true

javac -d "$CLASSES" \
  "$ROOT/common/Io.java" \
  "$ROOT/q7/SepAux.java" "$ROOT/q7/SepH.java" "$ROOT/q7/SepMain.java" \
  "$ROOT/m4/FoldAux.java" "$ROOT/m4/FoldG.java" "$ROOT/m4/FoldMain.java" \
  "$ROOT/v9/TieAux.java" "$ROOT/v9/TieW.java" "$ROOT/v9/TieMain.java" \
  "$ROOT/d1/BlendX.java" "$ROOT/d1/ScanY.java" \
  "$ROOT/e3/TagZ.java"

cat > "$WORK/sep_tool" <<'EOS'
#!/bin/bash
exec java -cp /app/work/classes q7.SepMain "$@"
EOS
cat > "$WORK/fold_tool" <<'EOS'
#!/bin/bash
exec java -cp /app/work/classes m4.FoldMain "$@"
EOS
cat > "$WORK/tie_tool" <<'EOS'
#!/bin/bash
exec java -cp /app/work/classes v9.TieMain "$@"
EOS
chmod +x "$WORK/sep_tool" "$WORK/fold_tool" "$WORK/tie_tool"
