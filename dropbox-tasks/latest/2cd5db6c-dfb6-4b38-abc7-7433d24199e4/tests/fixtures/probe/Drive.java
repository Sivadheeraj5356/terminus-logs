package probe;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;
import java.util.stream.Stream;

/** Orchestrates packaging stages and emits ffm_ledger.json / reactor_claim.json. */
public final class Drive {
    public static void main(String[] args) throws Exception {
        Path root = Path.of(".");
        Path casesDir = root.resolve("data").resolve("scenarios");
        Path outDir = root.resolve("output");
        Path workRoot = root.resolve("work");
        Files.createDirectories(workRoot);
        Files.createDirectories(outDir);

        List<Path> packs;
        try (Stream<Path> stream = Files.list(casesDir)) {
            packs =
                    stream
                            .filter(p -> !Files.isSymbolicLink(p))
                            .filter(p -> Files.isRegularFile(p, LinkOption.NOFOLLOW_LINKS))
                            .filter(p -> p.getFileName().toString().endsWith(".json"))
                            .sorted(Comparator.comparing(p -> p.getFileName().toString()))
                            .collect(Collectors.toList());
        }
        if (packs.isEmpty()) {
            throw new IllegalStateException("no scenario packs under " + casesDir);
        }

        Map<String, Object> cases = new LinkedHashMap<>();
        for (Path caseJson : packs) {
            String fileName = caseJson.getFileName().toString();
            String name = fileName.substring(0, fileName.length() - ".json".length());
            Path work = workRoot.resolve(name);
            Files.createDirectories(work);
            runJava("loom.GateLoad", caseJson, work);
            runJava("hearth.GateLoad", caseJson, work);
            runJava("anvil.GateLoad", caseJson, work);
            runQuiet("ops/pulse_echo.sh", root.resolve("modules/native/classifiers.txt").toString());
            runQuiet("ops/brace_echo.sh", root.resolve("modules/toolchain/pins.txt").toString());
            runQuiet("ops/span_echo.sh", root.resolve("modules/jextract/stamps.txt").toString());
            cases.put(name, buildCase(name, work));
        }

        Map<String, Object> ledger = new LinkedHashMap<>();
        ledger.put("cases", cases);
        Files.writeString(
                outDir.resolve("ffm_ledger.json"),
                JsonMini.stringifyPretty(ledger),
                StandardCharsets.UTF_8);
        Files.writeString(
                outDir.resolve("reactor_claim.json"),
                JsonMini.stringifyPretty(Surface.fromCases(cases)),
                StandardCharsets.UTF_8);
    }

    private static String classesCp() {
        String env = System.getenv("REACTOR_CLASSES");
        if (env != null && !env.isBlank()) {
            return env;
        }
        return "/app/classes";
    }

    private static void runJava(String mainClass, Path caseJson, Path work) throws Exception {
        ProcessBuilder pb =
                new ProcessBuilder(
                        "java",
                        "-cp",
                        classesCp(),
                        mainClass,
                        caseJson.toString(),
                        work.toString());
        pb.redirectErrorStream(true);
        Process p = pb.start();
        String out = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        if (!p.waitFor(120, TimeUnit.SECONDS) || p.exitValue() != 0) {
            throw new IllegalStateException("stage failed: " + mainClass + "\n" + out);
        }
    }

    private static Map<String, Object> buildCase(String name, Path work) throws Exception {
        String pick = readTrim(work.resolve("classifier.pick"));
        String stamp = readTrim(work.resolve("stamp.bind"));
        String soname = readTrim(work.resolve("soname.mark"));
        String gate = readTrim(work.resolve("stub.gate"));
        boolean okAssemble = "true".equalsIgnoreCase(readTrim(work.resolve("assemble.ok")));

        List<Map<String, Object>> entries = new ArrayList<>();
        Map<String, String> tokens = new TreeMap<>();
        entries.add(
                entry(
                        name,
                        "classpath",
                        pick,
                        readTrim(work.resolve("lane.cp")),
                        stamp,
                        soname,
                        gate,
                        "true".equalsIgnoreCase(readTrim(work.resolve("ok.cp"))),
                        tokens));
        entries.add(
                entry(
                        name,
                        "module-path",
                        pick,
                        readTrim(work.resolve("lane.mp")),
                        stamp,
                        soname,
                        gate,
                        "true".equalsIgnoreCase(readTrim(work.resolve("ok.mp"))),
                        tokens));

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("case_id", name);
        out.put("entries", entries);
        out.put("assemble_ok", okAssemble);
        out.put("state_hash", ShaHex.sha256Hex(tokens.toString()));
        return out;
    }

    private static Map<String, Object> entry(
            String caseId,
            String mode,
            String pick,
            String lane,
            String stamp,
            String soname,
            String gate,
            boolean ok,
            Map<String, String> tokens) {
        String token =
                ShaHex.sha256Hex(
                        caseId
                                + "|"
                                + mode
                                + "|"
                                + pick
                                + "|"
                                + lane
                                + "|"
                                + stamp
                                + "|"
                                + soname
                                + "|"
                                + gate
                                + "|"
                                + ok);
        tokens.put(mode, token);
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("case_id", caseId);
        row.put("path_mode", mode);
        row.put("classifier_pick", pick);
        row.put("path_lane", lane);
        row.put("stamp_bind", stamp);
        row.put("soname_mark", soname);
        row.put("stub_gate", gate);
        row.put("bind_ok", ok);
        row.put("row_token", token);
        return row;
    }

    private static String readTrim(Path p) throws Exception {
        if (!Files.exists(p)) {
            return "";
        }
        return Files.readString(p, StandardCharsets.UTF_8).trim();
    }

    private static void runQuiet(String rel, String arg) {
        try {
            ProcessBuilder pb = new ProcessBuilder("bash", Path.of(rel).toString(), arg);
            pb.redirectErrorStream(true);
            Process p = pb.start();
            p.waitFor();
        } catch (Exception ignored) {
            // helper exit ignored
        }
    }
}
