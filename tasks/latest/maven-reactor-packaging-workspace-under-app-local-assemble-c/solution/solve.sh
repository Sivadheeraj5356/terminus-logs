#!/bin/bash
set -euo pipefail
cd /app

cat > loom/OpA.java <<'EOF'
package loom;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/** Classifier packaging stage. */
public final class OpA {
    private OpA() {}

    public static void main(String[] args) throws Exception {
        OpA(Path.of(args[0]), Path.of(args[1]));
    }

    /** Writes classifier pick id from opaque fixture maps. */
    public static void OpA(Path a, Path b) throws IOException {
        PackIo.ensureDir(b);
        String text = PackIo.read(a);
        long tool = PackIo.num(text, "toolchain_arch");
        if (tool < 0L) {
            tool = 0L;
        }
        String pick = PackIo.str(text, "id_real_" + tool);
        if (pick.isEmpty()) {
            pick = PackIo.str(text, "id_stub");
            tool = 0L;
        } else {
            Path table = Path.of("modules/native/classifiers.txt");
            if (Files.isRegularFile(table)) {
                String tableText = Files.readString(table);
                if (!tableText.contains(pick)) {
                    pick = PackIo.str(text, "id_stub");
                    tool = 0L;
                }
            }
        }
        PackIo.write(b.resolve("classifier.pick"), pick);
        PackIo.write(b.resolve("pick.arch"), Long.toString(tool));
    }
}
EOF

cat > hearth/OpB.java <<'EOF'
package hearth;

import java.io.IOException;
import java.nio.file.Path;

/** Path-lane packaging stage. */
public final class OpB {
    private OpB() {}

    public static void main(String[] args) throws Exception {
        OpB(Path.of(args[0]), Path.of(args[1]));
    }

    /** Writes path lane markers for classpath and module-path from opaque fixture maps. */
    public static void OpB(Path a, Path b) throws IOException {
        PackIo.ensureDir(b);
        String text = PackIo.read(a);
        long hasCp = PackIo.num(text, "has_cp_classifier");
        long hasMp = PackIo.num(text, "has_mp_classifier");
        long hasCpStub = PackIo.num(text, "has_cp_stub");

        if (hasCp == 1L) {
            PackIo.write(b.resolve("lane.cp"), "real");
            PackIo.write(b.resolve("ok.cp"), "true");
        } else if (hasCpStub == 1L) {
            PackIo.write(b.resolve("lane.cp"), "stub");
            PackIo.write(b.resolve("ok.cp"), "false");
        } else {
            PackIo.write(b.resolve("lane.cp"), "none");
            PackIo.write(b.resolve("ok.cp"), "false");
        }

        if (hasMp == 1L) {
            PackIo.write(b.resolve("lane.mp"), "real");
            PackIo.write(b.resolve("ok.mp"), "true");
        } else if (hasCp == 1L || hasCpStub == 1L) {
            PackIo.write(b.resolve("lane.mp"), "leak");
            PackIo.write(b.resolve("ok.mp"), "false");
        } else {
            PackIo.write(b.resolve("lane.mp"), "none");
            PackIo.write(b.resolve("ok.mp"), "false");
        }
        PackIo.write(b.resolve("assemble.ok"), "true");
    }
}
EOF

cat > anvil/OpC.java <<'EOF'
package anvil;

import java.io.IOException;
import java.nio.file.Path;

/** Stamp and soname packaging stage. */
public final class OpC {
    private OpC() {}

    public static void main(String[] args) throws Exception {
        OpC(Path.of(args[0]), Path.of(args[1]));
    }

    /** Writes stamp bind, soname mark, and gate marker from opaque fixture maps. */
    public static void OpC(Path a, Path b) throws IOException {
        PackIo.ensureDir(b);
        String text = PackIo.read(a);
        long tool = PackIo.num(text, "toolchain_arch");
        String real = PackIo.str(text, "id_real_" + tool);
        long arch = tool;
        String gate = "allow";
        if (!real.isEmpty()) {
            gate = "refuse";
        } else {
            arch = 0L;
            String bait = PackIo.str(text, "id_stub");
            if (bait.isEmpty()) {
                PackIo.write(b.resolve("stamp.bind"), "");
                PackIo.write(b.resolve("soname.mark"), "");
                PackIo.write(b.resolve("stub.gate"), gate);
                return;
            }
        }
        String stamp = PackIo.str(text, "stamp_" + arch);
        String soname = PackIo.str(text, "soname_" + arch);
        if (stamp.isEmpty()) {
            stamp = PackIo.str(text, "stamp_0");
        }
        if (soname.isEmpty()) {
            soname = PackIo.str(text, "soname_0");
        }
        PackIo.write(b.resolve("stamp.bind"), stamp);
        PackIo.write(b.resolve("soname.mark"), soname);
        PackIo.write(b.resolve("stub.gate"), gate);
    }
}
EOF

find loom hearth anvil pulse brace span probe -name '*.java' > /tmp/sources.list
javac -d /app/classes @/tmp/sources.list
rm -f /tmp/sources.list
mkdir -p /app/output /app/work
/app/bin/reactor
