package org.example.parity;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.LinkOption;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

record SourceSpec(String repository, String revision, LinkedHashMap<String, String> artifacts) {
    static final List<String> FILES = List.of("mobilenet_v3_large.pt", "mobilenet_v3_large.onnx",
            "mobilenet_v3_large.onnx.data", "config.json");
    private static final List<String> KEYS = List.of("repository", "revision",
            "mobilenet_v3_large.pt", "mobilenet_v3_large.onnx",
            "mobilenet_v3_large.onnx.data", "config.json");
    private static final Pattern SHA = Pattern.compile("[0-9a-f]{64}");
    private static final Pattern REVISION = Pattern.compile("[0-9a-f]{40}");

    static SourceSpec read(Path path) throws IOException {
        if (Files.isSymbolicLink(path) || !Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS)) {
            throw new IllegalArgumentException("source properties must be a regular non-symlink file");
        }
        LinkedHashMap<String, String> values = new LinkedHashMap<>();
        for (String line : Files.readAllLines(path, StandardCharsets.UTF_8)) {
            if (line.isBlank() || line.startsWith("#") || !line.contains("=")) {
                throw new IllegalArgumentException("invalid source properties");
            }
            int split = line.indexOf('=');
            String key = line.substring(0, split);
            String value = line.substring(split + 1);
            if (key.isEmpty() || value.isEmpty() || values.put(key, value) != null) {
                throw new IllegalArgumentException("invalid source properties");
            }
        }
        if (!new java.util.ArrayList<>(values.keySet()).equals(KEYS)) {
            throw new IllegalArgumentException("invalid source properties");
        }
        String revision = values.remove("revision");
        String repository = values.remove("repository");
        if (!REVISION.matcher(revision).matches() || repository.isBlank()
                || !values.keySet().equals(new java.util.LinkedHashSet<>(FILES))) {
            throw new IllegalArgumentException("invalid source properties");
        }
        LinkedHashMap<String, String> artifacts = new LinkedHashMap<>();
        for (String file : FILES) {
            String digest = values.get(file);
            if (!SHA.matcher(digest).matches()) {
                throw new IllegalArgumentException("invalid artifact digest");
            }
            artifacts.put(file, digest);
        }
        return new SourceSpec(repository, revision, artifacts);
    }

    void verify(Path modelDir) throws IOException {
        if (Files.isSymbolicLink(modelDir) || !Files.isDirectory(modelDir, LinkOption.NOFOLLOW_LINKS)) {
            throw new IllegalArgumentException("model directory must be a regular non-symlink directory");
        }
        for (Map.Entry<String, String> entry : artifacts.entrySet()) {
            Path file = modelDir.resolve(entry.getKey());
            if (Files.isSymbolicLink(file) || !Files.isRegularFile(file, LinkOption.NOFOLLOW_LINKS)
                    || !Hashes.sha256(file).equals(entry.getValue())) {
                throw new IllegalArgumentException("missing or checksum-invalid model artifact: " + entry.getKey());
            }
        }
    }
}
