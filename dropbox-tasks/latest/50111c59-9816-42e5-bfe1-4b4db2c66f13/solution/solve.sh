#!/usr/bin/env bash
set -euo pipefail

log() { printf '[solve] %s\n' "$1"; }

mkdir -p /app/output/stage

do_lane_a=1
do_fold_b=1
do_sync_c=1
do_zip_d=1
do_io_kit=1

if [ "${do_lane_a:-0}" = 1 ]; then
cat > /app/environment/n3/k2/LaneA.java <<'EOF'
package n3.k2;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public final class LaneA {
  private LaneA() {}

  static List<TypesA.EpochCand> lane_a(TypesA.Connection db, List<TypesA.GenKey> gens) {
    Set<Integer> allowed = new HashSet<>();
    for (TypesA.GenKey g : gens) {
      allowed.add(g.gen);
    }
    Map<String, TypesA.IssueRow> best = new HashMap<>();
    for (TypesA.IssueRow r : db.issue) {
      if (!allowed.contains(r.gen)) {
        continue;
      }
      String k = r.pid + ":" + r.gen;
      TypesA.IssueRow prev = best.get(k);
      if (prev == null || r.ts > prev.ts) {
        best.put(k, r);
      }
    }
    List<TypesA.EpochCand> out = new ArrayList<>();
    for (TypesA.IssueRow r : best.values()) {
      long tag = tagOf(r.pid, r.scp, r.role, r.gen);
      out.add(new TypesA.EpochCand(r.pid, r.gen, r.scp, r.role, tag));
    }
    out.sort(Comparator.comparing((TypesA.EpochCand c) -> c.pid + ":" + c.gen));
    return out;
  }

  public static List<TypesA.EpochCand> PackLane(TypesA.Connection db, List<TypesA.GenKey> gens) {
    return lane_a(db, gens);
  }

  public static long tagOf(String pid, String scp, String role, int gen) {
    try {
      String s = pid + "|" + scp + "|" + role + "|" + gen;
      MessageDigest md = MessageDigest.getInstance("SHA-256");
      byte[] dig = md.digest(s.getBytes(StandardCharsets.UTF_8));
      long v = 0;
      for (int i = 0; i < 8; i++) {
        v = (v << 8) | (dig[i] & 0xffL);
      }
      return v;
    } catch (Exception e) {
      throw new IllegalStateException(e);
    }
  }
}
EOF
fi

if [ "${do_fold_b:-0}" = 1 ]; then
cat > /app/environment/m8/q1/FoldB.java <<'EOF'
package m8.q1;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import n3.k2.LaneA;
import n3.k2.TypesA;

public final class FoldB {
  private FoldB() {}

  static List<TypesB.BoundView> fold_b(
      List<TypesA.EpochCand> cands, List<TypesB.PemBlob> mats, List<TypesB.AnchorGen> anchors) {
    Set<Integer> allowed = new HashSet<>();
    for (TypesB.AnchorGen a : anchors) {
      allowed.add(a.gen);
    }
    Map<String, TypesB.PemBlob> by = new HashMap<>();
    for (TypesB.PemBlob m : mats) {
      by.put(m.pid + ":" + m.gen, m);
    }
    List<TypesB.BoundView> out = new ArrayList<>();
    for (TypesA.EpochCand c : cands) {
      if (!allowed.contains(c.gen)) {
        continue;
      }
      TypesB.PemBlob m = by.get(c.pid + ":" + c.gen);
      if (m == null) {
        continue;
      }
      long tag = LaneA.tagOf(c.pid, c.scp, m.role, c.gen);
      out.add(new TypesB.BoundView(c.pid, c.gen, c.scp, m.role, m.fp, tag));
    }
    out.sort(Comparator.comparing((TypesB.BoundView v) -> v.pid + ":" + v.gen));
    return out;
  }

  public static List<TypesB.BoundView> BindFold(
      List<TypesA.EpochCand> cands, List<TypesB.PemBlob> mats, List<TypesB.AnchorGen> anchors) {
    return fold_b(cands, mats, anchors);
  }
}
EOF
fi

if [ "${do_sync_c:-0}" = 1 ]; then
cat > /app/environment/t5/r4/SyncC.java <<'EOF'
package t5.r4;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import m8.q1.TypesB;
import n3.k2.TypesA;

public final class SyncC {
  private SyncC() {}

