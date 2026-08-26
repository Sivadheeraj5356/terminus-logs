package org.example.parity;

import com.fasterxml.jackson.core.StreamReadFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;

final class ManifestReader {
    private static final ObjectMapper MAPPER = JsonMapper.builder()
            .enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION).build();
    private static final Pattern SHA = Pattern.compile("[0-9a-f]{64}");

    private ManifestReader() {}

    static List<ManifestEntry> read(Path manifest) throws IOException {
        if (Files.isSymbolicLink(manifest) || !Files.isRegularFile(manifest, LinkOption.NOFOLLOW_LINKS)) {
            throw new IllegalArgumentException("manifest must be a regular non-symlink file");
        }
        byte[] manifestBytes = Files.readAllBytes(manifest);
        if (manifestBytes.length >= 3 && manifestBytes[0] == (byte) 0xef
                && manifestBytes[1] == (byte) 0xbb && manifestBytes[2] == (byte) 0xbf) {
            throw new IllegalArgumentException("manifest must not contain a UTF-8 BOM");
        }
        Path root = manifest.getParent().toRealPath();
        List<String> lines = Files.readAllLines(manifest, StandardCharsets.UTF_8);
        if (lines.isEmpty()) {
            throw new IllegalArgumentException("manifest must not be empty");
        }
        List<ManifestEntry> entries = new ArrayList<>();
        Set<String> ids = new HashSet<>();
        for (String line : lines) {
            if (line.isBlank()) {
                throw new IllegalArgumentException("blank manifest line");
            }
            JsonNode node = MAPPER.readTree(line);
            List<String> keys = new ArrayList<>();
            node.fieldNames().forEachRemaining(keys::add);
            if (!node.isObject() || !keys.equals(List.of("id", "image", "sha256", "group"))
                    || !node.get("id").isTextual() || !node.get("image").isTextual()
                    || !node.get("sha256").isTextual() || !node.get("group").isTextual()) {
                throw new IllegalArgumentException("invalid manifest entry");
            }
            String id = node.get("id").textValue();
            String image = node.get("image").textValue();
            String sha256 = node.get("sha256").textValue();
            String group = node.get("group").textValue();
            if (id.isBlank() || image.isBlank() || group.isBlank() || !SHA.matcher(sha256).matches()
                    || !ids.add(id)) {
                throw new IllegalArgumentException("empty or duplicate manifest id");
            }
            Path relative = Path.of(image);
            if (relative.isAbsolute() || image.contains("\\") || !relative.normalize().equals(relative)) {
                throw new IllegalArgumentException("unsafe manifest image path");
            }
            for (Path part : relative) {
                if (part.toString().equals(".") || part.toString().equals("..")) {
                    throw new IllegalArgumentException("unsafe manifest image path");
                }
            }
            Path target = root.resolve(relative).normalize();
            Path component = root;
            for (Path part : relative) {
                component = component.resolve(part);
                if (Files.isSymbolicLink(component)) {
                    throw new IllegalArgumentException("unsafe manifest image path");
                }
            }
            if (!target.startsWith(root)
                    || !Files.isRegularFile(target, LinkOption.NOFOLLOW_LINKS)) {
                throw new IllegalArgumentException("unsafe or missing manifest image");
            }
            if (!Hashes.sha256(target).equals(sha256)) {
                throw new IllegalArgumentException("manifest image checksum mismatch");
            }
            entries.add(new ManifestEntry(id, image, sha256, group, target));
        }
        return List.copyOf(entries);
    }
}
