package nxq.scoreboard;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
public final class BoardOut {
  private BoardOut() {}

  private static void atomicWrite(Path target, String content) throws Exception {
    Files.createDirectories(target.getParent());
    Path tmp = target.resolveSibling(target.getFileName().toString() + ".tmp");
    Files.writeString(tmp, content, StandardCharsets.UTF_8);
    try {
      Files.move(tmp, target, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
    } catch (Exception ex) {
      Files.move(tmp, target, StandardCopyOption.REPLACE_EXISTING);
    }
  }

  public static void writeTranscript(Path out, String caseId, String json) throws Exception {
    atomicWrite(out.resolve("transcripts").resolve(caseId + ".json"), json);
  }

  public static void writeEpoch(Path out, String generation) throws Exception {
    atomicWrite(out.resolve("state/hazard.epoch"), generation + "\n");
  }

  public static void writeManifest(Path out, String json) throws Exception {
    atomicWrite(out.resolve("batch.manifest.json"), json);
  }

  public static void pruneTranscripts(Path out, Set<String> keepIds) throws Exception {
    Path dir = out.resolve("transcripts");
    if (!Files.isDirectory(dir)) return;
    try (DirectoryStream<Path> ds = Files.newDirectoryStream(dir, "*.json")) {
      for (Path p : ds) {
        String id = p.getFileName().toString().replace(".json", "");
        if (!keepIds.contains(id)) Files.deleteIfExists(p);
      }
    }
  }
}