  static List<TypesC.TrustWin> sync_c(
      TypesA.Connection db, List<TypesB.BoundView> views, List<TypesC.HsFrag> frags) {
    Map<String, TypesC.HsFrag> hs = new HashMap<>();
    for (TypesC.HsFrag f : frags) {
      hs.put(f.pid + ":" + f.gen, f);
    }
    List<TypesC.TrustWin> out = new ArrayList<>();
    for (TypesB.BoundView v : views) {
      boolean revoked = lookupRev(db, v.pid, v.gen);
      TypesC.HsFrag f = hs.get(v.pid + ":" + v.gen);
      boolean hsFail = f == null || !f.ok;
      out.add(new TypesC.TrustWin(v.pid, v.gen, v.role, v.tag, revoked, hsFail));
    }
    out.sort(Comparator.comparing((TypesC.TrustWin w) -> w.pid + ":" + w.gen));
    try {
      Path stage = Path.of("/app/output/stage");
      Files.createDirectories(stage);
      StringBuilder tip = new StringBuilder();
      for (TypesC.TrustWin w : out) {
        tip.append(w.pid).append(":").append(w.gen).append("\n");
      }
      Files.writeString(stage.resolve("early.tip"), tip.toString());
    } catch (Exception ignored) {
    }
    return out;
  }

  public static List<TypesC.TrustWin> SnapSync(
      TypesA.Connection db, List<TypesB.BoundView> views, List<TypesC.HsFrag> frags) {
    return sync_c(db, views, frags);
  }

  static boolean lookupRev(TypesA.Connection db, String pid, int gen) {
    for (TypesA.RevRow r : db.revoke) {
      if (r.pid.equals(pid) && r.gen == gen) {
        return r.revoked != 0;
      }
    }
    return false;
  }
}
EOF
fi

if [ "${do_zip_d:-0}" = 1 ]; then
cat > /app/environment/t5/r4/ZipD.java <<'EOF'
package t5.r4;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;

public final class ZipD {
  private ZipD() {}

  static TypesC.SealRecord zip_d(List<TypesC.TrustWin> wins, List<TypesC.StageRow> stages) {
    String pack = stages.isEmpty() ? "" : stages.get(0).packId;
    String arm = stages.isEmpty() ? "" : stages.get(0).armId;
    byte[] raw = hashWins(pack, arm, wins);
    StringBuilder hex = new StringBuilder();
    for (byte b : raw) {
      hex.append(String.format("%02x", b));
    }
    int sealOk = hex.length() == 64 ? 1 : 0;
    return new TypesC.SealRecord(hex.toString(), 0, sealOk, raw);
  }

  public static TypesC.SealRecord SealZip(List<TypesC.TrustWin> wins, List<TypesC.StageRow> stages) {
    return zip_d(wins, stages);
  }

  static byte[] hashWins(String pack, String arm, List<TypesC.TrustWin> wins) {
    try {
      MessageDigest md = MessageDigest.getInstance("SHA-256");
      md.update(pack.getBytes(StandardCharsets.UTF_8));
      md.update((byte) 0);
      md.update(arm.getBytes(StandardCharsets.UTF_8));
      md.update((byte) 0);
      List<TypesC.TrustWin> sorted = new ArrayList<>(wins);
      sorted.sort((a, b) -> a.pid.compareTo(b.pid));
      for (TypesC.TrustWin w : sorted) {
        md.update(w.pid.getBytes(StandardCharsets.UTF_8));
        md.update(intLE(w.gen));
        md.update(w.role.getBytes(StandardCharsets.UTF_8));
        md.update(longBE(w.tag));
        md.update((byte) (w.revoked ? 1 : 0));
        md.update((byte) (w.hsFail ? 1 : 0));
      }
      return md.digest();
    } catch (Exception e) {
      throw new IllegalStateException(e);
    }
  }

  private static byte[] intLE(int v) {
    return new byte[] {
      (byte) (v & 0xff),
      (byte) ((v >> 8) & 0xff),
      (byte) ((v >> 16) & 0xff),
      (byte) ((v >> 24) & 0xff)
    };
  }

  private static byte[] longBE(long v) {
    byte[] b = new byte[8];
    for (int i = 7; i >= 0; i--) {
      b[i] = (byte) (v & 0xff);
      v >>= 8;
    }
    return b;
  }
}
EOF
fi

if [ "${do_io_kit:-0}" = 1 ]; then
python3 - <<'PY'
from pathlib import Path
path = Path("/app/environment/driver/IoKit.java")
text = path.read_text(encoding="utf-8")
start = text.index('    if ("reorder_journals".equals(transform)) {')
end = text.index("    return new TypesA.Connection(issue, revoke);", start)
fixed = '''    if ("reorder_journals".equals(transform)) {
      issue.sort(Comparator.comparingInt((TypesA.IssueRow r) -> -r.ts));
    } else if ("drop_redundant_snap".equals(transform)) {
      Map<String, TypesA.IssueRow> best = new HashMap<>();
      for (TypesA.IssueRow r : issue) {
        String k = r.pid + ":" + r.gen;
        TypesA.IssueRow prev = best.get(k);
        if (prev == null || r.ts > prev.ts) {
          best.put(k, r);
        }
      }
      issue = new ArrayList<>(best.values());
    }
'''
path.write_text(text[:start] + fixed + text[end:], encoding="utf-8")
PY
fi

log "rebuild and emit"
bash /app/environment/tools/build_x7.sh
/app/bin/x7 --evidence /app/corp --out /app/output/tl.json
log "done"
