package org.example.parity;

import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

record CliOptions(Path manifest, Path policy, Path modelDir, Path source, Path output) {
    private static final Set<String> NAMES = Set.of(
            "--manifest", "--policy", "--model-dir", "--source", "--output");

    static CliOptions parse(String[] args) {
        if (args.length != 10) {
            throw new IllegalArgumentException("exactly five named path options are required");
        }
        Map<String, Path> values = new LinkedHashMap<>();
        for (int i = 0; i < args.length; i += 2) {
            if (!NAMES.contains(args[i]) || values.containsKey(args[i])) {
                throw new IllegalArgumentException("unknown or duplicate option: " + args[i]);
            }
            Path value = Path.of(args[i + 1]);
            if (!value.isAbsolute() || !value.normalize().equals(value)) {
                throw new IllegalArgumentException("option paths must be absolute and normalized");
            }
            values.put(args[i], value.normalize());
        }
        if (!values.keySet().equals(NAMES)) {
            throw new IllegalArgumentException("all five named path options are required");
        }
        return new CliOptions(values.get("--manifest"), values.get("--policy"),
                values.get("--model-dir"), values.get("--source"), values.get("--output"));
    }
}
