package com.example.terminology.assets;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import java.util.List;

@Component
public class AssetLockValidator {
  private static final Pattern FINAL = Pattern.compile("<!--\\s*FINAL_RATIFIED:([^>]+)-->");
  private static final String PUBLIC_ROUTE = "public-synonym";
  private static final String REPO = "HuggingFaceFW/fineweb-edu-score-2";

  @Value("${hf.mirror-root:/data/hf-mirror}")
  private String mirrorRoot;

  @Value("${hf.transcript:/app/docs/release-council-transcript.md}")
  private String transcriptPath;

  public void validate(AssetLock lock) throws Exception {
    if (lock.lockSchemaVersion() == null || lock.lockSchemaVersion().isBlank()) {
      throw new IllegalStateException("missing lock schema version");
    }
    if (!REPO.equals(lock.repository())) {
      throw new IllegalStateException("repository mismatch");
    }
    Policy policy = loadPolicy();
    if (!policy.revision.equals(lock.revision())) {
      throw new IllegalStateException("revision mismatch");
    }
    String transcriptDigest = sha256(Files.readAllBytes(Path.of(transcriptPath)));
    if (!transcriptDigest.equals(lock.transcriptDigest())) {
      throw new IllegalStateException("transcript digest mismatch");
    }
    String gradleDigest = gradleDigest();
    if (!gradleDigest.equals(lock.gradleLockDigest())) {
      throw new IllegalStateException("gradle digest mismatch");
    }
  Path meta = Path.of(mirrorRoot, lock.repository(), "fineweb-edu-score-2", "revisions", lock.revision(), "metadata.json");
    String metaDigest = sha256(canonicalJson(Files.readString(meta)).getBytes());
    if (!metaDigest.equals(lock.sourceMetadataDigest())) {
      throw new IllegalStateException("metadata digest mismatch");
    }
    AssetLock.RouteAssets route = lock.routes().stream()
        .filter(r -> PUBLIC_ROUTE.equals(r.routeId()))
        .findFirst()
        .orElseThrow(() -> new IllegalStateException("missing public route"));
    Set<String> paths = route.files().stream().map(AssetLock.FileAsset::path).collect(Collectors.toSet());
    if (!paths.containsAll(policy.files)) {
      throw new IllegalStateException("missing required route file");
    }
    if (paths.stream().anyMatch(policy.forbidden::contains)) {
      throw new IllegalStateException("forbidden route file present");
    }
    Path filesDir = Path.of(mirrorRoot, lock.repository(), "fineweb-edu-score-2", "revisions", lock.revision(), "files");
    for (AssetLock.FileAsset entry : route.files()) {
      Path file = filesDir.resolve(entry.path());
      byte[] data = Files.readAllBytes(file);
      if (!sha256(data).equals(entry.sha256()) || data.length != entry.bytes()) {
        throw new IllegalStateException("checksum mismatch for " + entry.path());
      }
    }
  }

  private record Policy(String revision, Set<String> files, Set<String> forbidden) {}

  private Policy loadPolicy() throws IOException {
    String text = Files.readString(Path.of(transcriptPath));
    String revision = "";
    Set<String> files = new HashSet<>();
    Set<String> forbidden = new HashSet<>();
    Matcher matcher = FINAL.matcher(text);
    while (matcher.find()) {
      String blob = matcher.group(1).trim();
      String route = value(blob, "route");
      if (!PUBLIC_ROUTE.equals(route)) continue;
      String rev = value(blob, "revision");
      if (!rev.isBlank()) revision = rev;
      String fileList = value(blob, "files");
      if (!fileList.isBlank()) {
        for (String part : fileList.split(",")) if (!part.isBlank()) files.add(part);
      }
      String forb = value(blob, "forbidden");
      if (!forb.isBlank()) {
        for (String part : forb.split(",")) if (!part.isBlank()) forbidden.add(part);
      }
    }
    return new Policy(revision, files, forbidden);
  }

  private static String value(String blob, String key) {
    for (String part : blob.split("\\s+")) {
      if (part.startsWith(key + "=")) return part.substring(key.length() + 1);
    }
    return "";
  }

  private static String gradleDigest() throws Exception {
    Path root = Path.of("/app/gradle/dependency-locks");
    MessageDigest digest = MessageDigest.getInstance("SHA-256");
    List<Path> lockfiles = Files.list(root)
        .filter(p -> p.toString().endsWith(".lockfile"))
        .sorted()
        .toList();
    for (Path path : lockfiles) {
        byte[] raw = Files.readAllBytes(path);
        String normalized = new String(raw, java.nio.charset.StandardCharsets.UTF_8).replace("\r\n", "\n");
        byte[] data = normalized.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        digest.update(path.getFileName().toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
        digest.update((byte) 0);
        digest.update(data);
    }
    return HexFormat.of().formatHex(digest.digest());
  }

  private static String sha256(byte[] data) throws Exception {
    return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data));
  }

  private static String canonicalJson(String raw) throws IOException {
    var mapper = new com.fasterxml.jackson.databind.ObjectMapper();
    return mapper.writeValueAsString(mapper.readTree(raw));
  }
}
