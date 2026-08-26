package nxq.scoreboard;
import nxq.util.Io;
import java.nio.file.*;
import java.util.*;
public final class BoardOut {
  private BoardOut() {}

  public static void writeTranscript(Path out, String caseId, String json) throws Exception {
    Io.write(out.resolve("transcripts").resolve(caseId + ".json"), json);
  }

  public static void writeEpoch(Path out, String generation) throws Exception {
    Io.write(out.resolve("state/hazard.epoch"), generation + "\n");
  }

  public static void writeManifest(Path out, String json) throws Exception {
    Io.write(out.resolve("batch.manifest.json"), json);
  }

  public static void pruneTranscripts(Path out, Set<String> keepIds) throws Exception {
  }
}
