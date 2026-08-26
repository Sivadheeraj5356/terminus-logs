package gate;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.List;

public final class TagEvidence {

    private static final Duration ROTATED_GRACE = Duration.ofHours(72);

    private TagEvidence() { }

    public static Result forTag(Path repoRoot, String tag) {
        boolean valid = false;
        String fp = null;
        Instant created = null;

        try {
            Process p = new ProcessBuilder("git", "verify-tag", "--raw", tag)
                .directory(repoRoot.toFile())
                .redirectErrorStream(true)
                .start();
            try (BufferedReader r = new BufferedReader(
                    new InputStreamReader(p.getInputStream(),
                                           StandardCharsets.UTF_8))) {
                String line;
                while ((line = r.readLine()) != null) {
                    if (line.startsWith("[GNUPG:] VALIDSIG")) {
                        String[] parts = line.split("\\s+");
                        if (parts.length >= 3) {
                            valid = true;
                            fp = parts[2];
                        }
                    }
                }
            }
            p.waitFor();
        } catch (Exception ignore) { }

        try {
            Process p = new ProcessBuilder(
                "git", "for-each-ref",
                "--format=%(creatordate:iso-strict)",
                "refs/tags/" + tag)
                .directory(repoRoot.toFile())
                .redirectErrorStream(true)
                .start();
            try (BufferedReader r = new BufferedReader(
                    new InputStreamReader(p.getInputStream(),
                                           StandardCharsets.UTF_8))) {
                String line = r.readLine();
                if (line != null && !line.isBlank()) {
                    created = OffsetDateTime.parse(line.trim()).toInstant();
                }
            }
            p.waitFor();
        } catch (Exception ignore) { }

        return new Result(valid, fp, created);
    }

    public static PolicyEngine.Reason approve(Result ev, List<Db.ApprovedKey> keys) {
        if (!ev.signatureValid() || ev.fingerprint() == null) {
            return new PolicyEngine.Reason("§17.1", "CDSS-KEY-INVSIG", "");
        }
        if (ev.tagCreatedAt() == null) {
            return new PolicyEngine.Reason("§17.1", "CDSS-KEY-017", "");
        }
        String fp = normFp(ev.fingerprint());
        Db.ApprovedKey row = null;
        for (Db.ApprovedKey k : keys) {
            if (normFp(k.fingerprint()).equals(fp)) { row = k; break; }
        }
        if (row == null) return new PolicyEngine.Reason("§17.1", "CDSS-KEY-017", "");
        if (row.approvedAt().isAfter(ev.tagCreatedAt())) {
            return new PolicyEngine.Reason("§17.1", "CDSS-KEY-017", "");
        }
        Instant tagT = ev.tagCreatedAt();
        switch (row.status()) {
            case "active":
                return null;
            case "rotated":
                if (row.revokedAt() == null) return null;
                if (tagT.isBefore(row.revokedAt())) return null;
                if (tagT.isBefore(row.revokedAt().plus(ROTATED_GRACE))) return null;
                return new PolicyEngine.Reason("§17.1", "CDSS-KEY-017", "");
            case "compromised":
                if (row.revokedAt() == null) return null;
                if (tagT.isBefore(row.revokedAt())) return null;
                return new PolicyEngine.Reason("§17.1", "CDSS-KEY-017", "");
            default:
                return new PolicyEngine.Reason("§17.1", "CDSS-KEY-017", "");
        }
    }

    private static String normFp(String s) {
        return s.replaceAll("\\s+", "").toUpperCase();
    }

    public record Result(boolean signatureValid, String fingerprint,
                          Instant tagCreatedAt) { }
}
